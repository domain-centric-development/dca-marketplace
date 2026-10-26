"""What a story's run left in its journal and its evidence folder: the marks of its stages and gates, the current pass's stage files, the stages running."""

from __future__ import annotations

import hashlib
import os
import re
import typing
from datetime import datetime, timezone
from .hand_over_patterns import CRITERION
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..pipeline.stage_rows import SHARED_WINDOWS, STAGE_FILES
from .story_layout import EPIC_FILE, epic_folder
from ....domain.model.stage import StoryKind
from ....domain.model.story_state import AcceptanceVerdict, HandOverText
from ....domain.service.story_route import StoryRoute
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from .decision_record_files import acceptance_records, latest_verdict
from .journal_files import journal_events
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ....application.status.texts import parse_time
from ....domain.model.journal_marks import JournalMarks, MarkKind, MarkName, Seq
from ....domain.model.stage import StageName
from ....domain.service.current_pass import CurrentPass


OWNED_CHANGED = ".owned-changed"


def last_ended(runs: str, story_id: str, names: typing.Container[str]) -> typing.Optional[str]:
    """Which of the named windows ended last in the story's journal, or None."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    last = None
    if os.path.isfile(journal):
        for line in read_text(journal).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1] == "stage-end" and parts[2] in names:
                last = parts[2]
    return last


def window_open(runs: str, story_id: str, window: str) -> bool:
    """True while the journal's last mark for that exact window name is its start."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    if not os.path.isfile(journal):
        return False
    last = None
    for line in read_text(journal).splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] in ("stage-start", "stage-end") and parts[2] == window:
            last = parts[1]
    return last == "stage-start"


def stage_open(runs: str, story_id: str, stage: str) -> bool:
    """True while the journal's last mark for the stage is its start: the stage is running (plan to tidy
    also while a shared builder, which marks itself `builder`, runs them; judge and document also while a
    shared verifier, `verifier`, runs them)."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    if not os.path.isfile(journal):
        return False
    last = None
    for line in read_text(journal).splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] in ("stage-start", "stage-end") and (
                parts[2] == stage or parts[2] in SHARED_WINDOWS and stage in SHARED_WINDOWS[parts[2]]):
            last = parts[1]
    return last == "stage-start"


def verdict_in(text: str) -> str:
    for line in text.splitlines():
        if line.strip().lower().startswith("verdict:"):
            return line.split(":", 1)[1].strip().strip("`\"' ").lower()
    return ""


def back_in(text: str) -> str:
    """Where a `changes-requested` verdict in <text> sends a story: the domain's rule (`StoryRoute.judged_back`)."""
    return StoryRoute.judged_back(StoryKind.STORY, HandOverText(text)).value


#: What the plan gate leaves for the schedule: the digest of the story it let through, so a story edited
#: afterwards is planned again rather than built on a plan that describes something else. Protocol, not
#: state — a run folder without it is a story to plan. Delivered is written into the story itself
#: (`status: delivered`, `delivered:`), by the document or adopt gate alone.
STORY_DIGEST = ".story-digest"


def write_mark(runs: str, story_id: str, name: str, content: str) -> None:
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
        handle.write(content + "\n")


#: The reports of a gate that delivers.
DELIVERING_REPORT = re.compile(r"^gate-(document|adopt|integrate)\.\d+\.txt$")


def gate_passed_on_record(cwd: str, runs: str, story_id: str, story_path: typing.Optional[str] = None) -> str:
    """Whether a delivering gate's pass is on record for this story — the one rule the views and the migration read:
    the newest document, adopt or integrate report in the evidence folder ends `gate:pass story`, or the story's
    newest acceptance record is accepted (the document gate delivered on it). Returns the reason, or "" where none.
    It is a view of the run, not a truth: without `.dca-factory/` nothing is on record, and nothing that holds is
    lost (the proof that holds is the spec's test line per scenario)."""
    evidence = evidence_dir(runs, story_id)
    reports = sorted((name for name in (os.listdir(evidence) if os.path.isdir(evidence) else [])
                      if DELIVERING_REPORT.match(name)), key=lambda name: os.path.getmtime(os.path.join(evidence, name)))
    if reports:
        lines = read_text(os.path.join(evidence, reports[-1])).strip().splitlines()
        if lines and lines[-1].startswith("gate:pass story"):
            return f"{reports[-1]} passed"
    try:
        records = acceptance_records(cwd, story_id, story_path)
    except GateError:
        records = []
    if records and latest_verdict(records) is AcceptanceVerdict.ACCEPTED:
        return f"{records[-1][0]} accepted"
    return ""



ACCEPTED_TESTS = re.compile(r"\s+—\s+`[^`]*`$")


def accepted_criteria(body: str) -> typing.List[typing.Tuple[str, str]]:
    """The criteria an acceptance record listed, as (key, text) — the story as it was accepted."""
    found: typing.List[typing.Tuple[str, str]] = []
    for line in section_of(body, "question") or []:
        match = CRITERION.match(line.strip())
        if match:
            found.append((match.group(1), ACCEPTED_TESTS.sub("", match.group(2)).strip()))
    return found


def pass_marks(runs: str, story_id: str) -> typing.Dict[str, int]:
    """{name: seq} of what the journal says about the hand-overs: `wrote:<file>` (the last write), `pass:<gate>` (the
    last pass of that gate), `fail:<gate>` (the last refusal), `outdated:<file>` (marked an earlier pass's)."""
    marks: typing.Dict[str, int] = {}
    for event in journal_events(runs, story_id):
        kind, name, fields = event["kind"], event["name"], event["fields"]
        if kind == "wrote" and fields.get("sha") != "gone":
            marks[f"wrote:{name}"] = event["seq"]
        elif kind == "wrote":
            marks.pop(f"wrote:{name}", None)
        elif kind == "gate":
            # 3: every check passed and a person is asked — the file holds, though the gate has not passed yet
            marks[f"{'pass' if fields.get('exit') == '0' else 'held' if fields.get('exit') == '3' else 'fail'}:{name}"] \
                = event["seq"]
        elif kind == "outdated":
            marks[f"outdated:{name}"] = event["seq"]
    return marks


def journal_marks(marks: typing.Mapping[str, int]) -> JournalMarks:
    """The `<kind>:<name>` marks as the domain reads them."""
    seqs = {}
    for key, seq in marks.items():
        kind, _, name = key.partition(":")
        seqs[(MarkKind(kind), MarkName(name))] = Seq(seq)
    return JournalMarks(seqs)


def written_at(marks: typing.Mapping[str, int], stage: str) -> typing.Optional[int]:
    """When the stage's file last held for the pass (`CurrentPass.written_at`)."""
    at = CurrentPass.written_at(journal_marks(marks), StageName(stage))
    return None if at is None else at.value


def gate_passed_since(runs: str, story_id: str, gate: str, stage: str) -> bool:
    """Whether the gate passed after the stage's file was last written — the runner's or a stage's own run."""
    marks = pass_marks(runs, story_id)
    return os.path.isfile(os.path.join(runs, story_id, STAGE_FILES[stage])) \
        and marks.get(f"pass:{gate}", 0) >= marks.get(f"wrote:{STAGE_FILES[stage]}", 0) > 0


def current_stage_files(runs: str, story_id: str, order: typing.Iterable[str]) -> typing.Dict[str, str]:
    """{stage: text} for the stage files of the story's current pass, from the journal's order alone. A stage that
    ran again — a re-plan, a build after `changes-requested`, a test stage applying an answer — makes every later file
    an earlier pass's: it stays on disk as history, but it no longer says where the story stands. A stage whose gate
    passed after the file before it was written holds for this pass, though its own file is older: a shared session
    that went back to its test stage after the build and had the build gate pass again."""
    folder = os.path.join(runs, story_id)
    present = {StageName(stage) for stage in order if os.path.isfile(os.path.join(folder, STAGE_FILES[stage]))}
    holding = CurrentPass.holding(journal_marks(pass_marks(runs, story_id)), [StageName(s) for s in order], present)
    return {stage.value: read_text(os.path.join(folder, STAGE_FILES[stage.value])) for stage in holding}


def backlog_digest(story_path: typing.Optional[str]) -> str:
    """The story and its epic as the plan gate read them: a refusal holds until one of the two changes."""
    digest = hashlib.sha256()
    for path in (story_path, story_path and os.path.join(epic_folder(story_path), EPIC_FILE)):
        if path and os.path.isfile(path):
            with open(path, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def story_title(front: typing.Mapping[str, typing.Any], body: str) -> str:
    """The story's own name: `title:` in its front matter, else its first heading."""
    if str(front.get("title", "")).strip():
        return str(front["title"]).strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""




#: What a stage name may look like for the runner: the cli prints the table as shell lines the runner evaluates,
#: so a name is checked to be a plain word before it is printed.
STAGE_WORD = re.compile(r"[a-z][a-z0-9_-]*")


def run_stories(runs: str) -> typing.List[str]:
    """Every story with a run folder or an evidence folder — a story's journal outlives its deleted run folder."""
    folders = (runs, evidence_dir(runs))
    return sorted({d for root in folders if os.path.isdir(root) for d in os.listdir(root)
                   if os.path.isdir(os.path.join(root, d))})


# Two workers on one checkout build on each other's unfinished code. The claim is a file created
# exclusively — of two workers asking at the same moment, one gets it — in the git directory, so it is
# per checkout (a worktree has its own), never committed and never an untracked file the commit check
# would call drift. A holder renews it before every stage; one that stops renewing is stale after
# FACTORY_STALE_AFTER seconds (default two hours) and may be taken over, which is said out loud.
def stale_after() -> int:
    try:
        return max(0, int(os.environ.get("FACTORY_STALE_AFTER", "7200")))
    except ValueError:
        return 7200


def step_open(runs: str, story_id: str, name: str) -> bool:
    """True while the journal's last mark for the runner's step <name> (integrate, merge, format) is its start. A
    delivery ends the integrate step with its own record, before its commit; the runner ends a step nothing ended."""
    marks = [e["kind"] for e in journal_events(runs, story_id)
             if e["kind"] in ("step-start", "step-end") and e["name"] == name]
    return bool(marks) and marks[-1] == "step-start"


def running_stages(runs: str) -> typing.List[typing.Tuple[str, str, str]]:
    """[(story, stage, started)] for every stage whose journal shows a start and no end yet — or, where no stage
    runs, the runner's own step (`step-start`/`step-end`: integrate, merge, format), which no stage's reader counts.

    The journal knows that a stage began, not whether its process is still alive: a stage whose
    runner was killed reads the same, which is why the start time is shown with it. A stage that waits for the tool's
    usage limit (`limit` line, #161) reads as started at the reset it waits for: alive until then."""
    found: typing.List[typing.Tuple[str, str, str]] = []
    for story in run_stories(runs):
        journal = os.path.join(evidence_dir(runs, story), "journal.tsv")
        if not os.path.isfile(journal):
            continue
        open_stage: typing.Optional[typing.Tuple[str, str]] = None
        steps: typing.List[typing.Tuple[str, str]] = []
        # By time, not by position: a union merge interleaves two branches' lines.
        for line in sorted(read_text(journal).splitlines(), key=lambda l: parse_time(l.split("\t")[0])
                           or datetime.min.replace(tzinfo=timezone.utc)):
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            if parts[1] == "stage-start":
                open_stage = (parts[2], parts[0])
            elif parts[1] == "stage-end" and open_stage and parts[2] == open_stage[0]:
                open_stage = None
            elif parts[1] == "limit" and open_stage and parts[2] == open_stage[0]:
                until = next((f[len("until="):] for f in parts[3:] if f.startswith("until=")), "")
                until_at = parse_time(until)
                if until_at and until_at > (parse_time(open_stage[1]) or until_at):
                    open_stage = (open_stage[0], until)
            elif parts[1] == "step-start":
                steps.append((parts[2], parts[0]))
            elif parts[1] == "step-end":
                steps = [step for step in steps if step[0] != parts[2]]
        running = open_stage or (steps[-1] if steps else None)
        if running:
            found.append((story, running[0], running[1]))
    return found
