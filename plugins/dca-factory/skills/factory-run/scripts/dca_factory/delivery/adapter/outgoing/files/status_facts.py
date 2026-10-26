"""What the status reads, from the project's files and the factory's processes: the schedule, a story's journal,
its records, the running stages and the activity inside them, the epics, the worker, the claims of other factories —
raw, as they are written. What they mean for a person is the status read model's."""

from __future__ import annotations

import datetime
import glob
import json
import os
import re
import typing

from ..pipeline.stage_rows import SHARED_WINDOWS, STAGE_ORDER
from .findings_files import finding_records, FINDINGS_FILE
from .story_layout import delivered_on, find_story, story_kind
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, read_profile, resolve_profile, shown
from .decision_record_files import decision_files, records_of
from ....application.profile.profile_rules import perspectives_of
from ..tools.agents import TOOLS
from ..tools.streams import follow_lines, READERS, session_reader, session_usage_allowed, stream_parts, WINDOWS
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter, read_text
from ..claims.remote_claims import cached_claims
from ..claims.checkout_claim import claim_path, listener_line, read_claim
from .usage_files import resolve_window
from .run_marks import running_stages, story_title
from .journal_files import flaky_tests
from ....application.status.texts import parse_time
from ....domain.model.usage import USAGE_FIELDS
from ..process.factory_process import ended, worker
from .epic_files import epic_files
from .story_files import names_story
from ....domain.model.correction import REASON_CODES
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .signals import latest_signal
from .journal_files import journal_events
from ....application.shared.front import is_acceptance
from ....domain.model.decision_record import ANSWERED_WORDS

GateError = MarkdownError

Facts = typing.Dict[str, typing.Any]
#: Records as the contract reads them: one tuple per record.
Records = typing.List[typing.Tuple[typing.Any, ...]]

def duplicate_pipeline_note(cwd: str) -> typing.Optional[str]:
    """A session sees the person's plugins as well as the project's skills. With the dca-factory plugin
    enabled and a project copy installed, a stage run in the session may pick either copy — the
    runner's stage processes see only the project, a session does not."""
    if not os.path.isfile(os.path.join(cwd, ".claude", "skills", "factory-run", "SKILL.md")):
        return None
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    for settings in (os.path.join(home, "settings.json"), os.path.join(cwd, ".claude", "settings.json"),
                     os.path.join(cwd, ".claude", "settings.local.json")):
        try:
            with open(settings, encoding="utf-8") as handle:
                enabled = (json.load(handle) or {}).get("enabledPlugins") or {}
        except (OSError, ValueError):
            continue
        if any(str(key).startswith("dca-factory@") and value for key, value in enabled.items()):
            return ("note: the dca-factory plugin is enabled and the project has its own copy — a stage run in a "
                    "session may pick the plugin's skills; the runner's stages see only the project's")
    return None


def activity_logs(cwd: str, owner: str, since: typing.Optional[datetime.datetime]) -> typing.List[str]:
    """The session logs a running stage writes into while it works: the worker's own session and its
    subagents where the claim names a session, else the tool's logs for this project directory that
    changed since the stage started (a runner's stage process has a session of its own)."""
    kind, _, session_id = (owner or "").partition(":")
    reader = session_reader(kind)
    if reader:
        return reader.session_logs(session_id)
    return [path for reader in READERS.values() for path in reader.project_logs(cwd, since)]


def last_tool_call(path: str) -> str:
    """`Name: first words of its input` of the newest tool call in a Claude or Codex session log."""
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - 262144))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
        for block in reversed(content if isinstance(content, list) else []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                given = block.get("input") or {}
                detail = next((str(given[k]) for k in ("command", "description", "skill", "file_path", "pattern")
                               if isinstance(given, dict) and given.get(k)), "")
                detail = " ".join(detail.split())
                return f"{block.get('name')}" + (f": {detail[:70]}" + ("…" if len(detail) > 70 else "") if detail else "")
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if payload.get("type") in ("function_call", "local_shell_call"):
            return str(payload.get("name") or payload.get("type"))
    return ""


def activity_line(cwd: str, owner: str, started: str, now: datetime.datetime,
                  output: typing.Optional[str] = None) -> str:
    """The sign of life inside a stage: a stage writes to the journal only at its start and its end,
    while its session log grows with every tool call — and a runner's stage process its output (<output>, what
    `follow` shows), read where no session log is. Session logs only where they may be read."""
    if output and os.path.isfile(output) and os.path.getmtime(output) >= (parse_time(started) or now).timestamp():
        age = int(now.timestamp() - os.path.getmtime(output))
        lines, _ended = follow_lines(read_text(output))
        last = next((line.strip() for line in reversed(lines) if line.strip()), "")
        return f"activity: {age_text(age)}" + (f" — {last}" if last else "")
    if not session_usage_allowed(cwd):
        return "activity: not read — session logs are switched off (sessionUsage)"
    logs = [path for path in activity_logs(cwd, owner, parse_time(started)) if os.path.isfile(path)]
    if not logs:
        return "activity: unknown — no session log of this stage found on this machine"
    newest = max(logs, key=os.path.getmtime)
    call = last_tool_call(newest)
    return f"activity: {age_text(int(now.timestamp() - os.path.getmtime(newest)))}" \
        + (f" — last tool call {call}" if call else "")


def age_text(seconds: int) -> str:
    """`40 s ago`, `3 min ago` — how long since a sign of life."""
    return f"{seconds} s ago" if seconds < 120 else f"{seconds // 60} min ago"


def journal_timeline(runs: str, story_id: str) -> typing.List[typing.Tuple[datetime.datetime, str, str, Facts]]:
    """[(time, kind, stage, fields)] of a story's journal, by time — a union merge interleaves lines."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    if not os.path.isfile(journal):
        return []
    events: typing.List[typing.Tuple[datetime.datetime, str, str, Facts]] = []
    # A union merge can hold one window twice — read on one branch, still pending on the other: the read
    # one first, so the pending one is the duplicate that is skipped.
    for line in sorted(read_text(journal).splitlines(), key=lambda l: ("log=" in l or "session=" in l)):
        parts = line.split("\t")
        moment = parse_time(parts[0]) if len(parts) >= 3 else None
        if moment is None:
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        if "unknown" in parts[3:]:
            fields["unknown"] = "1"
        events.append((moment, parts[1], parts[2], fields))
    return sorted(events, key=lambda e: e[0])


def usage_tokens(fields: Facts, resolve: bool = True) -> typing.Optional[typing.Tuple[int, Facts, str, typing.Optional[float]]]:
    """(tokens, new tokens, model) of one usage line, or None where nothing was measured."""
    if fields.get("unknown"):
        return None
    if "window" in fields and ("log" in fields or "session" in fields) and "input" not in fields:
        read = resolve_window(fields) if resolve else None
        if read is None:
            return None
        fields = dict(fields, **{k: str(v) for k, v in read.items()})
    counts = {k: int(fields.get(k, 0) or 0) for k in USAGE_FIELDS}
    return (sum(counts.values()), counts, fields.get("model", ""),
            float(fields["cost"]) if fields.get("cost") else None)


def story_facts(cwd: str, runs: str, story_id: str, front: typing.Optional[Facts] = None) -> Facts:
    """What a story's journal says: when it started and ended, how long its stages took, its passes
    (a pass begins at every plan start), and its tokens — per stage and per pass. When it was delivered
    is the story's own line, `delivered:`, not the journal's."""
    events = journal_timeline(runs, story_id)
    stages: Facts = {}
    passes: typing.List[Facts] = []
    open_starts: typing.Dict[str, datetime.datetime] = {}
    counted: typing.Set[typing.Tuple[str, str]] = set()
    for moment, kind, stage, fields in events:
        if kind == "usage" and fields.get("window"):
            if (stage, fields["window"]) in counted:
                continue
            counted.add((stage, fields["window"]))
        if kind == "stage-start":
            if stage == STAGE_ORDER[0] or not passes:
                passes.append(dict(start=moment, end=None, seconds=0, tokens=0, measured=0, runs=0, stages=set()))
            passes[-1]["stages"].add(stage)
            open_starts[stage] = moment
            entry = stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS},
                                                  cost=0.0, priced=0, requested=set(), not_applied=0))
            entry["runs"] += 1
            passes[-1]["runs"] += 1
            if fields.get("tool"):
                entry.setdefault("tools", set()).add(fields["tool"])
            if fields.get("effort") and not str(fields["effort"]).startswith("no"):
                entry.setdefault("efforts", set()).add(fields["effort"])
            if fields.get("model_requested"):
                entry["requested"].add(fields["model_requested"])
            if str(fields.get("model_applied", "")).startswith("no"):
                entry["not_applied"] += 1
        elif kind == "window-start":
            open_starts[stage] = moment
            stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS},
                                          cost=0.0, priced=0, requested=set(), not_applied=0))["runs"] += 1
        elif kind == "window-end" and stage in open_starts:
            stages[stage]["seconds"] += (moment - open_starts.pop(stage)).total_seconds()
        elif kind == "stage-end" and stage in open_starts:
            took = (moment - open_starts.pop(stage)).total_seconds()
            stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS}, cost=0.0,
                                          priced=0, requested=set(), not_applied=0))["seconds"] += took
            if passes:
                passes[-1]["seconds"] += took
                passes[-1]["end"] = moment
        elif kind == "usage":
            read = usage_tokens(fields)
            entry = stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS},
                                                  cost=0.0, priced=0, requested=set(), not_applied=0))
            if read is None:
                continue
            tokens, counts, model, cost = read
            entry["tokens"] += tokens
            for k in USAGE_FIELDS:
                entry[k] = entry.get(k, 0) + counts[k]
            entry["measured"] += 1
            if model and model != "unknown":
                entry["models"].update(model.split(","))
            if cost is not None:
                entry["cost"] += cost
                entry["priced"] += 1
            if passes and stage not in WINDOWS:
                passes[-1]["tokens"] += tokens
                passes[-1]["measured"] += 1
    started = events[0][0] if events else None
    tokens = sum(e["tokens"] for e in stages.values())
    invocations = sum(e["runs"] for e in stages.values())
    measured = sum(e["measured"] for e in stages.values())
    return dict(started=started, delivered=parse_time(delivered_on(front or {})), stages=stages,
                passes=passes, tokens=tokens, runs=invocations, measured=measured,
                seconds=sum(e["seconds"] for e in stages.values()),
                cost=sum(e["cost"] for e in stages.values()), priced=sum(e["priced"] for e in stages.values()))


def story_records(cwd: str, story_id: str, story_path: typing.Optional[str] = None) -> Records:
    try:
        return records_of(story_id, story_path)
    except GateError:
        return []


def story_round(runs: str, story_id: str) -> int:
    """The round a story is in: 1, then one more for every gate refusal the runner counted (`.rounds`)."""
    path = os.path.join(evidence_dir(runs, story_id), ".rounds")
    text = read_text(path).strip() if os.path.isfile(path) else ""
    return (int(text) if text.isdigit() else 0) + 1


def window_part_now(runs: str, story_id: str, window: str) -> str:
    """The stage a running shared window is in, from its newest stream — '' when it has not loaded one."""
    outs = sorted(glob.glob(os.path.join(evidence_dir(runs, story_id), f"{window}.*.out")))
    if not outs:
        return ""
    parts, _cost = stream_parts(max(outs, key=os.path.getmtime))
    return parts[-1]["stage"] if parts else ""


def follow_newest(runs: str, story: typing.Optional[str] = None,
                  process: typing.Optional[str] = None) -> typing.Optional[typing.Tuple[str, str, str]]:
    """(story, stage, path) of the newest stage output, of one story or of every story — None if none."""
    pattern = os.path.join(evidence_dir(runs, story or "*"), f"{process}.*.out" if process else "*.out")
    outs = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    if not outs:
        return None
    path = max(outs, key=lambda p: (os.path.getmtime(p), p))
    return (os.path.basename(os.path.dirname(path)),
            os.path.basename(path).split(".")[0], path)


def dangling_skill_links(cwd: str) -> typing.List[str]:
    """The entries of the tools' skill directories that are links to nothing, as relative paths."""
    found: typing.List[str] = []
    for folder in [tool.skills for tool in TOOLS]:
        path = os.path.join(cwd, folder)
        if os.path.islink(path) and not os.path.exists(path):
            found.append(folder)
            continue
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            entry = os.path.join(path, name)
            if os.path.islink(entry) and not os.path.exists(entry):
                found.append(f"{folder}/{name}")
    return found


class StatusFactFiles:
    """The status's facts, read from the project <cwd> with its epics and run folder as the profile places them;
    the schedule is the schedule's read model, which the composition root hands in."""

    def __init__(self, cwd: str, epics: str, runs: str, schedule: typing.Callable[[], Facts]) -> None:
        self._cwd, self._epics, self._runs, self._schedule = cwd, epics, runs, schedule

    def now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    def project_name(self) -> str:
        return os.path.basename(os.path.abspath(self._cwd))

    def profile(self) -> typing.Dict[str, str]:
        return read_profile(resolve_profile(None, self._cwd))

    def schedule(self) -> Facts:
        return self._schedule()

    def story_facts(self, story_id: str, front: typing.Optional[Facts]) -> Facts:
        return story_facts(self._cwd, self._runs, story_id, front)

    def story_records(self, story_id: str, path: typing.Optional[str]) -> Records:
        return story_records(self._cwd, story_id, path)

    def decision_files(self) -> Records:
        return list(decision_files(self._cwd))

    def has_journal(self, story_id: str) -> bool:
        return os.path.isfile(os.path.join(evidence_dir(self._runs, story_id), "journal.tsv"))

    def flaky_tests(self, story_id: str) -> typing.List[str]:
        return list(flaky_tests(self._runs, story_id))

    def story_signals(self, story_id: str, records: Records, body: str) -> Facts:
        return story_signals(self._runs, story_id, records, body)

    def running_stages(self) -> typing.List[typing.Tuple[str, str, str]]:
        return running_stages(self._runs)

    def shared_windows(self) -> typing.Mapping[str, typing.Tuple[str, ...]]:
        return SHARED_WINDOWS

    def window_part(self, story_id: str, window: str) -> str:
        return window_part_now(self._runs, story_id, window)

    def story_round(self, story_id: str) -> int:
        return story_round(self._runs, story_id)

    def claim(self) -> typing.Optional[Facts]:
        return read_claim(claim_path(self._cwd))

    def activity(self, owner: str, started: str, now: datetime.datetime, story_id: str) -> str:
        output = (follow_newest(self._runs, story_id) or (None, None, None))[2]
        return activity_line(self._cwd, owner, started, now, output)

    def epic_files(self) -> typing.List[Facts]:
        return epic_files(self._epics)

    def story_kind(self, path: str) -> str:
        try:
            return story_kind(read_front_matter(path)[0])
        except GateError:
            return "story"

    def epic_text(self, story_path: str) -> str:
        epic_md = os.path.join(os.path.dirname(os.path.dirname(story_path)), "epic.md")
        return read_text(epic_md) if os.path.isfile(epic_md) else ""

    def worker(self) -> typing.Optional[Facts]:
        return worker(self._cwd)

    def ended(self) -> typing.Optional[Facts]:
        return ended(self._cwd)

    def listener(self) -> typing.Optional[str]:
        return listener_line(self._cwd)

    def dangling_skill_links(self) -> typing.List[str]:
        return dangling_skill_links(self._cwd)

    def duplicate_pipeline_note(self) -> typing.Optional[str]:
        return duplicate_pipeline_note(self._cwd)

    def findings_name(self) -> str:
        return FINDINGS_FILE

    def finding_records(self) -> typing.List[Facts]:
        return finding_records(self._epics)

    def perspectives(self, profile: typing.Dict[str, str]) -> typing.List[typing.Tuple[str, str]]:
        return perspectives_of(profile)

    def foreign_claims(self) -> typing.List[Facts]:
        return foreign_claim_facts(self._epics, self._runs)

    def shown(self, path: str) -> str:
        return shown(path)

    def names_story(self, word: str) -> bool:
        return names_story(word)


def foreign_claim_facts(epics: str, runs: str) -> typing.List[Facts]:
    """The claims other factories hold, as the last fetch saw them (no fetch here — a session's start and the cockpit
    stay quick and offline), each with this checkout's story under its id: `here`, its `own_epic` and `own_title`."""
    found = []
    for story, c in sorted(cached_claims(runs).items()):
        if c["own"]:
            continue
        entry = dict(c, story=story, here=False, own_epic="", own_title="")
        try:
            path = find_story(epics, story)
        except GateError:
            found.append(entry)
            continue
        front, body = read_front_matter(path)
        entry.update(here=True, own_epic=str(front.get("epic") or os.path.basename(os.path.dirname(os.path.dirname(path)))).strip(),
                     own_title=story_title(front, body) or story)
        found.append(entry)
    return found


CORRECTION_CODE = re.compile(r"^\s*correction:\s*([a-z-]+)\s*:", re.I)


def correction_code(answer: typing.Any) -> typing.Optional[str]:
    """The reason code of an acceptance correction's answer, `uncoded` for one that names none (or none known), None
    for an answer that is no correction."""
    text = str(answer or "").strip()
    if not text.lower().startswith("correction:"):
        return None
    match = CORRECTION_CODE.match(text)
    return match.group(1).lower() if match and match.group(1).lower() in REASON_CODES else "uncoded"


def story_signals(runs: str, story_id: str, records: typing.Sequence[typing.Any], body: str) -> Facts:
    """WP-148 B/C: the raw facts of one story the bench aggregates — questions the stages asked and how many a person
    answered, the story's assumptions open and answered, what the plan left open, each named rule's verdict at the
    test gate, the judge's confirmed findings by perspective and domain code, the acceptance corrections by reason
    code. Counted, never rated. What a gate decided is read from the journal alone (WP-150): a fact no gate recorded
    is None — "not recorded", never 0."""
    questions = [(front, state) for _p, front, _b, state, _a in records if not is_acceptance(front)]
    lines = [l.strip()[1:].strip().lower() for l in section_of(body, "assumptions") or [] if l.strip().startswith(("-", "*"))]
    events = journal_events(runs, story_id)
    plan = latest_signal(events, "plan")
    rules_group = latest_signal(events, "rules", "rule")
    rules: typing.Dict[str, int] = {}
    for _sel, fields in rules_group[1] if rules_group else []:
        verdict = fields.get("verdict", "unchecked")
        rules[verdict] = rules.get(verdict, 0) + len([n for n in fields.get("rules", "").split(",") if n])
    judge = latest_signal(events, "judge", "finding")
    findings: typing.Dict[str, int] = {}
    domain: typing.Dict[str, int] = {}
    for perspective, fields in judge[1] if judge else []:
        findings[perspective] = findings.get(perspective, 0) + 1
        if fields.get("code"):
            domain[fields["code"]] = domain.get(fields["code"], 0) + 1
    corrections: typing.Dict[str, int] = {}
    for _p, front, _b, state, answer in records:
        code = correction_code(answer.get("answer")) if is_acceptance(front) and state in ANSWERED_WORDS else None
        if code:
            corrections[code] = corrections.get(code, 0) + 1
    return dict(asked=len(questions), answered=sum(1 for _f, st in questions if st in ANSWERED_WORDS),
                assumptions_open=sum(1 for l in lines if l.startswith("open:")),
                assumptions_answered=sum(1 for l in lines if l.startswith("answered:")),
                plan_open=int(plan[0].get("open", 0)) if plan else None,
                rules=rules if rules_group else None,
                findings=findings if judge else None, domain=domain if judge else None,
                corrections=corrections)
