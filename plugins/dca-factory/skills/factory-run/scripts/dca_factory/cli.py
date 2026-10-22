"""Factory CLI — what shows and coordinates a factory run, beside the gate that decides.

The gate (`story-gate.py`, in this folder) reads the project's files and refuses or lets a stage
through. This file is everything a person, a stage or `factory.sh` asks *about* the pipeline. A project
file's content it reads with the gate's readers, which the runner calls in its own process — so the
profile, a stage file and a decision record have one reader, and two callers can never disagree about
what they say.

    factory-cli.py --status [--story <id>] [--format text|md|json] [--live] [--part all|backlog]
    factory-cli.py --status --brief [--session-start]   two lines for a session's start
    factory-cli.py --help-view [--format text|md|json]  the factory explained, with this project's place in it
    factory-cli.py --list-decisions [--story <id>]      the decision inbox, one line per record
    factory-cli.py --discover-list [--format text|md|json]  every discovery topic, its proposals and which are epics
    factory-cli.py --schedule                           every story's state and the next one to run
    factory-cli.py --story <id> --start | --kind        where a run begins | `story`, `journey` or `adopt`
    factory-cli.py --resolve "<argument>"               what /factory-run <argument> means
    factory-cli.py --reopen <story>                     take a delivered story back for a correction
    factory-cli.py --deliver-by-hand <story> --by <who> a story built by hand: delivered, claimed
    factory-cli.py --prove <story>                      a claimed delivery checked through the adopt path
    factory-cli.py --spec-check                         every delivered story's criteria stand in the living spec
    factory-cli.py --claim-story <story> | --claims-refresh | --release-claim <story> [--force]   claims on a remote
    factory-cli.py --free-id <PREFIX>                   the next story id no factory uses
    factory-cli.py --usage [--story <id>] [--total]     tokens per story and stage, from the journals
    factory-cli.py --usage-from <format> <file>         one invocation's usage from a tool's raw output
    factory-cli.py --stage-start|--stage-end <stage> --story <id>    a stage run inside a session
    factory-cli.py --window-start|--window-end <work> --story <id>   writing or answering, measured
    factory-cli.py --claim <owner> | --release [<owner>] | --listening   one worker per checkout

What factory.sh and a stage read through here instead of parsing a file itself:

    factory-cli.py --get <key>                the profile's value for one key ("" when absent)
    factory-cli.py --command-heads            the first word of every command the profile declares
    factory-cli.py --carriers                 the skills the profile names as carriers, reviewers, knowledge
    factory-cli.py --carrier-lines            those keys with their values, one `key value` per line
    factory-cli.py --model <tool> <stage>     `model.<tool>.<stage>`, else `model.<tool>`, else ""
    factory-cli.py --verdict <story>          the judge's verdict of that story, or ""
    factory-cli.py --needs-human <file>       the decision ids a stage file's `## needs-human` names,
                                              `<id>\\t<stage>` per line; exit 1 when it asks nobody
    factory-cli.py --open-decisions <story>   the records that name the story and carry no answer

Options as the gate's: --epics, --runs, --profile (else FACTORY_PROFILE, else the gate's place),
--root, --format, --color, --json.
"""

import argparse
import contextlib
import glob
import json
import os
import re
import shlex
import shutil
import sys
import textwrap
import time
from datetime import datetime, timezone
from .contract import (
    ALL_KINDS, CONTRACT, CREATED_KEY, created_of, decision_files, decision_options, decision_state, DECISIONS_DIR, decisions_store, DEFAULTS, delivered_by, delivered_on,
    EPIC_FILE, epic_folder, evidence_dir, factory_home, find_story, git, FINDINGS_FILE, FORM_CHECKS, GateError, is_delivered, layout_hint,
    finding_records, location, needs_human_ids, open_findings, place, PROFILE_FILE, read_front_matter, read_profile, read_text,
    recommended_option, record_path, records_of, resolve_profile, section_of, set_places, SHARED_WINDOWS, shown, STAGE_FILES, STAGE_ORDER, story_files,
    story_id_of, story_kind, TECH_HEADINGS, VERSION)
from .reports import (
    FOLLOW_ARGS, READERS, reader_of, session_reader, parse_time, part_of_call, session_usage_allowed, _short,
    stream_denials, stream_parts, tokens_of, USAGE_FIELDS, usage_from, WINDOWS)
from .state import (
    cached_claims, story_title, claim_config_here, claim_story, fetch_remote, free_id, PUBLISHED, refresh_claims, release_claim,
    remote_main,
    acceptance_records, accepted, accepted_criteria, back_in, claim, claim_path, freeze_all, gate_passed_on_record,
    has_worktree,
    flaky_tests, is_acceptance, journal_append, journal_events, journal_usage, journal_writer, listener_line, mark_listening,
    mark_stage, mark_window, OWNED_CHANGED, owned_end, PRODUCT_HEADINGS, read_claim, record_owned, release,
    resolve_window, run_stories, RUNNABLE, running_stages, schedule, schedule_data, session_owner, stage_rank, start, story_state,
    verdict_in, worktree_of, write_story_fields)
from .spec import (
    lint_context,
    derived, merge, read_delta, read_spec, render_spec, renamed_rules, story_entries)
from .gate import (
    criteria_of, DESCRIPTION_CHANGES, scenarios_of, spec_target, story_spec, description_part, discovery_items, perspectives_of, story_ids)
from .tools import (
    isolation_args, TOOL, TOOLS, tool_invocation, unprobed_flags)
from .runner import (
    contract_text, document_skeleton, files_skeleton, integrate_finish, integrate_prepare, link_places, migrate_layout,
    command_heads, first_word, model_for, needs_human_lines, open_decision_files, PASS_MARKS, plan_skeleton, run_main,
    stage_names, stages_shell, verdict_of_story, worktree_prepare, worktree_prune, worktree_remove)


def resolve(epics, argument):
    """What `/factory-run <argument>` means — decided here, not by a model: one word naming a story is that
    story; one word naming none is an unknown id, never a new story (a typo stays a typo); more than one
    word is a wish, for the backlog skill to turn into a story; nothing is the backlog."""
    words = argument.split()
    if not words:
        print("backlog")
        return 0
    if len(words) > 1:
        print("wish")
        return 0
    try:
        path = find_story(epics, words[0])
    except GateError:
        known = story_ids(epics) if os.path.isdir(epics) else []
        print(f"unknown {words[0]} — no story by that id under {epics.replace(os.sep, '/')}/"
              + (f"; the backlog has: {', '.join(known)}" if known else "; the backlog has no story yet")
              + ". A wish takes more than one word.")
        return 2
    front, _ = read_front_matter(path)
    print(f"story {story_id_of(path, front)}")
    return 0


def discovery_model(cwd, epics):
    """Every discovery topic with its proposed epics — and which of them the backlog already holds — and its
    proposed description changes. What the report says, read the way `--check-discovery` reads it."""
    profile = read_profile(resolve_profile(None, cwd))
    folder = location(profile, "discovery")
    held = epic_files(epics)
    topics = []
    for name in sorted(os.listdir(os.path.join(cwd, folder))) if os.path.isdir(os.path.join(cwd, folder)) else []:
        report = f"{folder}/{name}/discovery.md".replace(os.sep, "/")
        if not os.path.isfile(os.path.join(cwd, report)):
            continue
        text = read_text(os.path.join(cwd, report))
        title = re.search(r"^# (?:Discovery:\s*)?(.+)$", text, re.M)
        proposals = []
        for pid, fields in discovery_items(text, "Proposed work"):
            epic = next((e["epic"] for e in held if pid in (e["epic"], e["folder"])), "")
            proposals.append(dict(id=pid, **{k: fields.get(k, "") for k in ("intent", "goal", "metric", "domain_contact")},
                                  epic=epic))
        changes = [dict(target=target, change=fields.get("change", ""), why=fields.get("why", ""))
                   for target, fields in discovery_items(text, DESCRIPTION_CHANGES)]
        topics.append(dict(topic=name, report=report, title=title.group(1).strip() if title else name,
                           proposals=proposals, description_changes=changes))
    return dict(project=os.path.basename(os.path.abspath(cwd)), store=folder.replace(os.sep, "/") + "/", topics=topics)


def discovery_list(cwd, epics, fmt="text", colour="auto"):
    model = discovery_model(cwd, epics)
    if fmt == "json":
        print(json.dumps(model, indent=2, ensure_ascii=False))
        return 0
    use = use_colour(colour) if fmt == "text" else False
    out = [f"### Discovery — {model['project']}", ""] if fmt == "md" else [""] + heading(f"Discovery — {model['project']}", use, "═")
    if not model["topics"]:
        out += ["", f"No discovery yet — `/factory-discover <topic>` writes one under {model['store']}."]
    for topic in model["topics"]:
        out += ["", f"**{topic['topic']}** — {topic['title']} (`{topic['report']}`)" if fmt == "md"
                else "  " + bold(f"{topic['topic']}", use) + f"   {topic['title']}   {dim(topic['report'], use)}"]
        for p in topic["proposals"]:
            state = f"epic {p['epic']}" if p["epic"] else f"proposed — /factory-backlog epic {p['id']} --from {topic['report']}"
            out.append(f"- `{p['id']}` → {p['metric']} · {state}" if fmt == "md" else f"    {p['id']}   {p['metric']}   {state}")
        for c in topic["description_changes"]:
            line = f"description: {c['target']} — {c['change']}"
            out.append(f"- {line} · /dca-describe" if fmt == "md" else f"    {line}   /dca-describe")
    print("\n".join(out + [""]))
    return 0


def list_decisions(cwd, story_id=None, fmt="text", colour="auto"):
    """The inbox: every record, what waits for a person first — open, drafts, answered, applied — read
    from the files alone; the same view as the status, in text, Markdown or JSON."""
    records = []
    for name, front, body, state, error, path in decision_files(cwd):
        if error:
            records.append(dict(rank=-1, id=name, state="unreadable", kind="question", story="?", stage="?",
                                asked=None, text=str(error), options=[], recommended=None, path=shown(path)))
            continue
        story = str(front.get("story", "")).strip()
        if story_id and story != story_id:
            continue
        answer = decision_state(body)[1]
        options = [] if is_acceptance(front) else decision_options(body)
        question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
        given = f" → {answer.get('answer')} ({answer.get('by')})" if state in ("answered", "applied") else ""
        records.append(dict(rank={"open": 0, "draft": 1, "answered": 2, "applied": 3}[state],
                            id=str(front.get("id", name)).strip(), state=state,
                            kind="acceptance" if is_acceptance(front) else "question", story=story,
                            stage=str(front.get("stage", "?")).strip(),
                            asked=parse_time(str(front.get("asked", ""))), text=question + given,
                            options=[dict(key=o["key"], text=o["text"]) for o in options],
                            recommended=recommended_option(body, options), path=shown(path)))
    records.sort(key=lambda r: (r["rank"], r["id"]))
    waiting = [r for r in records if r["state"] in ("open", "draft", "unreadable")]
    model = dict(project=os.path.basename(os.path.abspath(cwd)), story=story_id, records=records,
                 waiting=len(waiting), store=f"{place('epics')}/<epic>/<story>/{DECISIONS_DIR}/")
    mark = lambda r: "look" if r["kind"] == "acceptance" and r["state"] in ("open", "draft") else \
        "stopped" if r["state"] == "unreadable" else decision_mark(r)
    headers = ["record", "state", "story / stage", "asked (UTC)", "question → answer"]
    cells = lambda marks: [[f"{marks[mark(r)]} {r['id']}", r["state"], f"{r['story']} / {r['stage']}",
                            stamp_text(r["asked"]), r["text"]] for r in records]
    summary = f"{len(records)} record" + ("" if len(records) == 1 else "s") + " · " + \
        (f"{len(waiting)} wait" + ("s" if len(waiting) == 1 else "") + " for you" if waiting else "nothing waits for you")
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
        return 0
    first = next((r for r in records if r in waiting), None)
    how = make_action(skill="/factory-decisions",
                      shell=f"write the answer into {first['path']} under `## Answer`") if first else None
    if fmt == "md":
        lead = "look" if first and first["kind"] == "acceptance" else "question" if waiting else "done"
        out = [f"### Decisions — {model['project']}" + (f" · {story_id}" if story_id else ""), "",
               f"{MARKS_MD[lead]} {summary}", ""]
        if records:
            # the question beside the record would make the table too wide to read: a list below it
            out += table_md(headers[:-1], [c[:-1] for c in cells(MARKS_MD)], first_bold=True)
            out += ["", "**Questions and answers**", ""] + [f"- **{r['id']}** — {r['text']}" for r in records]
        out += ["", f"**Next:** answer {first['id']} — {how_md(how)}" if how else "**Next:** Nothing waits for you."]
        print("\n".join(out))
        return 0
    use = use_colour(colour)
    out = [""] + heading(f"Decisions — {model['project']}" + (f" · {story_id}" if story_id else ""), use, "═")
    lead = "question" if waiting else "done"
    if first and first["kind"] == "acceptance":
        lead = "look"
    out += ["", "  " + paint(f"{MARKS_TEXT[lead]} {summary}", lead, use), ""]
    if records:
        # the question and its answer under each record, over the full width — a column would crush it
        lines = table_text(headers[:-1], [c[:-1] for c in cells(MARKS_TEXT)], colour=use,
                           marks=[mark(r) for r in records], first_bold=True)
        out += lines[:2]
        for row_line, r in zip(lines[2:], records):
            out.append(row_line)
            out += [f"        {piece}" for piece in textwrap.wrap(r["text"], view_width() - 8)]
            out.append("")
        out = out[:-1]
    else:
        out.append(f"    No decision record beside any story ({model['store']}).")
    out += ["", "─" * 72]
    if how:
        out += [f"  {bold('Next', use)}   answer {first['id']}."] + how_lines(how, use, "         ")
    else:
        out.append(f"  {bold('Next', use)}   Nothing waits for you.")
    print("\n".join(out + [""]))
    return 0


def facts_model(cwd, runs, story_id):
    """A story's stage figures from its journal alone — for a journal whose story is not in the backlog."""
    facts = story_facts(cwd, runs, story_id)
    return dict(stages=facts["stages"], models=sorted({m for e in facts["stages"].values() for m in e["models"]}),
                not_applied=sorted({r for e in facts["stages"].values() if e["not_applied"] for r in e["requested"]}),
                priced=facts["priced"] > 0)


def owned_confirm(runs, story_id):
    """The person's word that the story and its answers are as they want them after a stage changed them: the mark
    goes, what changed is journaled, and the story runs on from what its files say."""
    folder = evidence_dir(runs, story_id)
    marked = os.path.join(folder, OWNED_CHANGED)
    if not os.path.isfile(marked):
        print(f"owned: nothing to confirm for {story_id} — no stage changed its story or an answer")
        return 0
    parts = [line.split(":", 1)[1].strip() for line in read_text(marked).splitlines() if line.startswith("changed:")]
    os.remove(marked)
    journal_append(runs, story_id, "owned-confirmed", ",".join(parts))
    print(f"owned: {story_id} — {', '.join(parts)} confirmed as the person's; the story runs on")
    return 0


def refusal_counts(runs, story_id):
    """{who: {"form": n, "substance": n, "checks": {check: n}}} of a story's gate refusals, from its journal: the
    runner's (`by=runner`, or no `by` in an older journal) and the stages' own self-checks apart. A refusal is form
    when every check it names is one of FORM_CHECKS — the hand-over's shape, not the work."""
    counts = {}
    for event in journal_events(runs, story_id):
        fields = event["fields"]
        if event["kind"] != "gate" or fields.get("exit") != "1":
            continue
        who = "runner" if fields.get("by", "runner") == "runner" else "stages"
        failed = [c for c in fields.get("fail", "").split(",") if c]
        entry = counts.setdefault(who, {"form": 0, "substance": 0, "checks": {}})
        entry["form" if failed and all(c in FORM_CHECKS for c in failed) else "substance"] += 1
        for check in failed or ["unnamed"]:
            entry["checks"][check] = entry["checks"].get(check, 0) + 1
    return counts


def refusals_report(runs, story_filter=None, fmt="text"):
    """`--refusals`: every story's refusals, form against substance — what a bench counts."""
    stories = [s for s in run_stories(runs) if not story_filter or s == story_filter]
    data = {story: refusal_counts(runs, story) for story in stories}
    if fmt == "json":
        print(json.dumps({"form_checks": list(FORM_CHECKS), "stories": data}, indent=2, sort_keys=True))
        return 0
    for story, counts in data.items():
        if not counts:
            print(f"{story}  no refusal")
            continue
        parts = []
        for who in ("runner", "stages"):
            entry = counts.get(who)
            if entry:
                checks = ", ".join(f"{c} {n}" for c, n in sorted(entry["checks"].items()))
                label = "runner" if who == "runner" else "the stages' own gates"
                parts.append(f"{label}: {entry['form']} form, {entry['substance']} substance ({checks})")
        print(f"{story}  " + " · ".join(parts))
    return 0


def usage_report(runs, story_filter=None, total_only=False, cwd=".", epics=None, fmt="text"):
    """Tokens by class, as the status shows them: one story's stages, or every story by epic."""
    epics = epics or place("epics")
    stories = run_stories(runs)
    if story_filter:
        stories = [s for s in stories if s == story_filter]
    if total_only:
        print(sum(tokens_of(e) for s in stories for e in journal_usage(runs, s).values()))
        return 0
    colour = use_colour("auto")
    if story_filter:
        try:
            model = story_model(cwd, epics, runs, story_filter)
        except GateError:
            model = facts_model(cwd, runs, story_filter)
        if fmt == "json":
            print(json.dumps(json_ready(model["stages"]), indent=2, ensure_ascii=False))
            return 0
        if not model["stages"]:
            print(f"usage: no stage recorded for {story_filter}")
            return 0
        headers, rows, right = stage_cells(model)
        print("\n".join(section(stage_caption(model), colour) + table_text(headers, rows, right, total=True,
                                                                           colour=colour, first_bold=True) + [""]))
        return 0
    model = status_model(cwd, epics, runs)
    if not model["rows"]:
        print("usage: no story yet")
        return 0
    headers, rows, kinds, right = token_rows(model)
    caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
    print("\n".join(section(caption, colour) + table_text(headers, rows, right, total=True, colour=colour) + [""]))
    return 0


def dangling_skill_links(cwd):
    """The entries of the tools' skill directories that are links to nothing, as relative paths."""
    found = []
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


#: A foreign claim older than this reads as possibly forgotten — a factory that stopped without releasing it.
STALE_CLAIM_DAYS = 3


def claim_age(since, now=None):
    """`3 h`, `6 d`, and whether it is stale — from the claim's UTC stamp; the stamp itself where it is unreadable."""
    from datetime import datetime, timezone
    try:
        began = datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return since or "?", False
    hours = max(0, int(((now or datetime.now(timezone.utc)) - began).total_seconds() // 3600))
    return (f"{hours} h" if hours < 48 else f"{hours // 24} d"), hours >= STALE_CLAIM_DAYS * 24


def foreign_claims(epics, runs):
    """The claims other factories hold, as the last fetch saw them (no fetch here — a session's start and the cockpit
    stay quick and offline): `held` — who holds which story and for how long, `stale` past three days; `orphan` — a
    claim whose story this checkout does not have; `collision` — a claim on an id this checkout uses for another
    story. Each with what a person does about it."""
    found = []
    for story, c in sorted(cached_claims(runs).items()):
        if c["own"]:
            continue
        try:
            path = find_story(epics, story)
        except GateError:
            path = None
        age, stale = claim_age(c["since"])
        entry = dict(story=story, who=c["who"], host=c["host"], since=c["since"], age=age, stale=stale,
                     title=c["title"])
        if not path:
            found.append(dict(entry, kind="orphan", action=make_action(
                text="this checkout has no such story — take the claim away",
                shell=f"{RUNNER} release {story} --force")))
            continue
        front, body = read_front_matter(path)
        epic = str(front.get("epic") or os.path.basename(epic_folder(path))).strip()
        title = story_title(front, body) or story
        if (c["epic"] and c["epic"] != epic) or (c["title"] and c["title"] != title):
            found.append(dict(entry, kind="collision", action=make_action(
                text=f"another factory claimed {story} for \"{c['title']}\" — give yours another id",
                skill="/factory-backlog", shell=f"python3 .agents/factory/factory-cli.py --free-id {re.sub(r'[-_]?[0-9]+$', '', story)}")))
            continue
        found.append(dict(entry, kind="held", action=make_action(
            text="not built here" + ("; a stale claim may be forgotten — ask its holder, or take it away" if stale
                                     else ""),
            shell=f"{RUNNER} release {story} --force" if stale else "")))
    return found


def foreign_claim_lines(epics, runs):
    """The foreign claims as the session's start says them: one line each kind, like the findings."""
    claims = foreign_claims(epics, runs)
    held = [f"{c['story']} ({c['who']} on {c['host']}, {c['age']}{' — stale?' if c['stale'] else ''})"
            for c in claims if c["kind"] == "held"]
    lines = []
    if held:
        lines.append(f"claimed by other factories: {', '.join(held)} — not built here; "
                     f"`factory.sh release <story> --force` takes a stale one away")
    for c in claims:
        if c["kind"] == "orphan":
            lines.append(f"orphan claim {c['story']} — this checkout has no such story; "
                         f"`factory.sh release {c['story']} --force`")
    collisions = [f"{c['story']} — another factory claimed it for \"{c['title']}\"" for c in claims
                  if c["kind"] == "collision"]
    if collisions:
        lines.append(f"id collision: {'; '.join(collisions)} — give yours another id")
    return lines


def status_brief(cwd, epics, runs, session_start=False):
    """Two lines: what is ready, what waits, who works, what it cost — for a session's start."""
    import contextlib
    import io
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        schedule(cwd, epics, runs)
    rows = [l for l in buffer.getvalue().splitlines() if l and not l.startswith(("schedule:", "wait:", "layout:"))]
    nxt = next((l[6:] for l in rows if l.startswith("next: ")), "none")
    states = {}
    for line in rows:
        if line.startswith("next: "):
            continue
        parts = line.split()
        if len(parts) >= 2:
            states.setdefault(parts[1], []).append(parts[0])
    held = read_claim(claim_path(cwd))
    view = status_model(cwd, epics, runs)
    words = {}
    for row in view["rows"]:
        words.setdefault(row["state"], []).append(row["story"])
    summary = " · ".join(f"{len(v)} {k}" for k, v in sorted(words.items())) or "no stories yet"
    print(f"factory: {summary}" + (f" · {view['tokens']:,} tokens so far" if view["measured"] else ""))
    waiting = "; ".join(f"{MARKS_TEXT[w['mark']]} {w['story']} {w['what']}" for w in view["waiting"])
    print("factory: " + (f"waiting for you: {waiting} · " if waiting else "nothing waits for you · ")
          + (f"worker {held.get('owner')} holds the checkout · " if held else "no worker running · ")
          + f"next: {view['next']['text']}")
    listening = listener_line(cwd)
    if listening:
        print(f"factory: {listening}")
    for line in foreign_claim_lines(epics, runs):
        print(f"factory: {line}")
    findings = open_findings(epics)
    if findings:
        stories = sorted({f[0] for f in findings})
        print(f"factory: {len(findings)} open finding(s) in {len(stories)} file(s) "
              f"(<story>/{FINDINGS_FILE} in the story's folder, product/findings/ for the project's own) — "
              f"`factory-cli.py --findings` lists them")
    # A skill link that points nowhere — its plugin version pruned from the cache, a checkout moved: the
    # skills are then missing for a session and a runner stage alike, and only the update relinks them.
    dangling = dangling_skill_links(cwd)
    if dangling:
        more = f" and {len(dangling) - 1} more" if len(dangling) > 1 else ""
        print(f"factory: skill link {dangling[0]} points nowhere{more} — /factory-update relinks them (or copies, with --copy)")
    # The part of the factory that is missing, where the files show it: the description, the backlog.
    profile = read_profile(resolve_profile(None, cwd))
    undescribed = [key for key in ("product", "tech") if not os.path.isfile(os.path.join(cwd, location(profile, key)))]
    if layout_hint(cwd, profile):
        print(f"factory: {layout_hint(cwd, profile)}")
    elif undescribed:
        print(f"factory: no project description ({', '.join(location(profile, k) for k in undescribed)}) — /factory-setup")
    elif not states:
        print("factory: the backlog is empty — /factory-backlog writes the first epic and story")
    if session_start and os.environ.get("FACTORY_WORKER"):
        # A stage the runner started: the hook runs in its session too, and the claim it names is the
        # runner's — this session's own. Said plainly, or a careful model takes itself for a second writer.
        # A shared builder or verifier is named by what it carries out: told it is "stage builder", a model read
        # that as the build stage alone and refused the plan, test and tidy its prompt asked for.
        stage = os.environ.get("FACTORY_STAGE") or "?"
        covered = SHARED_WINDOWS.get(stage)
        what = (f"the shared {stage} of story {os.environ.get('FACTORY_STORY') or '?'} — it carries out the stages "
                f"{', '.join(covered)} one after another, all of them in this session" if covered else
                f"stage {stage} of story {os.environ.get('FACTORY_STORY') or '?'}")
        print(f"dca-factory: this session is {what}, started by the worker {os.environ['FACTORY_WORKER']} "
              "that holds the checkout — the claim and the story's `running` state are this session's own, not a "
              "second writer's. Carry out what the prompt says, write each stage's file under the run folder, and "
              "ask nothing: the runner reads the files when this session ends.")
    elif session_start:
        print("dca-factory: this project delivers stories through the factory. At the person's first message, "
              "unless they already name a task, show the two lines above and ask what they want to do: write or "
              "release a story (/factory-backlog), answer a waiting question (/factory-decisions), start working "
              "the backlog (/factory-run, which keeps asking the schedule; in Claude Code also /loop /factory-run), "
              "look closer (/factory-status), or learn how the factory works (/factory-help). An instruction that "
              "changes what an actor can see or do is a story: ask once, \"As a story through the factory — to an "
              "existing epic, a new epic — or directly by hand?\", and for the factory run /factory-run with the "
              "person's words. A story another factory claimed is not built here, by hand or otherwise; a "
              "`published` one waits for a person's merge. A session never runs `factory.sh run` — it starts a tool "
              "process per stage. A managing session writes backlog and decision files only; the worker is the "
              "one writer in the checkout.")
    return 0


def duplicate_pipeline_note(cwd):
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


def activity_logs(cwd, owner, since):
    """The session logs a running stage writes into while it works: the worker's own session and its
    subagents where the claim names a session, else the tool's logs for this project directory that
    changed since the stage started (a runner's stage process has a session of its own)."""
    kind, _, session_id = (owner or "").partition(":")
    reader = session_reader(kind)
    if reader:
        return reader.session_logs(session_id)
    return [path for reader in READERS.values() for path in reader.project_logs(cwd, since)]


def last_tool_call(path):
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


def activity_line(cwd, owner, started, now):
    """The sign of life inside a stage: a stage writes to the journal only at its start and its end,
    while its session log grows with every tool call. Read only where session logs may be read."""
    if not session_usage_allowed(cwd):
        return "activity: not read — session logs are switched off (sessionUsage)"
    logs = [path for path in activity_logs(cwd, owner, parse_time(started)) if os.path.isfile(path)]
    if not logs:
        return "activity: unknown — no session log of this stage found on this machine"
    newest = max(logs, key=os.path.getmtime)
    age = int(now.timestamp() - os.path.getmtime(newest))
    ago = f"{age} s ago" if age < 120 else f"{age // 60} min ago"
    call = last_tool_call(newest)
    return f"activity: {ago}" + (f" — last tool call {call}" if call else "")


def status(cwd, epics, runs, story_filter=None, fmt="text", colour="auto", live=False, part="all", every=False,
           epic_filter=None):
    """The person's view. Short by default (WP-146): what runs, what waits for them, the next stories in the schedule's
    order and one line of totals; `every` (`--all`) the whole table — every story by epic with times and tokens — and
    `--part backlog` the backlog alone; one story's or one epic's details. The JSON is the whole model whatever the
    form. The same files give the same text; `--live` adds what the clock says."""
    try:
        if story_filter:
            model = story_model(cwd, epics, runs, story_filter, live)
            text = render_story_md(model) if fmt == "md" else render_story_text(model, use_colour(colour))
        elif epic_filter:
            model = epic_model(cwd, epics, runs, epic_filter, live)
            text = render_epic_md(model) if fmt == "md" else render_epic_text(model, use_colour(colour))
        else:
            model = status_model(cwd, epics, runs, live)
            model["part"] = part
            if every or part == "backlog":
                text = render_status_md(model) if fmt == "md" else render_status_text(model, use_colour(colour))
            else:
                text = render_short_md(model) if fmt == "md" else render_short_text(model, use_colour(colour))
    except GateError as error:
        print(f"status: {error}")
        return 1
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
    else:
        print(text)
    return 0


def factory_help(cwd, epics, runs, fmt="text", colour="auto"):
    """The factory explained in one fixed view: the flow with where this project stands in it, every
    command in its agent and its shell form, the marks, the files. The text is the same everywhere;
    only the marks in the flow and the Next line come from the project's files."""
    try:
        model = help_model(cwd, epics, runs)
    except GateError as error:
        print(f"help: {error}")
        return 1
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
    else:
        print(render_help_md(model) if fmt == "md" else render_help_text(model, use_colour(colour)))
    return 0


BUILD_FILES = ("build.gradle", "build.gradle.kts", "pom.xml", "package.json", "pyproject.toml", "go.mod", "Cargo.toml")


SHELL_NAME = "factory.sh"          # the help's tables name the runner short; the view says its full path once


HELP_COMMANDS = (
    ("deliver a wish", "your words become a backlog story — which epic, the criteria — and it runs at once",
     "/factory-run <your words>", ""),
    ("where it stands", "what runs, what waits for you, what comes next, the totals — short",
     "/factory-status", "status"),
    ("every story", "the backlog by epic, newest first, with times and tokens", "/factory-status all", "status --all"),
    ("one story", "its words, criteria, stages, passes and tokens", "/factory-status <story>", "status --story <story>"),
    ("one epic", "what it is for, its text, its stories with their state", "/factory-status <epic>",
     "status --epic <epic>"),
    ("follow a stage", "what the running stage reads, edits and runs, as it happens — whoever started it", "",
     "follow"),
    ("find the problem", "a problem or a wished deliverable → a report with sources and proposed epics, each with "
                         "its outcome event", "/factory-discover <topic>", "discover --check <topic>"),
    ("the discoveries", "every topic, its proposed epics and which are epics already, its proposed description changes",
     "/factory-discover", "discover --list"),
    ("release a proposal", "a discovery's proposed epic becomes an epic in the backlog",
     "/factory-backlog epic <id> --from <report>", ""),
    ("cut stories", "the next stories of an epic, each a draft", "/factory-backlog stories <epic>", ""),
    ("release stories", "drafts become approved after the question pass — open questions keep them drafts",
     "/factory-backlog release <story> …", ""),
    ("guard an epic", "a delivered, unguarded epic gets its journey — the timeline to its outcome event and its "
                      "journey item as a draft", "/factory-backlog journey <epic>", ""),
    ("change the description", "one statement of the product, the stack or the domain, in your words",
     "/dca-describe <change>", ""),
    ("the backlog", "the epics and stories, their state, the next one", "/factory-backlog", "backlog"),
    ("check the backlog", "the plan gate's checks over every open story, writing nothing", "/factory-backlog",
     "backlog --check"),
    ("the inbox", "the open questions and acceptances, and how to answer them", "/factory-decisions", "decisions"),
    ("give up a claim", "with `claim_remote:` — a story's claim on the remote taken back (another's with --force)", "",
     "release <story>"),
    ("deliver again", "with `claim_remote:` — a published story whose merge request lost the race, merged again",
     "", "integrate <story>"),
    ("the profile", "what detection finds against the stack profile", "/factory-setup", "setup --check"),
    ("observe a story", "what a delivered story changed, measured from its files", "/factory-verify <story>",
     "verify --story <story>"),
    ("the machinery", "the pipeline's own suite against fixtures — for whoever changes the pipeline",
     "/factory-verify --fixtures", "verify --fixtures"),
    ("one stage by hand", "stage-plan … stage-document are the six stages the run calls; by hand only to redo one "
                          "stage of a story that has the ones before", "/stage-<stage> <story>", ""),
    ("update the pipeline", "the newest pipeline found, same tools", "/factory-update", "update"),
    ("this help", "the flow, the commands, the marks, the files", "/factory-help", "help"),
)


#: The two parts of the flow: the foundation is written once and changed when things move; the cycle recurs.
PART_WORDS = {"foundation": "once", "cycle": "↻ cycle"}


NOW_WORDS = {"done": "done", "next": "you are here", "look": "waits for your look", "question": "waits for your answer",
             "running": "running"}


HELP_MARKS = (("look", "waits for your look — an acceptance"), ("question", "waits for your answer"),
              ("stopped", "stopped — read why before it runs again"), ("running", "running"),
              ("done", "done — a story, an epic, a decision"), ("none", "nothing to do there now"))


def help_model(cwd, epics, runs):
    profile_path = resolve_profile(None, cwd)
    profile = read_profile(profile_path)
    status_view = status_model(cwd, epics, runs)
    described = all(os.path.isfile(os.path.join(cwd, location(profile, k))) for k in ("product", "tech"))
    has_build = any(os.path.isfile(os.path.join(cwd, name)) for name in BUILD_FILES) \
        or any(name.endswith((".sln", ".slnx", ".csproj")) for name in os.listdir(cwd))
    marks = {m["mark"] for m in status_view["waiting"]}
    rows = status_view["rows"]
    delivered = bool(rows) and all(r["state"] in ("delivered", "superseded") for r in rows)
    has_stories = bool(rows) and not delivered
    waiting_mark = "look" if "look" in marks else ("question" if "question" in marks else "")
    started = described and has_build
    # what waits for a person comes first: nothing of theirs moves until it is answered
    if waiting_mark:
        here = "decide"
    elif not started:
        here = "describe"
    elif not profile_path:
        here = "set up"
    elif not has_stories:
        here = "backlog"
    else:
        here = "run"
    # A foundation, done once and changed when the product or the stack moves, and a cycle that recurs with
    # every body of work. The foundation's steps can be done; the cycle's never are — there the flow marks
    # only where the project is now (waiting, running, next).
    flow = [
        dict(step="describe", part="foundation",
             what="product, technical decisions, designed domain — a new project with its skeleton: /dca-new project",
             skill="/dca-describe", shell="", done=started),
        dict(step="set up", part="foundation", what="the stack profile: build, test, format and browser commands, the carriers",
             skill="/factory-setup", shell="setup --check" if profile_path else "setup", done=bool(profile_path)),
        dict(step="discover", part="cycle", what="optional: which problem is worth solving — a report with sources and "
                                                 "proposed epics, each with its outcome event",
             skill="/factory-discover <topic>", shell="discover --list"),
        dict(step="backlog", part="cycle", what="epics and stories with acceptance criteria; a story runs once released",
             skill="/factory-backlog", shell="backlog"),
        dict(step="run", part="cycle", what="plan → test → build → tidy → judge → document, a gate between the stages",
             skill="/factory-run [<story>]", shell="run [--story <story>]"),
        dict(step="decide", part="cycle", what="a question a stage may not decide alone, or a result to look at: "
                                               "accepted delivers it, a correction goes back into the story",
             skill="/factory-decisions", shell="decisions"),
        dict(step="delivered", part="cycle", what="what is delivered — stories, epics and their outcome events; an epic "
                                                  "without a journey test shows as unguarded",
             skill="/factory-status", shell="status"),
    ]
    for n, f in enumerate(flow, 1):
        f["number"] = n
        if f["step"] == here:
            f["mark"] = waiting_mark if here == "decide" else \
                "running" if here == "run" and status_view["running"] else "next"
        else:
            f["mark"] = "done" if f.pop("done", False) else "none"
        f.pop("done", None)
    if waiting_mark:
        nxt = status_view["next"]
    elif not described and has_build:
        nxt = dict(text="Describe the project — drafted from its code, confirmed by you.",
                   action=make_action(skill="/dca-describe", shell=""))
    elif not has_build:
        nxt = dict(text="Start the project — the description and a skeleton from a generator, in one pass.",
                   action=make_action(skill="/dca-new project", shell=""))
    elif not profile_path:
        nxt = dict(text="Set the factory up — the stack profile is missing.",
                   action=make_action(skill="/factory-setup", shell=f"{RUNNER} setup"))
    else:
        nxt = status_view["next"]
    files = [("description", ", ".join(location(profile, k) for k in ("product", "tech", "domain")),
              "what is built, on which stack, in which contexts"),
             ("spec", location(profile, "spec").rstrip("/") + "/",
              "what holds: per context scenarios.md with a test line each, and its glossary.md; journeys.md"),
             ("epics", epics.replace(os.sep, "/") + "/", "the changes: an epic.md per epic, a folder per story with its story.md; a delivered story says so itself"),
             ("stack profile", (profile_path or PROFILE_FILE).replace(os.sep, "/"),
              "the project's commands and the skills each stage uses"),
             ("decisions", f"{epics.replace(os.sep, '/')}/<epic>/<story>/{DECISIONS_DIR}/",
              "one record per question or acceptance, in its story's folder"),
             ("a story's run", f"{runs}/<story>/", "hand-overs, marks, the journal — protocol, disposable")]
    return dict(project=status_view["project"], flow=flow, commands=[dict(zip(("name", "what", "skill", "shell"), c))
                                                                    for c in HELP_COMMANDS],
                marks=[dict(mark=m, meaning=t) for m, t in HELP_MARKS],
                files=[dict(name=n, where=w, holds=h) for n, w, h in files],
                runner=RUNNER, next=nxt)


def shell_form(command):
    return f"{SHELL_NAME} {command}" if command else ""


def render_help_text(model, colour=False):
    out = [""] + heading(f"Factory help — {model['project']}", colour, "═")
    out += section("The flow — a foundation once, then the cycle — and where this project is now", colour)
    rows = [[f"{f['number']}  {f['step']}", PART_WORDS[f["part"]], NOW_WORDS.get(f["mark"], ""), f["skill"],
             shell_form(f["shell"]) or "— needs an agent session", f["what"]] for f in model["flow"]]
    out += table_text(["step", "part", "now", "agent", "shell", "what it is"], rows,
                      marks=[f["mark"] if f["mark"] != "none" else None for f in model["flow"]], colour=colour, painted=3)
    out += section("Commands", colour)
    out += table_text(["to see", "agent", "shell", "what it shows"],
                      [[c["name"], c["skill"], shell_form(c["shell"]) or "— needs an agent session", c["what"]]
                       for c in model["commands"]],
                      colour=colour, first_bold=True)
    note = f"{SHELL_NAME} is {model['runner']}, in a terminal of its own; a session uses the agent form."
    out += ["", "    " + dim(note, colour)]
    out += section("Marks", colour)
    out += table_text(["mark", "means"], [[MARKS_TEXT[m["mark"]], m["meaning"]] for m in model["marks"]],
                      marks=[m["mark"] for m in model["marks"]], colour=colour, painted=1)
    out += section("Files", colour)
    out += table_text(["what", "where", "holds"], [[f["name"], f["where"], f["holds"]] for f in model["files"]],
                      colour=colour, first_bold=True)
    return "\n".join(out + ["", "─" * 72] + next_text(model, colour) + [""])


def render_help_md(model):
    out = [f"### Factory help — {model['project']}", "",
           "**The flow — a foundation once, then the cycle — and where this project is now**", ""]
    out += table_md(["step", "part", "now", "agent", "shell", "what it is"],
                    [[f"{f['number']} {f['step']}", PART_WORDS[f["part"]], f"**{NOW_WORDS[f['mark']]}**" if f["mark"] in NOW_WORDS else "",
                      f"`{f['skill']}`",
                      f"`{shell_form(f['shell'])}`" if f["shell"] else "— needs an agent session", commands(f["what"], False, md=True)]
                     for f in model["flow"]])
    out += ["", "**Commands**", ""]
    out += table_md(["to see", "agent", "shell", "what it shows"],
                    [[c["name"], f"`{c['skill']}`", f"`{shell_form(c['shell'])}`" if c["shell"] else "— needs an agent session",
                      c["what"]] for c in model["commands"]],
                    first_bold=True)
    out += ["", f"`{SHELL_NAME}` is `{model['runner']}`, in a terminal of its own; a session uses the agent form.",
            "", "**Marks**", ""]
    out += table_md(["session", "terminal", "means"], [[MARKS_MD[m["mark"]], f"`{MARKS_TEXT[m['mark']]}`", m["meaning"]]
                                                      for m in model["marks"]])
    out += ["", "**Files**", ""]
    out += table_md(["what", "where", "holds"], [[f["name"], f"`{f['where']}`", f["holds"]] for f in model["files"]],
                    first_bold=True)
    return "\n".join(out + ["", next_md(model)])


MARKS_TEXT = {"look": "!", "question": "?", "stopped": "✗", "running": "▶", "done": "✓", "none": "·", "next": "→"}


MARKS_MD = {"look": "👀", "question": "❓", "stopped": "⛔", "running": "⏳", "done": "✅", "none": "➖", "next": "👉"}


COLOURS = {"look": "33", "question": "33", "stopped": "31", "running": "34", "done": "32", "none": "2", "next": "36"}


def stamp_text(value):
    """`2026-09-25 14:31` in UTC, or `—`."""
    moment = parse_time(value) if isinstance(value, str) else value
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if moment else "—"


def took_text(seconds):
    if not seconds:
        return "—"
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def tokens_text(tokens, measured=True):
    return f"{tokens:,}" if measured and tokens else "not measured"


def journal_timeline(runs, story_id):
    """[(time, kind, stage, fields)] of a story's journal, by time — a union merge interleaves lines."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    if not os.path.isfile(journal):
        return []
    events = []
    # A union merge can hold one window twice — read on one branch, still pending on the other: the read
    # one first, so the pending one is the duplicate that is skipped.
    for line in sorted(read_text(journal).splitlines(), key=lambda l: ("log=" in l or "session=" in l)):
        parts = line.split("\t")
        if len(parts) < 3 or parse_time(parts[0]) is None:
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        if "unknown" in parts[3:]:
            fields["unknown"] = "1"
        events.append((parse_time(parts[0]), parts[1], parts[2], fields))
    return sorted(events, key=lambda e: e[0])


def usage_tokens(fields, resolve=True):
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


def story_facts(cwd, runs, story_id, front=None):
    """What a story's journal says: when it started and ended, how long its stages took, its passes
    (a pass begins at every plan start), and its tokens — per stage and per pass. When it was delivered
    is the story's own line, `delivered:`, not the journal's."""
    events = journal_timeline(runs, story_id)
    stages, passes, open_starts, counted = {}, [], {}, set()
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


def story_records(cwd, story_id, story_path=None):
    try:
        return records_of(story_id, story_path)
    except GateError:
        return []


RUNNER = "bash .agents/factory/factory.sh"


def make_action(text="", skill="", shell="", look=""):
    """What to do, both ways: `skill` in an agent session, `shell` in a terminal — empty where a
    terminal cannot do it (writing a story needs an agent)."""
    return dict(text=text, skill=skill, shell=shell, look=look)


def story_attention(cwd, story_id, story, profile):
    """(mark, state words, action) for one story — the words a person uses."""
    state, detail = story["state"], story.get("detail", "")
    records = story_records(cwd, story_id, story.get("path"))
    open_records = [(path, front) for path, front, _body, st, _a in records if st in ("open", "draft")]
    record = shown(open_records[0][0]) if open_records else ""
    by_hand = f"write the answer into {record} under `## Answer`" if record else ""
    if state == "waiting" and any(is_acceptance(f) for _p, f in open_records):
        record = next(shown(p) for p, f in open_records if is_acceptance(f))
        return "look", "waiting for your acceptance", make_action(
            skill="/factory-decisions", look=str(profile.get("run", "")).strip() or "start the application",
            shell=f"write accepted or your correction into {record} under `## Answer`")
    if state == "waiting":
        return "question", "waiting for your answer", make_action(skill="/factory-decisions", shell=by_hand)
    if state == "unreleased":
        return "question", "draft — waits for your release", make_action(
            text="release it", skill=f"/factory-backlog release {story_id}",
            shell=f"set `status: approved` in {str(story.get('path', 'the story')).replace(os.sep, '/')}")
    if state == "stopped":
        return "stopped", "stopped", make_action(text=detail, skill=f"/factory-status {story_id}",
                                            shell=f"{RUNNER} status --story {story_id}")
    if "possibly interrupted" in detail:
        return "stopped", "interrupted?", make_action(text=detail, skill=f"/factory-run {story_id}",
                                                 shell=f"{RUNNER} run --story {story_id}")
    if state == "running":
        return "running", "running", make_action()
    if state == "delivered":
        return "done", f"delivered, {detail}" if detail else "delivered", make_action()
    if state == "published":
        return "look", "published — waits for its merge", make_action(
            text="open the merge request from its branch; once merged, any factory's next look releases the claim",
            shell=f"{RUNNER} integrate {story_id}  (only after another merge request landed first)")
    if state == "claimed":
        return "none", "claimed elsewhere", make_action(text=detail, shell=f"{RUNNER} release {story_id} --force")
    if str(story.get("kind", "")) == "adopt" and state in ("ready", "in-progress", "resumable"):
        return "none", "to adopt", make_action(text=detail)
    if state == "blocked":
        return "none", "blocked", make_action(text=detail)
    if state in ("ready", "in-progress", "resumable"):
        words = {"ready": "ready", "in-progress": "in progress", "resumable": "can continue"}[state]
        return "none", words, make_action(text=detail)
    return "none", state, make_action(text=detail)


def status_model(cwd, epics, runs, live=False):
    epics_dir = epics                                 # the folder; `epics` below becomes the list it holds
    profile = read_profile(resolve_profile(None, cwd))
    data = schedule_data(cwd, epics, runs)
    stories, order = data["stories"], data["order"]
    now = datetime.now(timezone.utc)
    rows, waiting = [], []
    for story_id in order:
        story = stories[story_id]
        facts = story_facts(cwd, runs, story_id, story.get("front"))
        mark, words, action = story_attention(cwd, story_id, story, profile)
        done = story["state"] == "delivered"
        stage = "" if done else next((st for sid, st, _t in running_stages(runs) if sid == story_id),
                                     story.get("start") or "")
        journal = os.path.isfile(os.path.join(evidence_dir(runs, story_id), "journal.tsv"))
        # the tests a gate of this story ran again alone and saw green: red in the whole suite, not the story's (WP-113)
        flaky = sorted(flaky_tests(runs, story_id))
        rows.append(dict(journal=journal, done=done, epic=story.get("epic", ""), story=story_id, flaky=flaky,
                         title=story.get("title", ""), mark=mark, created=created_of(story.get("front") or {}),
                         state=words, stage=stage or "—", passes=len(facts["passes"]) or 0,
                         started=facts["started"], delivered=facts["delivered"], seconds=facts["seconds"],
                         tokens=facts["tokens"], measured=facts["measured"], runs=facts["runs"],
                         **{k: sum(e.get(k, 0) for e in facts["stages"].values()) for k in USAGE_FIELDS},
                         cost=facts["cost"], priced=facts["priced"]))
        if mark in ("look", "question", "stopped"):
            waiting.append(dict(mark=mark, story=story_id, what=words, action=action, draft=story["state"] == "unreleased",
                                record=open_record(cwd, story_id, story) if mark != "stopped" else ""))
    for name, front, body, state, error, path in decision_files(cwd):
        story_id = str(front.get("story", "")).strip() if not error else ""
        if story_id in stories:
            continue                                  # its story's row already says so
        if error or state in ("open", "draft"):
            waiting.append(dict(mark="question", story=story_id or name, what="an open question", record=shown(path), draft=False,
                                action=make_action(skill="/factory-decisions",
                                              shell=f"write the answer into {shown(path)} under `## Answer`")))
    running = []
    held = read_claim(claim_path(cwd)) if live else None
    for story_id, stage, started in running_stages(runs):
        if story_id in stories and stories[story_id]["state"] in ("delivered", "superseded"):
            continue
        interrupted = story_id in stories and stories[story_id]["state"] != "running"
        entry = dict(story=story_id, stage=stage, since=parse_time(started), interrupted=interrupted,
                     round=story_round(runs, story_id))
        if stage in SHARED_WINDOWS and not interrupted:
            entry["part"] = window_part_now(runs, story_id, stage)
        if live:
            since = parse_time(started)
            entry["ago"] = took_text((now - since).total_seconds()) + " ago" if since else ""
            entry["activity"] = activity_line(cwd, (held or {}).get("owner", ""), started, now).split(": ", 1)[-1]
        running.append(entry)
    epics = []
    for row in rows:
        if not epics or epics[-1]["epic"] != row["epic"]:
            found = next((e for e in epics if e["epic"] == row["epic"]), None)
            if found is None:
                epics.append(dict(epic=row["epic"], rows=[]))
            else:
                epics.append(epics.pop(epics.index(found)))
        epics[-1]["rows"].append(row)
    for epic in epics:
        epic["rows"].sort(key=lambda r: order.index(r["story"]))
        epic.update(delivered=sum(r["done"] for r in epic["rows"]), total=len(epic["rows"]),
                    tokens=sum(r["tokens"] for r in epic["rows"]), measured=sum(r["measured"] for r in epic["rows"]),
                    seconds=sum(r["seconds"] for r in epic["rows"]))
    epics.sort(key=lambda e: min(order.index(r["story"]) for r in e["rows"]))
    journeys = journey_hints(stories, epics)
    blank = dict(title="", goal="", metric="", discovery="", intent="", domain_contact="", created="", path="")
    files = epic_files(epics_dir)
    for epic in epics:
        own = next((f for f in files if epic["epic"] in (f["epic"], f["folder"])), None)
        epic.update({k: (own or blank)[k] for k in blank})
    named = {e["epic"] for e in epics}
    # an epic whose folder holds no story yet: listed after the others, its next step is cutting them
    for own in files:
        if own["epic"] not in named and own["folder"] not in named:
            epics.append(dict(epic=own["epic"], rows=[], delivered=0, total=0, tokens=0, measured=0, seconds=0,
                              **{k: own[k] for k in blank}))
    empty = [e["epic"] for e in epics if not e["rows"]]
    # The backlog newest first (WP-146): the epics by `created:`, the stories within an epic by theirs — the factory
    # orders, every view shows the order as given. An item without the field comes after the dated ones, in the
    # schedule's order, as does every tie.
    for epic in epics:
        epic["rows"] = newest_first(epic["rows"])
    epics[:] = newest_first(epics)
    # what comes next, in the schedule's order: the stories that can run, and how many cannot yet
    queue = dict(ready=[r["story"] for r in rows if stories[r["story"]]["state"] in RUNNABLE
                        and r["story"] not in {x["story"] for x in running}],
                 blocked=sum(1 for r in rows if stories[r["story"]]["state"] == "blocked"),
                 drafts=sum(1 for r in rows if stories[r["story"]]["state"] == "unreleased"))
    # the delivered stories, the newest delivery first; one without a time (delivered before the field) last
    delivered_order = [r["story"] for r in newest_first([r for r in rows if r["done"]], key="delivered")]
    nxt = data["next"]
    if nxt:
        next_line = dict(text=f"{nxt} can start from {stories[nxt]['start'] or 'plan'} — run it.",
                         action=make_action(skill=f"/factory-run {nxt}", shell=f"{RUNNER} run --story {nxt}"))
    elif empty and all(r["state"] in ("delivered", "superseded") for r in rows):
        next_line = dict(text=f"The epic {empty[0]} has no story yet — cut its stories.",
                         action=make_action(skill=f"/factory-backlog stories {empty[0]}", shell=""))
    elif not rows:
        next_line = dict(text="The backlog is empty — write the first story.",
                         action=make_action(skill="/factory-backlog", shell=""))
    elif all(r["state"] in ("delivered", "superseded") for r in rows):
        next_line = dict(text="Every story is delivered — write the next one.",
                         action=make_action(skill="/factory-backlog", shell=""))
    else:
        holder = next((r for r in rows if r["mark"] in ("look", "question", "stopped")), None)
        busy = next((r for r in rows if r["mark"] == "running"), None)
        if holder:
            until = {"look": "is accepted", "question": "has its answer", "stopped": "is unblocked"}[holder["mark"]]
            text = f"Nothing else starts until {holder['story']} {until} — see Waiting for you."
        elif busy:
            text = f"{busy['story']} is running — one story at a time; nothing to do but wait."
        else:
            text = data["reason"] + "."
        next_line = dict(text=text, action=make_action())
    extra = []
    if live:
        if held:
            extra.append(f"worker: {held.get('owner')} since {stamp_text(held.get('since'))} UTC")
        listening = listener_line(cwd)
        extra.append(listening or "listening: no session has looked at the backlog")
        note = duplicate_pipeline_note(cwd)
        if note:
            extra.append(note)
    # the project description as it stands — the foundation a person writes once and changes when things move
    description = [description_part(cwd, profile, "product", PRODUCT_HEADINGS),
                   description_part(cwd, profile, "tech", TECH_HEADINGS),
                   description_part(cwd, profile, "domain", ())]
    # what else waits for a person: the judge's open minors, other factories' claims (WP-104)
    findings = []
    for found in finding_records(epics_dir):
        story, plain, defect, kept = found["owner"], found["plain"], found["defect"], shown(found["path"])
        # `plain` leads: the finding in one sentence a person understands at once (contract 23; '' in an older row).
        # A project finding (`<product>/findings/<name>.md`, WP-146) belongs to no story: the backlog skill is handed
        # its row, which a task's `closes:` names.
        findings.append(dict(story=story, row=found["row"], project=found["project"], plain=plain, where=found["where"],
                             severity=found["severity"], defect=defect, perspective=found["perspective"],
                             fix=found["fix"], file=kept,
                             action=make_action(text=f"fix it in a story, or set its Status to done or wont-fix in {kept}",
                                                skill=f"/factory-backlog {found['row'] if found['project'] else story}: "
                                                      f"{plain or defect}")))
    # the review perspectives the profile asks for now — a view shows a story's `review:<name>` processes for these
    # alone, never a reviewer a profile named before (an old `reviews/dca.md`, a `review:dca` in the journal)
    perspectives = [dict(name=name, carrier=carrier) for name, carrier in perspectives_of(profile)]
    return dict(project=os.path.basename(os.path.abspath(cwd)), waiting=waiting, running=running, epics=epics,
                findings=findings, claims=foreign_claims(epics_dir, runs), perspectives=perspectives,
                description=description, queue=queue, delivered_order=delivered_order,
                rows=rows, next=next_line, journeys=journeys,
                priced=any(r["priced"] for r in rows), extra=extra, hint=data["hint"],
                delivered=sum(r["done"] for r in rows), total=len(rows),
                tokens=sum(r["tokens"] for r in rows), measured=sum(r["measured"] for r in rows),
                seconds=sum(r["seconds"] for r in rows))


def front_text(value):
    """One front-matter value as text — a list (`key:` with `- item` lines) joined, never its Python form."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def epic_files(epics):
    """Every epic folder with an epic.md, the one with no story yet included — the status lists the epics
    from their own files, not from the stories that name them."""
    found = []
    if not os.path.isdir(epics):
        return found
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, "epic.md")
        if not os.path.isfile(path):
            continue
        try:
            front = read_front_matter(path)[0]
        except GateError:
            front = {}
        found.append(dict(epic=str(front.get("id") or name), folder=name, created=created_of(front), path=shown(path),
                          **{k: front_text(front.get(k))
                             for k in ("title", "goal", "metric", "discovery", "intent", "domain_contact")}))
    return found


def utc_text(moment):
    """A time as the backlog writes it: UTC, to the second, `Z`."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backfill_created(cwd, epics):
    """WP-146: `created:` into every story and every epic that has none — once, idempotent, never over a value there
    (a line `created:` of any content is the person's). The time is the commit that first added the file, followed
    through its renames — a file a layout change moved keeps its first day; a file git does not hold yet takes its own
    modification time. Prints what it wrote."""
    files = story_files(epics) + [os.path.join(epics, e["folder"], EPIC_FILE) for e in epic_files(epics)]
    missing = []
    for path in files:
        try:
            front = read_front_matter(path)[0]
        except GateError:
            continue                              # a file the gate cannot read is named by the gate, not filled here
        if CREATED_KEY not in front:
            missing.append(path)
    if not missing:
        print("backfill: every story and epic has its created: — nothing written")
        return 0
    tracked = git(cwd, "rev-parse", "--is-inside-work-tree")[0] == 0
    written, from_file = {"story": 0, "epic": 0}, 0
    for path in missing:
        rel = os.path.normpath(os.path.relpath(path, cwd))
        stamp = None
        if tracked and git(cwd, "ls-files", "--error-unmatch", "--", rel)[0] == 0:
            # through every rename: a file a layout change moved keeps the day it was first written, not the move's
            code, out = git(cwd, "log", "--follow", "--diff-filter=A", "--format=%aI", "--", rel)
            lines = out.strip().splitlines() if code == 0 else []
            stamp = lines[-1].strip() if lines else None              # the log is newest first: the earliest add
        moment = None
        if stamp:
            with contextlib.suppress(ValueError):
                moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if moment is None:
            moment, from_file = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc), from_file + 1
        write_story_fields(path, **{CREATED_KEY: utc_text(moment)})
        written["epic" if os.path.basename(path) == EPIC_FILE else "story"] += 1
    print(f"backfill: created: written into {written['story']} stor{'y' if written['story'] == 1 else 'ies'} and "
          f"{written['epic']} epic{'' if written['epic'] == 1 else 's'}, from the commit that added each"
          + (f" — {from_file} not in git yet, from the file's own time" if from_file else ""))
    return 0


def created_moment(value):
    """A `created:` (or `delivered:`) value as a UTC time to order by — a date alone at its midnight; None for none."""
    value = str(value or "").strip()
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00") if "T" in value else value + "T00:00:00+00:00")
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def newest_first(items, key="created"):
    """The items newest first by their `key` (a `created:` or a delivery time); the undated after them. Stable: the
    order the items come in decides a tie and among the undated."""
    def moment(item):
        value = item.get(key)
        return value if isinstance(value, datetime) else created_moment(value)
    dated = sorted((i for i in items if moment(i)), key=lambda i: moment(i).astimezone(timezone.utc), reverse=True)
    # sorted(reverse=True) keeps equal items in their order, so a tie stays in the schedule's
    return dated + [i for i in items if not moment(i)]


def story_round(runs, story_id):
    """The round a story is in: 1, then one more for every gate refusal the runner counted (`.rounds`)."""
    path = os.path.join(evidence_dir(runs, story_id), ".rounds")
    text = read_text(path).strip() if os.path.isfile(path) else ""
    return (int(text) if text.isdigit() else 0) + 1


def open_record(cwd, story_id, story):
    """The open record a waiting story waits on, as a path a person reads — '' where none is open."""
    records = story_records(cwd, story_id, story.get("path"))
    opened = [(path, front) for path, front, _b, st, _a in records if st in ("open", "draft")]
    chosen = next((p for p, f in opened if is_acceptance(f)), opened[0][0] if opened else "")
    return shown(chosen) if chosen else ""


def journey_hints(stories, epics):
    """An epic whose stories are all delivered and that has no `kind: journey` item: delivered, unguarded — the way
    to its outcome event has no test. A hint, never a stop. An epic decides against a journey with `- none: <why>`
    under `## Journey`; without the section it has decided nothing."""
    hints = []
    for epic in epics:
        paths = [stories[r["story"]].get("path", "") for r in epic["rows"]]
        kinds = []
        for path in paths:
            try:
                kinds.append(story_kind(read_front_matter(path)[0]) if path else "story")
            except GateError:
                kinds.append("story")
        built = [r for r, k in zip(epic["rows"], kinds) if k == "story"]
        if not built or any(r["state"] != "delivered" for r in built) or "journey" in kinds or not paths[0]:
            continue
        epic_md = os.path.join(epic_folder(paths[0]), EPIC_FILE)
        text = read_text(epic_md) if os.path.isfile(epic_md) else ""
        heading = re.search(r"^## Journey\s*$", text, re.M)
        section = text[heading.end():].split("\n## ", 1)[0] if heading else None
        if section is not None and re.search(r"^\s*-\s*none:", section, re.M):
            continue
        said = "the epic names no journey" if section is None \
            else "its journey is still open" if re.search(r"^\s*-\s*open:", section, re.M) or not section.strip() \
            else "its journey has no journey test yet"
        hints.append(dict(epic=epic["epic"], text=f"delivered, unguarded — {said}",
                          action=make_action(skill=f"/factory-backlog journey {epic['epic']}", shell="")))
    return hints


def paint(text, mark, colour):
    return f"\x1b[{COLOURS[mark]}m{text}\x1b[0m" if colour and mark in COLOURS else text


def bold(text, colour):
    return f"\x1b[1m{text}\x1b[0m" if colour else text


def dim(text, colour):
    return f"\x1b[2m{text}\x1b[0m" if colour else text


COMMAND = re.compile(r"(/(?:factory|dca)-[a-z-]+(?: [A-Za-z0-9][\w.-]*)?)")


def commands(text, colour, md=False):
    """The skills a line names, set apart: cyan on a terminal, `code` in Markdown."""
    if md:
        return COMMAND.sub(r"`\1`", text)
    return COMMAND.sub(lambda m: f"\x1b[36m{m.group(1)}\x1b[0m", text) if colour else text


def how_lines(act, colour, indent):
    """The action as labelled lines: look at it, in an agent session, in a shell."""
    lines = []
    if act.get("text"):
        lines.append(f"{indent}{act['text']}")
    rows = []
    if act.get("look"):
        rows.append(("look at it", act["look"]))
    if act.get("skill"):
        rows.append(("agent", commands(act["skill"], colour)))
        rows.append(("shell", act["shell"] if act.get("shell") else dim("— needs an agent session", colour)))
    for label, value in rows:
        lines.append(f"{indent}{dim(label.ljust(10), colour)}   {value}")
    return lines


def how_md(act):
    parts = []
    if act.get("text"):
        parts.append(act["text"])
    if act.get("look"):
        parts.append(f"look at it: `{act['look']}`")
    if act.get("skill"):
        parts.append(f"`{act['skill']}`" + (f" (in a shell: {act['shell']})" if act.get("shell") else ""))
    return " · ".join(parts)


def next_text(model, colour):
    nxt = model["next"]
    return [f"  {bold('Next', colour)}   {nxt['text']}"] + how_lines(nxt["action"], colour, "         ")


def next_md(model):
    """The session's form: the skill to use; the shell's command beside it where there is one."""
    nxt, act = model["next"], model["next"]["action"]
    line = f"**Next:** {nxt['text']}"
    if act.get("skill"):
        line += f" → `{act['skill']}`" + (f" (in a shell: `{act['shell']}`)" if act.get("shell") else "")
    return line


def table_text(headers, rows, right=(), indent="    ", marks=None, colour=False, widths=None, total=False,
               first_bold=False, painted=2):
    """Aligned columns with a rule under the header; `marks[i]` colours row i's first `painted` cells.
    `widths` makes several tables line up — the backlog's, one per epic; `total` sets the last row
    apart with a rule of its own."""
    widths = list(widths or column_widths(headers, rows))
    # The last column wraps inside its own column rather than being cut: nothing a reader needs is lost.
    # The width is the terminal's where there is one, else a fixed 120 — the same text in a pipe.
    room = view_width() - len(indent) - sum(widths[:-1]) - 3 * (len(widths) - 1)
    wrap_last = len(widths) > 1 and (len(widths) - 1) not in right and widths[-1] > max(room, 30)
    if wrap_last:
        widths[-1] = max(room, 30)
    fmt = lambda cells: "   ".join((str(c).rjust(widths[i]) if i in right else str(c).ljust(widths[i]))
                                   for i, c in enumerate(cells)).rstrip()
    if wrap_last:
        wrapped = []
        for row in rows:
            pieces = textwrap.wrap(str(row[-1]), widths[-1]) or [""]
            wrapped.append(list(row[:-1]) + [pieces[0]])
            wrapped += [[""] * (len(row) - 1) + [piece] for piece in pieces[1:]]
        if marks is not None:
            expanded = []
            for mark, row in zip(marks, rows):
                expanded += [mark] + [None] * (len(textwrap.wrap(str(row[-1]), widths[-1]) or [""]) - 1)
            marks = expanded
        rows = wrapped
    lines = [indent + (bold(fmt(headers), True) if colour else fmt(headers)),
             indent + "   ".join("─" * w for w in widths)]
    for n, row in enumerate(rows):
        is_total = total and n == len(rows) - 1
        if is_total:
            lines.append(indent + "   ".join("─" * w for w in widths))
        line = bold(fmt(row), colour) if is_total else fmt(row)
        if first_bold and colour and not is_total:
            first = str(row[0]).ljust(widths[0])
            line = bold(first, True) + line[len(first):]
        if marks and colour and marks[n]:
            head = "   ".join(str(c).ljust(widths[i]) for i, c in enumerate(row[:painted]))
            line = paint(head, marks[n], True) + line[len(head):]
        lines.append(indent + line)
    return lines


def view_width():
    return shutil.get_terminal_size((120, 24)).columns if sys.stdout.isatty() else 120


def column_widths(headers, rows):
    return [max([len(str(h))] + [len(str(r[i])) for r in rows]) for i, h in enumerate(headers)]


def table_md(headers, rows, right=(), first_bold=False):
    """A Markdown table with its headers in bold; `first_bold` sets the first column apart too."""
    strong = lambda c: f"**{c}**" if str(c) and not str(c).startswith("**") else str(c)
    rows = [[strong(r[0])] + list(r[1:]) for r in rows] if first_bold else rows
    lines = ["| " + " | ".join(strong(h) for h in headers) + " |",
             "|" + "|".join("--:" if i in right else "---" for i in range(len(headers))) + "|"]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return lines


def epic_mark(epic):
    """The epic's own mark, from its stories: what needs you wins, then what stopped, what runs; ✓ when all
    are delivered."""
    marks = [r["mark"] for r in epic["rows"]]
    for wanted in ("look", "question", "stopped", "running"):
        if wanted in marks:
            return wanted
    return "done" if marks and all(m == "done" for m in marks) else "none"


def epic_summary(item):
    parts = [f"{item['delivered']} of {item['total']} delivered",
             tokens_text(item["tokens"], item["measured"]) + (" tokens" if item["measured"] else "")]
    if item["seconds"]:
        parts.append(took_text(item["seconds"]))
    return " · ".join(parts)


def backlog_columns(model):
    headers = ["story", "state", "stage", "passes", "started (UTC)", "delivered (UTC)", "worked"]
    return headers, {3, 6}


def backlog_cells(row, model, marks):
    if not row.get("journal", True) and row["mark"] == "done":
        # delivered before the pipeline kept a journal: said once, not in five empty cells
        return [f"{marks[row['mark']]} {row['story']}", row["state"], "", "", "no journal",
                stamp_text(row["delivered"]), ""]
    return [f"{marks[row['mark']]} {row['story']}", row["state"], row["stage"], row["passes"] or "—",
            stamp_text(row["started"]), stamp_text(row["delivered"]), took_text(row["seconds"])]


def token_rows(model):
    """The tokens per story, grouped by epic with a subtotal each and the total over every story — the
    four classes as the tool reports them."""
    classes = ("input", "output", "cache_write", "cache_read")
    def cells(label, item, runs):
        if not item["measured"]:
            return [label, runs or "—", "—", "—", "—", "—", "not measured"] + (["—"] if model["priced"] else [])
        row = [label, runs] + [f"{item.get(k, 0):,}" for k in classes] + [f"{item['tokens']:,}"]
        return row + ([f"{item.get('cost', 0):.2f}" if item.get("priced") else "—"] if model["priced"] else [])
    rows, kinds = [], []
    for epic in (e for e in model["epics"] if e["rows"]):
        subtotal = {k: sum(r.get(k, 0) for r in epic["rows"]) for k in classes + ("tokens", "measured", "runs", "cost", "priced")}
        rows.append(cells(epic["epic"] or "(no epic)", subtotal, subtotal["runs"]))
        kinds.append("epic")
        for r in epic["rows"]:
            rows.append(cells("  ↳ " + r["story"], r, r["runs"]))
            kinds.append("story")
    grand = {k: sum(r.get(k, 0) for r in model["rows"]) for k in classes + ("tokens", "measured", "runs", "cost", "priced")}
    rows.append(cells("total", grand, grand["runs"]))
    kinds.append("total")
    headers = ["epic / story", "runs", "input", "output", "cache write", "cache read", "total"] \
        + (["cost $"] if model["priced"] else [])
    return headers, rows, kinds, set(range(1, len(headers)))


def heading(text, colour, underline="─"):
    """A title the eye finds: bold where there is colour, underlined always."""
    return [bold(text, colour), underline * len(text)]


def section(text, colour):
    return ["", "  " + bold(text, colour), ""]


#: How many of the stories that can run the short view names; the rest it counts.
QUEUE_SHOWN = 5


#: Where the short view points for more — the same words in the terminal and in a session.
MORE_FORMS = (("every story", "status --all"), ("one story", "status --story <id>"), ("one epic", "status --epic <id>"))


def short_model(model):
    """What the short view shows, decided once for the terminal and the session: the running stages with their round,
    what waits for a person (the drafts in one line), the next stories in the schedule's order — the first few, the
    rest counted — and the totals."""
    queue = model.get("queue") or dict(ready=[], blocked=0, drafts=0)
    by_id = {r["story"]: r for r in model["rows"]}
    shown_ids = queue["ready"][:QUEUE_SHOWN]
    rest = []
    if len(queue["ready"]) > len(shown_ids):
        rest.append(f"{len(queue['ready']) - len(shown_ids)} more ready")
    if queue["blocked"]:
        rest.append(f"{queue['blocked']} blocked")
    totals = [f"{model['delivered']} of {model['total']} delivered", f"{len(queue['ready'])} ready"] if model["total"] \
        else ["no story yet"]
    totals += [f"{queue['blocked']} blocked"] if queue["blocked"] else []
    totals += [f"{queue['drafts']} draft" + ("s" if queue["drafts"] != 1 else "")] if queue["drafts"] else []
    if model["measured"]:
        totals.append(f"{tokens_short(model['tokens'])} tokens")
    if model["seconds"]:
        totals.append(f"{took_text(model['seconds'])} worked")
    if model.get("findings"):
        totals.append(f"{len(model['findings'])} open finding" + ("s" if len(model["findings"]) != 1 else ""))
    return dict(running=model["running"], waiting=[w for w in model["waiting"] if not w.get("draft")],
                drafts=[w["story"] for w in model["waiting"] if w.get("draft")],
                queue=[by_id[i] for i in shown_ids if i in by_id], rest=" · ".join(rest), totals=" · ".join(totals))


def running_words(entry):
    """A running stage as the short view says it: the stage (and the part of a shared one), its round after the
    first, since when."""
    stage = f"{entry['stage']} · {entry['part']}" if entry.get("part") else entry["stage"]
    if entry.get("round", 1) > 1:
        stage += f" · round {entry['round']}"
    line = f"{stage}   since {stamp_text(entry['since'])} UTC"
    if entry.get("interrupted"):
        line += " · never ended — possibly interrupted"
    if entry.get("ago"):
        line += f" · {entry['ago']}"
    return line


def tokens_short(count):
    """A token count at a glance: `481.7 M`, `12.3 k`."""
    return f"{count / 1e6:.1f} M" if count >= 1e6 else f"{count / 1e3:.1f} k" if count >= 1e3 else str(count)


def render_short_text(model, colour=False):
    short = short_model(model)
    section = lambda title, colour: ["", "  " + bold(title, colour)]   # the short view: no blank line under a heading
    out = [""] + heading(f"Factory — {model['project']}", colour, "═")
    out += section("Running", colour)
    for r in short["running"]:
        mark = "stopped" if r.get("interrupted") else "running"
        out.append("    " + paint(f"{MARKS_TEXT[mark]} {r['story']}   {running_words(r)}", mark, colour))
        if r.get("activity"):
            out.append(f"        activity: {r['activity']}")
    if not short["running"]:
        out.append("    Nothing is running.")
    out += section("Waiting for you", colour)
    for n, w in enumerate(short["waiting"]):
        head = f"{MARKS_TEXT[w['mark']]} {w['story']}   {w['what']}" + (f"   {w['record']}" if w.get("record") else "")
        out += ([""] if n else []) + ["    " + paint(head, w["mark"], colour)]
        out += how_lines(w["action"], colour, "        ")
    if short["drafts"]:
        ids = " ".join(short["drafts"])
        out += ([""] if short["waiting"] else []) + [
            "    " + paint(f"{MARKS_TEXT['question']} {len(short['drafts'])} draft(s) wait for your release: {ids}",
                           "question", colour),
            f"        {dim('agent'.ljust(10), colour)}   {commands('/factory-backlog release ' + ids, colour)}"]
    if not short["waiting"] and not short["drafts"]:
        out.append("    Nothing waits for you.")
    out += section("Next in line", colour)
    if short["queue"]:
        cells = [[f"{MARKS_TEXT[r['mark']]} {r['story']}", r["state"], r["title"]] for r in short["queue"]]
        out += table_text(["story", "state", "title"], cells, indent="    ",
                          marks=[r["mark"] for r in short["queue"]], colour=colour)
    else:
        out.append("    Nothing is ready to run.")
    if short["rest"]:
        out.append(f"    … {short['rest']}")
    out += ["", "  " + short["totals"]]
    out += ["", "─" * 72] + next_text(model, colour)
    out.append(f"  {bold('More', colour)}   " + " · ".join(f"{what}: {form}" for what, form in MORE_FORMS))
    if model["extra"]:
        out += [""] + ["  " + line for line in model["extra"]]
    if model["hint"]:
        out += ["", f"  layout: {model['hint']}"]
    return "\n".join(out + [""])


def render_short_md(model):
    short = short_model(model)
    out = [f"### Factory — {model['project']}", "", "**Running**", ""]
    if short["running"]:
        out += [f"- {MARKS_MD['stopped' if r.get('interrupted') else 'running']} **{r['story']}** {running_words(r)}"
                + (f" — {r['activity']}" if r.get("activity") else "") for r in short["running"]]
    else:
        out.append("Nothing is running.")
    out += ["", "**Waiting for you**", ""]
    if short["waiting"]:
        out += table_md(["", "story", "what", "how"],
                        [[MARKS_MD[w["mark"]], w["story"], w["what"] + (f" — `{w['record']}`" if w.get("record") else ""),
                          how_md(w["action"])] for w in short["waiting"]])
    if short["drafts"]:
        ids = " ".join(short["drafts"])
        out += ([""] if short["waiting"] else []) + [
            f"{MARKS_MD['question']} {len(short['drafts'])} draft(s) wait for your release: {ids} → `/factory-backlog release {ids}`"]
    if not short["waiting"] and not short["drafts"]:
        out.append("Nothing waits for you.")
    out += ["", "**Next in line**", ""]
    if short["queue"]:
        out += table_md(["", "story", "state", "title"],
                        [[MARKS_MD[r["mark"]], r["story"], r["state"], r["title"]] for r in short["queue"]])
    else:
        out.append("Nothing is ready to run.")
    if short["rest"]:
        out += ["", f"… {short['rest']}"]
    out += ["", short["totals"], "", next_md(model), "",
            "More — " + " · ".join(f"{what}: `{form}`" for what, form in MORE_FORMS)]
    if model["extra"]:
        out += [""] + [f"- {line}" for line in model["extra"]]
    return "\n".join(out)


def render_status_text(model, colour=False):
    only_backlog = model.get("part") == "backlog"
    out = [""] + heading(f"{'Backlog' if only_backlog else 'Factory'} — {model['project']}", colour, "═")
    if not only_backlog:
        out += waiting_running_text(model, colour)
    return "\n".join(out + backlog_text(model, colour, heading_line=not only_backlog) + [""])


def waiting_running_text(model, colour):
    out = section("Waiting for you", colour)
    if model["waiting"]:
        width = max(len(w["story"]) for w in model["waiting"])
        what = max(len(w["what"]) for w in model["waiting"])
        for n, w in enumerate(model["waiting"]):
            head = f"{MARKS_TEXT[w['mark']]} {w['story'].ljust(width)}   {w['what']}"
            out += ([""] if n else []) + ["    " + paint(head, w["mark"], colour)]
            out += how_lines(w["action"], colour, "        ")
    else:
        out.append("    Nothing waits for you.")
    out += section("Running", colour)
    if model["running"]:
        for r in model["running"]:
            mark = "stopped" if r.get("interrupted") else "running"
            stage = f"{r['stage']} · {r['part']}" if r.get("part") else r["stage"]
            line = f"{MARKS_TEXT[mark]} {r['story']}   {stage}   since {stamp_text(r['since'])} UTC"
            if r.get("interrupted"):
                line += " · never ended — possibly interrupted"
            if r.get("ago"):
                line += f" · {r['ago']}"
            out.append("    " + paint(line, mark, colour))
            if r.get("activity"):
                out.append(f"        activity: {r['activity']}")
    else:
        out.append("    Nothing is running.")
    return out


def backlog_text(model, colour, heading_line=True):
    whole = epic_mark({"rows": model["rows"]})
    summary = paint(f"{MARKS_TEXT[whole]} {epic_summary(model)}", whole, colour) if model["rows"] else ""
    out = section("Backlog" + (f" — {epic_summary(model)}" if model["rows"] else ""), colour) if heading_line \
        else ["", "  " + summary, ""]
    if not model["rows"]:
        out.append("    No story yet.")
    headers, right = backlog_columns(model)
    widths = column_widths(headers, [backlog_cells(r, model, MARKS_TEXT) for r in model["rows"]])
    for n, epic in enumerate(model["epics"]):
        mark = epic_mark(epic)
        out += ([""] if n else []) + ["    " + paint(bold(f"{MARKS_TEXT[mark]} {epic['epic'] or '(no epic)'}", colour), mark, colour)
                                      + (f"   {dim(epic_summary(epic), colour)}" if epic["rows"] else "")]
        if not epic["rows"]:
            out.append(f"      no story yet — {commands('/factory-backlog stories ' + epic['epic'], colour)}")
            continue
        cells = [backlog_cells(r, model, MARKS_TEXT) for r in epic["rows"]]
        out += table_text(headers, cells, right, indent="      ", marks=[r["mark"] for r in epic["rows"]],
                          colour=colour, widths=widths)
    for hint in model.get("journeys", []):
        out += ["", f"    {dim('journey', colour)}   {hint['epic']}: {hint['text']} — {commands(hint['action']['skill'], colour)}"]
    for row in model["rows"]:
        if row.get("flaky"):
            out += ["", f"    {dim('flaky', colour)}   {row['story']}: {', '.join(row['flaky'])} — red in a whole suite, "
                        f"green on its own run; no round counted"]
    if model["rows"]:
        headers, rows, kinds, right = token_rows(model)
        caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
        out += section(caption, colour)
        lines = table_text(headers, rows, right, total=True, colour=colour)
        # epic rows and the total in bold: the sums stand out
        for n, kind in enumerate(kinds):
            index = 2 + n + (1 if kind == "total" else 0)
            if kind == "epic" and colour:
                lines[index] = bold(lines[index], True)
        out += lines
    out += ["", "─" * 72] + next_text(model, colour)
    if model["extra"]:
        out += [""] + ["  " + line for line in model["extra"]]
    if model["hint"]:
        out += ["", f"  layout: {model['hint']}"]
    return out


def render_status_md(model):
    if model.get("part") == "backlog":
        return render_backlog_md(model)
    out = [f"### Factory — {model['project']}", "", "**Waiting for you**", ""]
    if model["waiting"]:
        out += table_md(["", "story", "what", "how"],
                        [[MARKS_MD[w["mark"]], w["story"], w["what"], how_md(w["action"])] for w in model["waiting"]])
    else:
        out.append("Nothing waits for you.")
    out += ["", "**Running**", ""]
    if model["running"]:
        out += table_md(["", "story", "stage", "since"] + (["activity"] if any(r.get("activity") for r in model["running"]) else []),
                        [[MARKS_MD["stopped" if r.get("interrupted") else "running"], r["story"], r["stage"],
                          stamp_text(r["since"]) + " UTC" + (" · never ended — possibly interrupted" if r.get("interrupted") else "")
                          + (f" · {r['ago']}" if r.get("ago") else "")]
                         + ([r.get("activity", "")] if any(x.get("activity") for x in model["running"]) else [])
                         for r in model["running"]])
    else:
        out.append("Nothing is running.")
    return "\n".join(out + backlog_md_lines(model))


def render_backlog_md(model):
    return "\n".join([f"### Backlog — {model['project']}"] + backlog_md_lines(model))


def backlog_md_lines(model):
    out = ["", "**Backlog**" + (f" — {epic_summary(model)}" if model["rows"] else "")]
    if not model["rows"]:
        out += ["", "No story yet."]
    headers, right = backlog_columns(model)
    for epic in model["epics"]:
        out += ["", f"{MARKS_MD[epic_mark(epic)]} *{epic['epic'] or '(no epic)'}* — {epic_summary(epic)}", ""]
        if not epic["rows"]:
            out.append(f"No story yet — `/factory-backlog stories {epic['epic']}`.")
            continue
        out += table_md(headers, [backlog_cells(r, model, MARKS_MD) for r in epic["rows"]], right)
    for hint in model.get("journeys", []):
        out += ["", f"*journey* — {hint['epic']}: {hint['text']} → `{hint['action']['skill']}`"]
    for row in model["rows"]:
        if row.get("flaky"):
            out += ["", f"*flaky* — {row['story']}: {', '.join(f'`{t}`' for t in row['flaky'])} — red in a whole suite, "
                        f"green on its own run; no round counted"]
    if model["rows"]:
        headers, rows, kinds, right = token_rows(model)
        rows = [[f"**{c}**" if kind in ("epic", "total") and str(c) else c for c in row] if kind != "story"
                else [row[0].strip()] + row[1:] for row, kind in zip(rows, kinds)]  # "↳ story" in Markdown
        caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
        out += ["", f"**{caption}**", ""] + table_md(headers, rows, right)
    out += ["", next_md(model)]
    if model["extra"]:
        out += [""] + [f"- {line}" for line in model["extra"]]
    return out


def pass_label(index, pass_, records):
    """First delivery, then what started each later pass: a human's correction, or a re-plan."""
    if index == 0:
        return "first delivery"
    corrections = [str(f["id"]).strip() for _p, f, _b, st, a in records
                   if is_acceptance(f) and st in ("answered", "applied") and not accepted(a)
                   and parse_time(str(a.get("at", ""))) and parse_time(str(a.get("at", ""))) <= pass_["start"]]
    return "correction" if corrections else "again from plan"


def decision_mark(decision):
    """Open or a draft needs you; answered waits for the stage that applies it; applied is done — and
    an answered acceptance is done too: it was applied by the gate or by the re-plan."""
    if decision["state"] in ("open", "draft"):
        return "question"
    if decision["state"] == "applied" or decision["kind"] == "acceptance":
        return "done"
    return "running"


def window_parts(runs, story_id, window):
    """The parts of every run of one shared window of a story, summed per stage, in the stages' order:
    [{stage, runs, seconds, input, cache_read, cache_write, output, tokens, cost (or None), denied}]."""
    order = SHARED_WINDOWS.get(window, ())
    total = {}
    for path in sorted(glob.glob(os.path.join(evidence_dir(runs, story_id), f"{window}.*.out"))):
        parts, cost = stream_parts(path)
        weight = sum(p["weight"] for p in parts)
        denied = [d["stage"] for d in stream_denials(path)]
        for part in parts:
            entry = total.setdefault(part["stage"], dict(stage=part["stage"], runs=0, seconds=0.0, input=0,
                                                         cache_read=0, cache_write=0, output=0, cost=0.0,
                                                         priced=True, denied=0))
            entry["denied"] += denied.count(part["stage"])
            entry["runs"] += 1
            if part["start"] and part["end"]:
                entry["seconds"] += max((part["end"] - part["start"]).total_seconds(), 0)
            for field in USAGE_FIELDS:
                entry[field] += part[field]
            if cost is None or not weight:
                entry["priced"] = False
            else:
                entry["cost"] += cost * part["weight"] / weight
    rows = []
    for stage in [s for s in order if s in total] + [s for s in total if s not in order]:
        entry = total[stage]
        entry["tokens"] = sum(entry[f] for f in USAGE_FIELDS)
        if not entry.pop("priced"):
            entry["cost"] = None
        rows.append(entry)
    return rows


def window_running(entry, runs, story_id, moving, live):
    """A shared window whose process still runs has no usage line yet — the tool reports it at its end. Its row
    shows what the newest stream says so far: the tokens of its parts, and with `live` the time since it began;
    the cost stays the tool's and comes with the end."""
    if not entry or moving["stage"] not in SHARED_WINDOWS or entry["measured"] >= entry["runs"]:
        return
    outs = glob.glob(os.path.join(evidence_dir(runs, story_id), f"{moving['stage']}.*.out"))
    parts = stream_parts(max(outs, key=os.path.getmtime))[0] if outs else []
    for field in USAGE_FIELDS:
        entry[field] = entry.get(field, 0) + sum(p[field] for p in parts)
    entry["tokens"] += sum(p[field] for p in parts for field in USAGE_FIELDS)
    if live and moving.get("since"):
        entry["seconds"] += max((datetime.now(timezone.utc) - moving["since"]).total_seconds(), 0)
    entry["running"] = True


def window_part_now(runs, story_id, window):
    """The stage a running shared window is in, from its newest stream — '' when it has not loaded one."""
    outs = sorted(glob.glob(os.path.join(evidence_dir(runs, story_id), f"{window}.*.out")))
    if not outs:
        return ""
    parts, _cost = stream_parts(max(outs, key=os.path.getmtime))
    return parts[-1]["stage"] if parts else ""


def story_model(cwd, epics, runs, story_id, live=False):
    overview = status_model(cwd, epics, runs, live)
    row = next((r for r in overview["rows"] if r["story"] == story_id), None)
    if row is None:
        raise GateError(f"no story {story_id} under {epics}/")
    data = schedule_data(cwd, epics, runs)["stories"][story_id]
    facts = story_facts(cwd, runs, story_id, data.get("front"))
    records = story_records(cwd, story_id, data.get("path"))
    try:
        criteria = len(criteria_of(data["path"], data["body"], data.get("front")))
    except GateError:
        criteria = 0
    accepted_by = next((str(f["id"]).strip() for _p, f, _b, st, a in reversed(records)
                        if is_acceptance(f) and st in ("answered", "applied") and accepted(a)), None)
    passes = []
    for i, p in enumerate(facts["passes"]):
        before = facts["passes"][i - 1]["end"] if i else None
        passes.append(dict(p, label=pass_label(i, p, records),
                           waited=(p["start"] - before).total_seconds() if before and p["start"] else 0))
    # why a stage ran more than once per pass: the questions it asked, else a repeat (a gate refused it)
    questions = {}
    for _p, front, _b, _st, _a in records:
        if not is_acceptance(front):
            questions.setdefault(str(front.get("stage", "")).strip(), []).append(str(front["id"]).strip())
    for stage, entry in facts["stages"].items():
        if stage in WINDOWS:
            entry["why"] = {"backlog": "writing the story", "decisions": "answering its questions"}[stage] \
                + (f" · {entry['runs']} sessions" if entry["runs"] > 1 else "")
            continue
        extra = entry["runs"] - sum(1 for p in facts["passes"] if stage in p["stages"])
        # a shared window carries several stages: a question any of those stages asked is its
        covered = SHARED_WINDOWS.get(stage, (stage,))
        asked = [rid for name in covered for rid in questions.get(name, [])][:max(extra, 0)]
        repeats = max(extra, 0) - len(asked)
        why = [f"{len(asked)} question" + ("s" if len(asked) > 1 else "") + f" ({', '.join(asked)})"] if asked else []
        if repeats:
            why.append(f"{repeats} repeat" + ("s" if repeats > 1 else "") + " (a gate refused)")
        entry["why"] = " · ".join(why)
    decisions = []
    for _p, front, body, state, answer in records:
        question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
        given = str(answer.get("answer", "")).strip() if state in ("answered", "applied") else ""
        text = (f"{given}" if is_acceptance(front) and given else
                f"{given} — {question}" if given else f"open — {question}")
        decisions.append(dict(id=str(front["id"]).strip(), state=state,
                              kind="acceptance" if is_acceptance(front) else "question", text=text))
    for window in SHARED_WINDOWS:
        if window in facts["stages"]:
            facts["stages"][window]["parts"] = window_parts(runs, story_id, window)
    for moving in overview["running"]:
        if moving["story"] == story_id and not moving["interrupted"]:
            window_running(facts["stages"].get(moving["stage"]), runs, story_id, moving, live)
    # the calls a stage was denied: each a turn spent on another way
    for stage, entry in facts["stages"].items():
        entry["denials"] = [d for path in sorted(glob.glob(os.path.join(evidence_dir(runs, story_id), f"{stage}.*.out")))
                            for d in stream_denials(path)]
        entry["denied"] = len(entry["denials"])
        if entry["denied"]:
            entry["why"] = " · ".join(w for w in (entry.get("why", ""), f"{entry['denied']} denied") if w)
    models = sorted({m for e in facts["stages"].values() for m in e["models"]})
    not_applied = sorted({r for e in facts["stages"].values() if e["not_applied"] for r in e["requested"]})
    front, body = data.get("front") or {}, data.get("body") or ""
    return dict(row=row, story=story_id, title=data.get("title", ""), epic=data.get("epic", ""),
                path=shown(data["path"]) if data.get("path") else "", kind=story_kind(front),
                created=created_of(front), intent=front_text(front.get("intent")),
                description=story_description(body), scenarios=scenarios_of(body),
                superseded=data.get("state") == "superseded", **story_sections(body),
                **story_situation(row, data, overview, body),
                context=str(front.get("context", "")).strip(), criteria=criteria, accepted_by=accepted_by,
                passes=passes, stages=facts["stages"], decisions=decisions, models=models, not_applied=not_applied,
                priced=facts["priced"] > 0, waiting=[w for w in overview["waiting"] if w["story"] == story_id],
                next=overview["next"])


def story_description(body):
    """What a story is about, in its own words: its `## Story` section — or, for a task, which has none, the prose
    between its title and its first section. Comments left out."""
    lines = section_of(body, "story")
    if lines is None:
        lines = []
        for line in body.splitlines():
            if line.startswith("## "):
                break
            if not line.startswith("# "):
                lines.append(line)
    text = re.sub(r"<!--.*?-->", "", "\n".join(lines), flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


#: The sections a detail shows in a block of its own instead of as text: a story's criteria (as scenarios), an
#: epic's stories (with their state). Their place among the sections is kept as an index.
STORY_OWN_BLOCK, EPIC_OWN_BLOCK = "acceptance criteria", "stories"

#: A section a detail puts first, whatever its place in the file: why a story is not built.
FIRST_SECTIONS = ("superseded",)


def sections_of(body, own_block):
    """Every `## ` section of a story's or an epic's file in the file's order, as {heading, text, kind} — the text
    as Markdown, a wrapped line kept as written, comments left out, an empty section left out. Prose between the
    title and the first section is a section without a heading. The section the detail draws as a block of its own
    (`own_block`) is not among them; `at` says where it stood (the number of sections before it, or None). A section
    of FIRST_SECTIONS moves to the front and says so in `kind` — the view draws the sections as given."""
    parts, heading, lines = [], "", []
    for line in body.splitlines() + ["## "]:
        if line.startswith("## "):
            parts.append((heading, lines))
            heading, lines = line[3:].strip(), []
        elif not line.startswith("# "):
            lines.append(line)
    sections, at = [], None
    for name, lines in parts:
        key = name.split("(")[0].strip().lower()
        if name and key == own_block:
            at = len(sections)
            continue
        text = re.sub(r"\n{3,}", "\n\n", re.sub(r"<!--.*?-->", "", "\n".join(lines), flags=re.S)).strip("\n")
        if text.strip():
            sections.append(dict(heading=name, text=textwrap.dedent(text).strip(),
                                 kind=key if name and key in FIRST_SECTIONS else ""))
    first = [s for s in sections if s["kind"]]
    if first and at is not None:
        at += sum(1 for s in sections[at:] if s["kind"])
    return [*first, *(s for s in sections if not s["kind"])], at


#: The front-matter fields an epic's head shows, by the heading of the section that may say the same: a section under
#: one of these headings whose text says nothing beyond its field is left out of the detail.
HEAD_FIELDS = {"intent": "intent", "goal": "goal", "outcome": "metric", "metric": "metric",
               "domain contact": "domain_contact", "domain": "domain_contact"}

#: The sentence the epic template writes under `## Outcome` — it says nothing beyond the outcome event the head shows.
OUTCOME_BOILERPLATE = ("The epic is measured by the outcome event `{metric}`: as long as it is not published in "
                       "production, the epic has not delivered, however much code exists.")


def said_alike(text):
    """A text as compared with a field: whitespace collapsed, a trailing period off."""
    return " ".join(text.split()).rstrip(".").strip()


def without_head(sections, front):
    """The sections the head does not already show: one whose heading names a field of HEAD_FIELDS and whose text is
    that field's value (or, for the outcome, the template's sentence about it) — compared after `said_alike` — is
    left out; a section with more to say stays. Returns the sections kept and how many were left out before `at`."""
    kept, gone = [], []
    for index, one in enumerate(sections):
        key = HEAD_FIELDS.get(one["heading"].split("(")[0].strip().lower())
        value = front_text(front.get(key)).strip() if key else ""
        same = {said_alike(value)} | ({said_alike(OUTCOME_BOILERPLATE.format(metric=value))} if key == "metric" else set())
        if value and said_alike(one["text"]) in same:
            gone.append(index)
        else:
            kept.append(one)
    return kept, gone


#: The longest a situation line quotes a reason before it cuts it.
SITUATION_REASON = 90


def first_sentence(text, limit=SITUATION_REASON):
    """The first sentence of a section's text, list marks and line breaks out, cut at `limit` with an ellipsis."""
    words = " ".join(line.strip().lstrip("-*").strip() for line in text.splitlines() if line.strip())
    sentence = re.split(r"(?<=[.!?;])\s", words, maxsplit=1)[0].rstrip(".;")
    return sentence if len(sentence) <= limit else sentence[:limit - 1].rstrip(" ,;—") + "…"


def story_situation(row, story, overview, body):
    """What is up with a story, in one line the factory decides — and which of its two views a detail opens with:
    `pipeline` while it runs or waits for a person, `story` before it starts and once it is done or set aside. A line
    that would only repeat the state the head shows is empty."""
    found = situation_of_story(row, story, overview, body)
    if said_alike(found["situation"]) == said_alike(str(row.get("state", ""))):
        found["situation"] = ""
    return found


def situation_of_story(row, story, overview, body):
    state = story.get("state", "")
    moving = next((m for m in overview["running"] if m["story"] == row["story"] and not m["interrupted"]), None)
    if moving:
        line = f"running {moving['stage']}" + (f" · {moving['part']}" if moving.get("part") else "")
        line += f" · round {moving['round']}" if (moving.get("round") or 1) > 1 else ""
        if moving.get("since"):
            line += " · " + took_text((datetime.now(timezone.utc) - moving["since"]).total_seconds())
        return dict(situation=line, view="pipeline")
    if state == "superseded":
        reason = next((s["text"] for s in sections_of(body, STORY_OWN_BLOCK)[0] if s["kind"] == "superseded"), "")
        return dict(situation="superseded" + (f" — {first_sentence(reason)}" if reason else ""), view="story")
    if row["done"]:
        return dict(situation=f"delivered {stamp_text(row['delivered'])[:10]}" if row["delivered"] else "delivered",
                    view="story")
    detail = str(story.get("detail", "")).strip()
    if state == "blocked":
        return dict(situation="blocked" + (f" — {first_sentence(detail)}" if detail else ""), view="story")
    if row["mark"] in ("look", "question", "stopped"):
        line = row["state"] + (f" — {first_sentence(detail)}" if row["mark"] == "stopped" and detail else "")
        return dict(situation=line, view="story" if state == "unreleased" else "pipeline")
    started = row["passes"] > 0 or state in ("in-progress", "resumable")
    line = row["state"] + ("" if started else " — not started")
    queue = overview.get("queue", {}).get("ready", [])
    if row["story"] in queue:
        place = queue.index(row["story"])
        line += " · next in line" if place == 0 else f" · {place + 1}. in line"
    return dict(situation=line, view="pipeline" if started else "story")


def epic_situation(epic, overview):
    """What is up with an epic beyond the progress its head shows, in one line: what is set aside, what runs, what
    waits for a person — empty when nothing does. The detail is one page: head, sections, stories."""
    ids = {r["story"] for r in epic["rows"]}
    parts = []  # how much is delivered stands in the head (its progress) — the line says only what comes beside it
    set_aside = sum(1 for r in epic["rows"] if r["state"] == "superseded")
    parts += [f"{set_aside} superseded"] if set_aside else []
    parts += [f"{m['story']} running {m['stage']}" for m in overview["running"] if m["story"] in ids and not m["interrupted"]]
    waits = sum(1 for w in overview["waiting"] if w["story"] in ids and not w.get("draft"))
    drafts = sum(1 for w in overview["waiting"] if w["story"] in ids and w.get("draft"))
    parts += [f"{waits} wait{'s' if waits == 1 else ''} for you"] if waits else []
    parts += [f"{drafts} draft{'' if drafts == 1 else 's'}"] if drafts else []
    return dict(situation=" · ".join(parts))


def story_sections(body):
    """A story's sections for its detail, its criteria's place among them, and why it is not built where it says."""
    sections, at = sections_of(body, STORY_OWN_BLOCK)
    return dict(sections=sections, criteria_at=at)


def epic_sections(body, front):
    """An epic's sections for its detail without those its head already says (`without_head`), and its stories'
    place among the ones kept."""
    sections, at = sections_of(body, EPIC_OWN_BLOCK)
    kept, gone = without_head(sections, front)
    return dict(sections=kept, stories_at=None if at is None else at - sum(1 for i in gone if i < at))


def epic_description(body, front):
    """An epic's own text beside its fields: its body without the title, without `## Stories` (the stories come with
    their state) and without a section the front matter already says — `## Intent`, `## Goal`, `## Outcome` (its
    `metric:`). Comments left out."""
    said = {"stories"} | {name for name, key in (("intent", "intent"), ("goal", "goal"), ("outcome", "metric"))
                          if front_text(front.get(key))}
    kept, skip = [], False
    for line in body.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            skip = line[3:].strip().lower() in said
        if not skip:
            kept.append(line)
    text = re.sub(r"<!--.*?-->", "", "\n".join(kept), flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def epic_model(cwd, epics, runs, epic_id, live=False):
    """One epic as a person reads it (WP-146): its fields, its own text, its stories with their state — newest
    first, as the backlog shows them — and what comes next."""
    overview = status_model(cwd, epics, runs, live)
    wanted = epic_id.lower()
    folders = {f["folder"].lower(): f["epic"] for f in epic_files(epics)}
    epic = next((e for e in overview["epics"] if e["epic"].lower() in (wanted, folders.get(wanted, "").lower())), None)
    if epic is None:
        known = ", ".join(e["epic"] for e in overview["epics"] if e["epic"]) or "none"
        raise GateError(f"no epic {epic_id} under {epics}/ — the epics: {known}")
    front, body = {}, ""
    own = next((f for f in epic_files(epics) if epic["epic"] in (f["epic"], f["folder"])), None)
    if own:
        with contextlib.suppress(GateError, OSError):
            front, body = read_front_matter(os.path.join(epics, own["folder"], EPIC_FILE))
    journey = next((j for j in overview["journeys"] if j["epic"] == epic["epic"]), None)
    return dict(epic=epic["epic"], title=epic.get("title", ""), path=epic.get("path", ""), created=epic.get("created", ""),
                intent=epic.get("intent", ""), goal=epic.get("goal", ""), metric=epic.get("metric", ""),
                domain_contact=epic.get("domain_contact", ""), discovery=epic.get("discovery", ""),
                description=epic_description(body, front), mark=epic_mark(epic), rows=epic["rows"],
                **epic_sections(body, front),
                **epic_situation(epic, overview),
                delivered=epic["delivered"], total=epic["total"], tokens=epic["tokens"], measured=epic["measured"],
                seconds=epic["seconds"], journey=journey, next=overview["next"])


def sections_text(sections, at, block, colour):
    """A story's or an epic's sections as the terminal shows them, in the order given — the block of its own (the
    criteria, the stories) where its section stood, else after them; why a story is not built painted as a wait."""
    out = []
    for index, one in enumerate(sections + [None]):
        if index == (len(sections) if at is None else at):
            out += block
        if one is None:
            break
        heading = one["heading"] or "Text"
        out += (section(paint(heading, "look", colour) if one["kind"] else heading, colour)
                + paragraph_lines(one["text"], "    "))
    return out


def sections_md(sections, at, block):
    """The same for a session: each section under its heading in bold, its Markdown as written."""
    out = []
    for index, one in enumerate(sections + [None]):
        if index == (len(sections) if at is None else at):
            out += block
        if one is None:
            break
        heading = f"**{one['heading'] or 'Text'}**"
        out += ["", f"⚠ {heading}" if one["kind"] else heading, "", one["text"]]
    return out


def paragraph_lines(text, indent):
    """Prose wrapped to the view's width, its paragraphs kept apart; a heading, a list item or a table row stands on
    its own line as written, a line wrapped under a list item joined to it."""
    out = []
    for paragraph in text.split("\n\n"):
        lines = []
        for line in paragraph.splitlines():
            if lines and line[:1].isspace() and line.strip() and not line.lstrip().startswith(("-", "*", "|", ">", "#")):
                lines[-1] += " " + line.strip()
            else:
                lines.append(line)
        if any(l.lstrip().startswith(("#", "-", "*", "|", ">")) for l in lines):
            wrapped = [w for l in lines for w in (textwrap.wrap(l.strip(), view_width(), initial_indent=indent,
                                                                subsequent_indent=indent + "  ") or [""])]
        else:
            wrapped = textwrap.wrap(" ".join(paragraph.split()), view_width(), initial_indent=indent,
                                    subsequent_indent=indent)
        out += ([""] if out else []) + wrapped
    return out


def epic_story_cells(model, marks):
    """An epic's stories as its view lists them: the story with its mark, its state, when it was delivered, its title."""
    return [[f"{marks[r['mark']]} {r['story']}", r["state"], stamp_text(r["delivered"]), r["title"]] for r in model["rows"]]


def scenario_lines(model, indent="    "):
    """A story's criteria as a person reads them: the title, then the steps, the rule they serve above them."""
    out, rule, width = [], None, view_width()
    wrap = lambda text, first, rest: textwrap.wrap(text, width, initial_indent=first, subsequent_indent=rest) or [first]
    for scenario in model["scenarios"]:
        if scenario["rule"] and scenario["rule"] != rule:
            out += [""] + wrap(f"Rule: {scenario['rule']}", indent, indent + "      ")
        rule = scenario["rule"]
        out += wrap(scenario["title"] + (" (happy path)" if scenario["happy"] else "") + f"  [{scenario['key']}]",
                    indent + "  ", indent + "    ")
        for step in scenario["steps"]:
            out += wrap(f"{step['word']} {step['text']}", indent + "    ", indent + "      ")
        if scenario["text"]:
            out += wrap(scenario["text"], indent + "    ", indent + "      ")
    return out


def render_epic_text(model, colour=False):
    title = f"{model['epic']} — {model['title']}" if model["title"] else model["epic"]
    facts = [(label, value) for label, value in (
        ("Intent", model["intent"]), ("Goal", model["goal"]), ("Outcome", model["metric"]),
        ("Domain", model["domain_contact"]), ("Discovery", model["discovery"]), ("Created", model["created"]),
        ("Stories", epic_summary(model) if model["rows"] else "no story yet"), ("File", model["path"])) if value]
    width = max(len(label) for label, _v in facts)
    out = [""] + heading(title, colour, "═") + [""]
    out += [f"  {model['situation']}", ""] if model.get("situation") else []
    out += [f"  {bold(label.ljust(width), colour)}   {value}" for label, value in facts]
    if model["rows"]:
        stories = section("Stories — newest first", colour) + table_text(
            ["story", "state", "delivered (UTC)", "title"], epic_story_cells(model, MARKS_TEXT),
            indent="    ", marks=[r["mark"] for r in model["rows"]], colour=colour)
    else:
        stories = ["", f"  no story yet — {commands('/factory-backlog stories ' + model['epic'], colour)}"]
    out += sections_text(model["sections"], model["stories_at"], stories, colour)
    if model["journey"]:
        out += ["", f"  {dim('journey', colour)}   {model['journey']['text']} — "
                    f"{commands(model['journey']['action']['skill'], colour)}"]
    return "\n".join(out + ["", "─" * 72] + next_text(model, colour) + [""])


def render_epic_md(model):
    title = f"{model['epic']} — {model['title']}" if model["title"] else model["epic"]
    out = [f"**{title}**", ""] + ([f"*{model['situation']}*", ""] if model.get("situation") else [])
    out += [f"- **{label}:** {value}" for label, value in (
        ("Intent", model["intent"]), ("Goal", model["goal"]), ("Outcome", f"`{model['metric']}`" if model["metric"] else ""),
        ("Domain contact", model["domain_contact"]), ("Discovery", model["discovery"]), ("Created", model["created"]),
        ("Stories", epic_summary(model) if model["rows"] else "no story yet"), ("File", f"`{model['path']}`" if model["path"] else ""))
        if value]
    if model["rows"]:
        stories = ["", "**Stories** — newest first", ""] + table_md(["story", "state", "delivered (UTC)", "title"],
                                                                     epic_story_cells(model, MARKS_MD))
    else:
        stories = ["", f"No story yet — `/factory-backlog stories {model['epic']}`."]
    out += sections_md(model["sections"], model["stories_at"], stories)
    if model["journey"]:
        out += ["", f"*journey* — {model['journey']['text']} → `{model['journey']['action']['skill']}`"]
    return "\n".join(out + ["", next_md(model)])


def token_cells(entry, measured):
    """The four token classes as Claude Code reports them (and ccusage shows them), and their total."""
    if not measured:
        return ["—", "—", "—", "—", "not measured"]
    return [f"{entry.get(k, 0):,}" for k in ("input", "output", "cache_write", "cache_read")] + [f"{entry['tokens']:,}"]


def stage_cells(model):
    """One row per stage and a total. A model column only where the stages ran on different models or a
    requested one did not reach a stage — otherwise the one model is named in the caption."""
    tools_used = {t for e in model["stages"].values() for t in e.get("tools", ())}
    per_stage = len(model["models"]) > 1 or bool(model["not_applied"]) or len(tools_used) > 1 \
        or any(e.get("efforts") for e in model["stages"].values())
    any_why = any(e.get("why") for e in model["stages"].values())
    rows = []
    for stage in sorted(model["stages"], key=stage_rank):
        e = model["stages"][stage]
        cells = [stage, e["runs"], took_text(e["seconds"])] + token_cells(e, e["measured"])
        if e.get("running"):
            cells[1] = f"{e['runs']} (running)"
            cells[3:3 + 5] = token_cells(e, True)
        elif e["measured"] < e["runs"]:
            cells[1] = f"{e['runs']} ({e['runs'] - e['measured']} not measured)"
        if model["priced"]:
            cells.append(f"{e['cost']:.2f}" if e["priced"] else "—")
        if per_stage:
            ran = ", ".join(sorted(e["models"])) or "—"
            if e["not_applied"]:
                ran += f" (requested {', '.join(sorted(e['requested']))}: not applied)"
            if len(tools_used) > 1 and e.get("tools"):
                ran += f" · {', '.join(sorted(e['tools']))}"
            if e.get("efforts"):
                ran += f" · effort {', '.join(sorted(e['efforts']))}"
            cells.append(ran)
        if any_why:
            cells.append(e.get("why", ""))
        rows.append(cells)
        for part in e.get("parts") or []:
            sub = [f"  · {part['stage']}", "", took_text(part["seconds"])] + token_cells(part, True)
            sub[4] = "≈" + sub[4]                     # the output column: split by what each part wrote
            if model["priced"]:
                sub.append(f"≈{part['cost']:.2f}" if part["cost"] is not None else "—")
            if per_stage:
                sub.append("")
            if any_why:
                sub.append(f"{part['denied']} denied" if part.get("denied") else "")
            rows.append(sub)
    total = {k: sum(e.get(k, 0) for e in model["stages"].values())
             for k in ("runs", "seconds", "tokens", "measured", "cost") + USAGE_FIELDS}
    streaming = any(e.get("running") for e in model["stages"].values())
    cells = ["total", total["runs"], took_text(total["seconds"])] + token_cells(total, total["measured"] or streaming)
    if model["priced"]:
        cells.append(f"{total['cost']:.2f}")
    if per_stage:
        cells.append("")
    if any_why:
        cells.append("")
    rows.append(cells)
    headers = ["stage", "runs", "worked", "input", "output", "cache write", "cache read", "total"] \
        + (["cost $"] if model["priced"] else []) + (["model"] if per_stage else []) + (["notes"] if any_why else [])
    right = {1, 2, 3, 4, 5, 6, 7} | ({8} if model["priced"] else set())
    return headers, rows, right


def story_header(model):
    """(title line, [(label, value)]): what the story is, where it stands, how often it ran."""
    row = model["row"]
    title = f"{model['story']} — {model['title']}" if model["title"] else model["story"]
    state = row["state"]
    if row["delivered"]:
        state = f"delivered {stamp_text(row['delivered'])} UTC"
    if model["accepted_by"]:
        state += " · accepted by a human"
    passes = model["passes"]
    corrections = sum(1 for p in passes[1:] if p["label"].startswith("correction"))
    again = len(passes) - 1 - corrections
    why = []
    if corrections:
        why.append("one correction" if corrections == 1 else f"{corrections} corrections")
    if again:
        why.append("planned again once" if again == 1 else f"planned again {again} times")
    pass_text = ("no journal — delivered before the pipeline measured"
                 if not model["row"].get("journal", True) and model["row"]["mark"] == "done"
                 else "not run yet") if not passes else "1 pass — the first delivery" if len(passes) == 1 else \
        f"{len(passes)} passes — the first delivery, then " + " and ".join(why)
    facts = [("Epic", model["epic"] or "—")]
    if model["context"]:
        facts.append(("Context", model["context"]))
    facts += [("Criteria", str(model["criteria"])), ("State", state), ("History", pass_text)]
    if row.get("flaky"):
        facts.append(("Flaky", ", ".join(row["flaky"]) + " — red in a whole suite, green on its own run; no round"))
    return title, facts


def stage_caption(model):
    caption = "Stages"
    parts = []
    if len(model["models"]) == 1 and not model["not_applied"]:
        parts.append(model["models"][0])
    if model["not_applied"]:
        parts.append(f"requested {', '.join(model['not_applied'])}: not applied")
    if not model["priced"] and any(e["measured"] for e in model["stages"].values()):
        parts.append("no price in a session log")
    return caption + (" — " + " · ".join(parts) if parts else "")


def render_story_text(model, colour=False):
    row = model["row"]
    title, facts = story_header(model)
    width = max(len(label) for label, _v in facts)
    out = [""] + heading(title, colour, "═") + [""]
    if model.get("situation"):
        out += [f"  {paint(model['situation'], row['mark'], colour)}", ""]
    for label, value in facts:
        if label == "State":
            value = paint(f"{MARKS_TEXT[row['mark']]} {value}", row["mark"], colour)
        out.append(f"  {bold(label.ljust(width), colour)}   {value}")
    for w in model["waiting"]:
        out += ["", "  " + paint(f"{MARKS_TEXT[w['mark']]} {w['what']}", w["mark"], colour)]
        out += how_lines(w["action"], colour, "      ")
    criteria = (section("Criteria", colour) + scenario_lines(model)[1 if model["scenarios"][0]["rule"] else 0:]
                if model.get("scenarios") else [])
    if "sections" in model:
        out += sections_text(model["sections"], model["criteria_at"], criteria, colour)
    else:
        out += (section("Story", colour) + paragraph_lines(model["description"], "    ")
                if model.get("description") else []) + criteria
    if model["passes"]:
        out += section("Passes", colour)
        out += table_text(["pass", "started (UTC)", "ended (UTC)", "worked", "waited before", "tokens"],
                          [[f"{i + 1}  {p['label']}", stamp_text(p["start"]), stamp_text(p["end"]),
                            took_text(p["seconds"]), took_text(p["waited"]), tokens_text(p["tokens"], p["measured"])]
                           for i, p in enumerate(model["passes"])], {3, 4, 5}, colour=colour, first_bold=True)
    if model["stages"]:
        headers, rows, right = stage_cells(model)
        out += section(stage_caption(model), colour) + table_text(headers, rows, right, total=True, colour=colour,
                                                                    first_bold=True)
    denials = denial_rows(model)
    if denials:
        out += section("Denied — calls the tool refused without asking, each a turn spent", colour)
        out += table_text(["stage", "tool", "call"], denials, colour=colour, first_bold=True)
    if model["decisions"]:
        out += section("Decisions", colour)
        out += table_text(["record", "state", "answer or question"],
                          [[d["id"], d["state"], d["text"]] for d in model["decisions"]], colour=colour,
                          marks=[decision_mark(d) for d in model["decisions"]], first_bold=True)
    out += ["", "─" * 72] + next_text(model, colour) + [""]
    return "\n".join(out)


def denial_rows(model):
    """[stage, tool, call] for every call a stage was denied — a shared process's named with its stage inside."""
    return [[f"{stage} · {d['stage']}" if d["stage"] and d["stage"] != stage else stage, d["tool"], d["command"]]
            for stage in sorted(model["stages"], key=stage_rank) for d in model["stages"][stage].get("denials") or []]


def render_story_md(model):
    title, facts = story_header(model)
    out = [f"**{title}**", ""] + ([f"*{model['situation']}*", ""] if model.get("situation") else [])
    out += [f"- **{label}:** " + (f"{MARKS_MD[model['row']['mark']]} " if label == "State" else "") + value
            for label, value in facts]
    for w in model["waiting"]:
        out += ["", f"{MARKS_MD[w['mark']]} **{w['what']}** — {how_md(w['action'])}"]
    criteria = []
    if model.get("scenarios"):
        criteria += ["", "**Criteria**"]
        rule = None
        for scenario in model["scenarios"]:
            if scenario["rule"] and scenario["rule"] != rule:
                criteria += ["", f"*Rule: {scenario['rule']}*"]
            rule = scenario["rule"]
            criteria += ["", f"- **{scenario['title']}**" + (" (happy path)" if scenario["happy"] else "") + f" `{scenario['key']}`"]
            criteria += [f"  - {step['word']} {step['text']}" for step in scenario["steps"]]
            if scenario["text"]:
                criteria.append(f"  - {scenario['text']}")
    out += sections_md(model["sections"], model["criteria_at"], criteria)
    if model["passes"]:
        out += ["", "**Passes**", ""]
        out += table_md(["pass", "started (UTC)", "ended (UTC)", "worked", "waited before", "tokens"],
                        [[f"{i + 1} {p['label']}", stamp_text(p["start"]), stamp_text(p["end"]),
                          took_text(p["seconds"]), took_text(p["waited"]), tokens_text(p["tokens"], p["measured"])]
                         for i, p in enumerate(model["passes"])], {3, 4, 5}, first_bold=True)
    if model["stages"]:
        headers, rows, right = stage_cells(model)
        rows = rows[:-1] + [[f"**{c}**" if str(c) else c for c in rows[-1]]]
        out += ["", f"**{stage_caption(model)}**", ""] + table_md(headers, rows, right, first_bold=True)
    denials = denial_rows(model)
    if denials:
        out += ["", "**Denied** — calls the tool refused without asking, each a turn spent", ""]
        out += table_md(["stage", "tool", "call"], [[a, b, f"`{c}`"] for a, b, c in denials], first_bold=True)
    if model["decisions"]:
        out += ["", "**Decisions**", ""]
        out += table_md(["", "record", "state", "answer or question"],
                        [[MARKS_MD[decision_mark(d)], f"**{d['id']}**", d["state"], d["text"]] for d in model["decisions"]])
    out += ["", next_md(model)]
    return "\n".join(out)


def json_ready(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return value


def use_colour(choice):
    if choice == "always":
        return True
    if choice == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def checkout_holders(cwd, epics, runs, exclude=None):
    """The stories with unfinished code in the checkout — past their test stage, not delivered — as
    the schedule counts them."""
    holders = []
    for path in story_files(epics):
        try:
            front, _body = read_front_matter(path)
        except GateError:
            continue
        story_id = story_id_of(path, front)
        if story_id == exclude or not os.path.isfile(os.path.join(runs, story_id, STAGE_FILES["test"])):
            continue
        if story_state(cwd, runs, story_id, front, path)[0] not in ("delivered", "superseded"):
            holders.append(story_id)
    return sorted(holders)


def reopen(cwd, runs, epics, story_id):
    """Take a delivered story back for a correction a human gave on looking at it.

    Only with an answered acceptance record the story cites — the answer is in the story, not in a
    prompt. Before a story was accepted every answer is a correction; after an acceptance, one that
    changes or takes back a criterion is a new wish, and that is a new story, not this one."""
    story_path = find_story(epics, story_id)
    front, _body = read_front_matter(story_path)
    if not is_delivered(front):
        print(f"reopen: {story_id} is not delivered — a correction before delivery goes into the story, "
              f"and the schedule runs it from plan")
        return 1
    records = acceptance_records(cwd, story_id, story_path)
    if not records or records[-1][2] not in ("answered", "applied") or accepted(records[-1][3]):
        print(f"reopen: {story_id} has no answered correction — /factory-decisions records the human's "
              f"correction as an acceptance record first")
        return 1
    rid = records[-1][0]
    holders = checkout_holders(cwd, epics, runs, exclude=story_id)
    if holders:
        print(f"reopen: {', '.join(holders)} holds the checkout with unfinished code — one story at a time; "
              f"reopen {story_id} once it is delivered")
        return 1
    text = read_text(story_path)
    if rid not in text:
        print(f"reopen: the story does not cite {rid} — write the correction into it first (criteria and "
              f"an `answered:` line naming {rid})")
        return 1
    # After an acceptance, the criteria as accepted are the record's list: a correction that changes one of
    # them is a new wish.
    earlier = [record for record in records[:-1] if accepted(record[3])]
    if earlier:
        before = dict(accepted_criteria(earlier[-1][4]))
        now = dict(criteria_of(story_path, read_front_matter(story_path)[1]))
        changed = sorted(key for key, value in before.items() if now.get(key) != value)
        if changed:
            print(f"reopen: after its acceptance the correction changes {', '.join(changed)} — that is a new "
                  f"wish: a new story with `## Changed expectations`, not this one reopened")
            return 1
    kept = keep_pass(os.path.join(runs, story_id))
    write_story_fields(story_path, status="approved", delivered=None, delivered_by=None)
    print(f"reopen: {story_id} taken back for {rid} — it runs again from plan; the delivered pass is kept as "
          f"{shown(kept) if kept else 'nothing (no run folder)'}, and the story no longer says delivered")
    return 0


def deliver_by_hand(cwd, runs, epics, story_id, who, force=False):
    """A story a person built: `status: delivered`, `delivered:` (UTC), `delivered_by: hand:<who>`. Works where the
    factory never ran. The delivery is claimed, not proven — `--prove` checks it later through the adopt path. A
    delivered story is not delivered a second time: a change of delivered behaviour is a new story."""
    who = " ".join(str(who or "").split())
    if not who:
        print("deliver-by-hand: `--by <who>` names the person who delivers — the line is their claim")
        return 1
    story_path = find_story(epics, story_id)
    front, _body = read_front_matter(story_path)
    if is_delivered(front):
        print(f"deliver-by-hand: {story_id} is delivered already ({delivered_by(front) or 'before delivered_by'}) — "
              f"a change of its behaviour is a new story with `## Changed expectations`")
        return 1
    status = str(front.get("status", "")).strip().lower()
    if status == "superseded":
        print(f"deliver-by-hand: {story_id} is superseded — nothing to deliver")
        return 1
    config = claim_config_here(cwd)
    if config:
        refresh_claims(cwd, runs, config, claim_target(cwd), say=lambda _line: None)
        held = cached_claims(runs).get(story_id)
        if held and not held["own"]:
            if not force:
                print(f"deliver-by-hand: {story_id} is claimed by {held['who']} ({held['host']}) since {held['since']} — "
                      f"another factory builds it; `--force` delivers it anyway")
                return 1
            with contextlib.suppress(OSError):
                journal_append(runs, story_id, "note", "deliver-by-hand", f"over-claim={held['who']}", "forced=1")
    # The spec takes the story's new criteria, without test lines — unproven until `--prove`. A story that changes or
    # removes what holds needs a plan to derive its delta: that is `--prove`'s adopt path, not this helper.
    _front, body = read_front_matter(story_path)
    target, spec, _features, feature = story_spec(front)
    preamble = read_spec(target)[0] if target else []
    own = [item for item in spec if item["feature"] == feature] if story_kind(front) != "journey" else spec
    story = story_entries(body) if target else []
    elsewhere = {item["key"] for item in spec if item["feature"] != feature}
    changing = [key for key, verb in derived(story, spec).items() if verb == "changes"] \
        + sorted(item["key"] for item in story if item["key"] in elsewhere)
    if changing:
        print(f"deliver-by-hand: {story_id} changes what holds ({', '.join(changing)} in {shown(target)}) — the delta of a "
              f"change is planned: `factory-cli.py --prove {story_id}` once it is delivered, or run it through the factory")
        return 1
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_story_fields(story_path, status="delivered", delivered=stamp, delivered_by=f"hand:{who}")
    added = [item for item in story if item["key"] not in {s["key"] for s in spec}]
    if added:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(render_spec(preamble, merge(own, story, read_delta(""), {}), str(front.get("context", "")).strip()
                                     or "Spec"))
        print(f"deliver-by-hand: {len(added)} criterion(s) into {shown(target)}, without a test line — unproven until "
              f"`--prove`")
    print(f"deliver-by-hand: {shown(story_path)} carries `status: delivered`, `delivered: {stamp}`, "
          f"`delivered_by: hand:{who}` — delivered, claimed. Commit it with the trailer `Story: {story_id}`; "
          f"`factory-cli.py --prove {story_id}` turns the claim into proof.")
    return 0


def claim_target(cwd):
    """The branch the main checkout is on — the remote's branch of that name is the shared main line."""
    return git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip() or "main"


def claim_command(cwd, runs, epics, story_id):
    """`--claim-story`: claim one story on the remote (WP-93). 0 claimed or own, 3 another factory has it, 4 needs a
    person; 0 and nothing pushed where the profile names no `claim_remote:`."""
    config = claim_config_here(cwd)
    if not config:
        return 0
    path = find_story(epics, story_id)
    front, body = read_front_matter(path)
    epic = str(front.get("epic") or os.path.basename(epic_folder(path))).strip()
    title = story_title(front, body) or story_id
    code = claim_story(cwd, runs, config, claim_target(cwd), story_id, epic, title)
    if code == 3:
        with contextlib.suppress(OSError):
            held = cached_claims(runs).get(story_id, {})
            journal_append(runs, story_id, "note", "claimed-elsewhere", f"by={held.get('who', '?')}",
                           f"since={held.get('since', '?')}")
    return code


def undeliver_branch(cwd, runs, epics, story_id):
    """WP-93 F: a published branch whose merge request lost the race goes back to before its delivery — the spec's
    scenarios and journeys as the remote main line has them, the story's state lines out and its status as before —
    so the integrate step merges the remote main line and the delivering function merges again under the new rules.
    The spec is never resolved by text."""
    config = claim_config_here(cwd)
    if not config or not has_worktree(story_id, cwd):
        print(f"integrate: {story_id} has no published branch in this checkout")
        return 1
    path = worktree_of(story_id, cwd)
    fetch_remote(cwd, config["remote"])
    main = remote_main(config["remote"], claim_target(cwd))
    spec_rel = os.path.relpath(place("spec") if os.path.isabs(place("spec")) else os.path.join(cwd, place("spec")), cwd)
    changed = [p for p in git(path, "diff", "--name-only", f"{main}...HEAD", "--", spec_rel)[1].splitlines()
               if p.endswith(("scenarios.md", "journeys.md"))]
    for rel in changed:
        if git(path, "cat-file", "-e", f"{main}:{rel}")[0] == 0:
            git(path, "checkout", main, "--", rel)
        else:
            git(path, "rm", "--quiet", "--", rel)
    story_rel = os.path.relpath(find_story(epics, story_id), factory_home() or cwd)
    local_story = os.path.join(path, story_rel)
    before = os.path.join(evidence_dir(runs, story_id), "published-status")
    status = read_text(before).strip() if os.path.isfile(before) else "approved"
    write_story_fields(local_story, status=status or "approved", delivered=None, delivered_by=None)
    git(path, "add", "-A", "--", *(changed + [story_rel]))
    git(path, *(["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]
                if not git(path, "config", "user.email")[1].strip() else []),
        "commit", "--no-verify", "--quiet", "-m", f"wip({story_id}): before it is delivered again")
    with contextlib.suppress(OSError):
        os.remove(os.path.join(evidence_dir(runs, story_id), PUBLISHED))
    print(f"integrate: {story_id}'s delivery taken back on its branch ({len(changed)} spec file(s) as {main} has them) "
          f"— the integrate step merges {main} and delivers it again")
    return 0


def spec_delta_view(runs, epics, story_id):
    """What holds before and after the story (WP-105): per key of the delta, its verb, the feature it stands under
    before and after, the criterion's lines before and after — what a person accepting the story looks at, read from
    the story, its plan and the spec, never parsed by a skill. `adds feature` names a feature the story brings."""
    story_path = find_story(epics, story_id)
    front, body = read_front_matter(story_path)
    target, held, _features, feature = story_spec(front)
    if not target:
        return dict(story=story_id, context="", feature="", features=[], renames=[], rows=[])
    plan = os.path.join(runs, story_id, "plan.md")
    delta = read_delta(read_text(plan)) if os.path.isfile(plan) else read_delta("")
    story = story_entries(body)
    before = {item["key"]: item for item in held}
    rows = []
    for key, verb in derived(story, held).items():
        after = next(item for item in story if item["key"] == key)
        old = before.get(key)
        rows.append(dict(key=key, verb="moves" if key in delta["moves"] and verb == "holds" else verb,
                         before_feature=old["feature"] if old else None, after_feature=feature,
                         before=old["lines"] if old else [], after=after["lines"], reason=""))
    for key, reason in sorted(delta["removes"].items()):
        old = before.get(key)
        rows.append(dict(key=key, verb="removes", before_feature=old["feature"] if old else None, after_feature=None,
                         before=old["lines"] if old else [], after=[], reason=reason))
    renames = [dict(old=old, new=new, follow=renamed_rules(story, held, delta).get(old, []))
               for old, new in delta["renames"]]
    return dict(story=story_id, context=str(front.get("context", "")).strip(), feature=feature,
                features=sorted(delta["features"]), renames=renames, rows=rows)


def print_spec_delta(view, fmt):
    if fmt == "json":
        print(json.dumps(view, indent=2))
        return 0
    where = lambda f: f if f else "the context" if f == "" else "—"
    print(f"spec delta of {view['story']} — {view['context'] or 'no context'}"
          + (f", feature {view['feature']}" if view["feature"] else ""))
    for name in view["features"]:
        print(f"  new feature: {name}")
    for rename in view.get("renames", []):
        print(f'  rule "{rename["old"]}" → "{rename["new"]}"'
              + (f" — {', '.join(rename['follow'])} follow it" if rename["follow"] else ""))
    for row in view["rows"]:
        if row["verb"] == "holds":
            continue
        head = f"  {row['verb']} {row['key']}"
        if row["verb"] == "moves" or (row["before_feature"] is not None and row["after_feature"] is not None
                                       and row["before_feature"] != row["after_feature"]):
            head += f" ({where(row['before_feature'])} → {where(row['after_feature'])})"
        print(head + (f" — {row['reason']}" if row["reason"] else ""))
        for line in row["before"]:
            print(f"    - {line}")
        for line in row["after"]:
            print(f"    + {line}")
    held = sum(1 for row in view["rows"] if row["verb"] == "holds")
    if held:
        print(f"  {held} criterion(s) hold as they are")
    return 0


def spec_place(front):
    """What a key is unique in: the story's context (every feature of it), or the journeys."""
    return "journeys" if story_kind(front) == "journey" else str(front.get("context", "")).strip().lower()


def spec_check(cwd, runs, epics):
    """Story and spec agree (WP-98), in one direction: every criterion of a delivered story that is still there stands
    in its spec — unless a later delivered story's plan removed it. Whether a scenario came from a story is not asked:
    a delivered story may be gone. Prints one line per disagreement; exit 1 when there is one."""
    delivered = []
    for story_path in story_files(epics):
        try:
            front, body = read_front_matter(story_path)
        except GateError:
            continue
        if is_delivered(front) and spec_target(front):
            delivered.append((delivered_on(front), story_id_of(story_path), front, body))
    removed, problems = {}, []
    for when, story_id, front, _body in delivered:
        plan = os.path.join(runs, story_id, "plan.md")
        if os.path.isfile(plan):
            for key in read_delta(read_text(plan))["removes"]:
                removed.setdefault((spec_place(front), key), []).append(when)
    for when, story_id, front, body in sorted(delivered):
        target, spec, _features, _feature = story_spec(front)
        held = {item["key"] for item in spec}
        for item in story_entries(body):
            later = [w for w in removed.get((spec_place(front), item["key"]), []) if w >= when]
            if item["key"] not in held and not later:
                problems.append(f"{story_id}: `{item['key']}` is delivered and not in {shown(target)}")
    # the shape of every context's spec (WP-105): what a delivery checks before it writes, over what stands now
    spec_root = place("spec")
    for name in sorted(os.listdir(spec_root)) if os.path.isdir(spec_root) else []:
        if os.path.isdir(os.path.join(spec_root, name)):
            problems += lint_context(name)
    for line in problems:
        print(f"spec: {line}")
    if not problems:
        print(f"spec: every criterion of the {len(delivered)} delivered stor{'y' if len(delivered) == 1 else 'ies'} "
              f"stands in its spec, and every spec file holds its shape")
    return 1 if problems else 0


#: Where `--prove` keeps the claim it took out of the story: one line in the story's evidence.
CLAIM_FILE = "claim"


def prove(cwd, runs, epics, story_id):
    """A claimed delivery checked through the adopt path: the story becomes `status: adopted` — the code exists,
    check it, build nothing — and loses its delivered lines (`delivered_on` would keep it delivered and
    unscheduled). The claim is kept as one line of the evidence. The adopt gate then maps every criterion to a
    green test, proves the tests the adoption writes with a break, has a fresh judge read them, and writes
    `status: delivered`, `delivered_by: gate`. Not the way to deliver an edit: a change is a new story."""
    story_path = find_story(epics, story_id)
    front, _body = read_front_matter(story_path)
    if not is_delivered(front):
        print(f"prove: {story_id} is not delivered — `--prove` checks a claimed delivery; an open story runs as it is")
        return 1
    by = delivered_by(front)
    if by == "gate" and gate_passed_on_record(cwd, runs, story_id, story_path):
        print(f"prove: {story_id} is delivered by the gate with its pass on record — nothing to prove")
        return 1
    holders = checkout_holders(cwd, epics, runs, exclude=story_id)
    if holders:
        print(f"prove: {', '.join(holders)} holds the checkout with unfinished code — one story at a time; "
              f"prove {story_id} once it is delivered")
        return 1
    evidence = evidence_dir(runs, story_id)
    os.makedirs(evidence, exist_ok=True)
    with open(os.path.join(evidence, CLAIM_FILE), "a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\tdelivered_by={by or 'unknown'}"
                     f"\tdelivered={delivered_on(front)}\n")
    kept = keep_pass(os.path.join(runs, story_id))
    write_story_fields(story_path, status="adopted", delivered=None, delivered_by=None)
    print(f"prove: {story_id} is `status: adopted` — the adopt path checks it (`factory.sh run --story {story_id}`); "
          f"the claim ({by or 'unknown'}) is kept in {shown(os.path.join(evidence, CLAIM_FILE))}"
          + (f", the earlier pass as {shown(kept)}" if kept else ""))
    return 0


def keep_pass(folder):
    """Before a story runs again from plan: its hand-overs and refusals, and the marks of the pass (`PASS_MARKS`, the
    base tree the pass's diff was taken against among them), go to `<evidence>/<story>/pass-<n>/` — the next pass
    records its own. The journal and the tree snapshots stay where they are; the history continues. Returns the
    folder, or None without a run folder."""
    if not os.path.isdir(folder):
        return None
    folder = os.path.normpath(folder)
    evidence = evidence_dir(os.path.dirname(folder), os.path.basename(folder))
    os.makedirs(evidence, exist_ok=True)
    number = 1 + sum(1 for name in os.listdir(evidence) if name.startswith("pass-"))
    target = os.path.join(evidence, f"pass-{number}")
    os.makedirs(target)
    for name in sorted(os.listdir(folder)):
        os.replace(os.path.join(folder, name), os.path.join(target, name))
    for name in PASS_MARKS:
        if os.path.isfile(os.path.join(evidence, name)):
            os.replace(os.path.join(evidence, name), os.path.join(target, name))
    return target


# --- the carriers the profile names ------------------------------------------------------

CARRIER_KEY = re.compile(r"^(carrier\.[a-z]+|review\.[a-z-]+|knowledge)$")


def carrier_lines(profile):
    return [(key, first_word(value)) for key, value in profile.items() if CARRIER_KEY.match(key) and first_word(value)]


def carriers(profile):
    """The skill names, without a `plugin:` prefix, sorted and unique."""
    return sorted({value.rsplit(":", 1)[-1] for _, value in carrier_lines(profile)})


def follow_render(event, denied=frozenset()):
    """The lines one common event stands for — [] for an event that shows nothing. `denied` holds the ids of the
    calls the stream's result names as denied permission: known once the process ended, so a running one shows such
    a call as any failed call, by the reason the tool gave. One rendering for every tool: the readers turn each
    format into the same events."""
    kind = event.get("kind")
    if kind == "session":
        return [f"· session started{(' — ' + event['model']) if event.get('model') else ''}"]
    if kind == "call":
        given = event.get("input") or {}
        lines = []
        stage = part_of_call(event)
        if stage:
            lines.append(f"── {stage}")                             # a shared process begins this stage
            if event.get("name") == "Skill":
                return lines
        arg = next((given[k] for k in FOLLOW_ARGS if isinstance(given, dict) and given.get(k)), "")
        return lines + [f"▸ {event.get('name', 'tool')} {_short(arg, 100)}".rstrip()]
    if kind == "error":
        said = " — ".join([line.strip() for line in str(event.get("text") or "").splitlines() if line.strip()][:2]) \
            or "failed"
        return [f"✗ {'denied: ' if event.get('id') in denied else ''}{_short(said, 120)}"]
    if kind == "text" and str(event.get("text", "")).strip():
        return [f"  {_short(event['text'])}"]
    if kind == "result":
        bits = [f"{event['turns']} turns" if event.get("turns") is not None else "",
                f"${float(event['cost']):.2f}" if event.get("cost") is not None else "",
                f"{int(event['duration_ms']) // 1000}s" if event.get("duration_ms") else "",
                f"{len(event['denied'])} denied" if event.get("denied") else ""]
        state = "stopped: " + event["failed"] if event.get("failed") else "done"
        return [f"■ {state}" + (" — " + ", ".join(b for b in bits if b) if any(bits) else "")]
    return []


def follow_lines(text, fmt=None):
    events = reader_of(text, fmt).events(text)
    ended = any(e["kind"] == "result" for e in events)
    denied = {call_id for e in events if e["kind"] == "result" for call_id, _n, _i in e.get("denied") or []}
    lines = []
    for event in events:
        lines += follow_render(event, denied)
    return lines, ended


def follow_outputs(runs, story, process=None):
    """[(stage, path)] of one story's stage outputs in the order they began, or of one process (`builder`,
    `review-ddd`, `plan`, …) alone."""
    pattern = os.path.join(evidence_dir(runs, story), f"{process}.*.out" if process else "*.out")
    outs = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    return [(os.path.basename(p).split(".")[0], p) for p in sorted(outs, key=lambda p: (os.path.getmtime(p), p))]


def follow_newest(runs, story=None, process=None):
    """(story, stage, path) of the newest stage output, of one story or of every story — None if none."""
    pattern = os.path.join(evidence_dir(runs, story or "*"), f"{process}.*.out" if process else "*.out")
    outs = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    if not outs:
        return None
    path = max(outs, key=lambda p: (os.path.getmtime(p), p))
    return (os.path.basename(os.path.dirname(path)),
            os.path.basename(path).split(".")[0], path)


def follow(runs, story, once, fmt, width, process=None, every=False):
    if every:
        if not story:
            print("factory: follow --all names a story (--story <id>)", file=sys.stderr)
            return 2
        shown = []
        for stage, path in follow_outputs(runs, story, process):
            lines, ended = follow_lines(open(path, encoding="utf-8", errors="replace").read())
            shown.append(dict(stage=stage, file=os.path.relpath(path), running=not ended, lines=lines))
        if fmt == "json":
            print(json.dumps({"story": story, "processes": shown}, ensure_ascii=False))
        else:
            if not shown:
                print(f"factory: no stage output yet for {story}")
            for entry in shown:
                print(f"══ {story} · {entry['stage']}{'' if not entry['running'] else ' (running)'}")
                for line in entry["lines"]:
                    print(line)
                print()
        return 0
    found = follow_newest(runs, story, process)
    if once:
        if not found:
            if fmt == "json":
                print(json.dumps({"story": story or "", "stage": "", "file": "", "running": False, "lines": []}))
            else:
                print("factory: no stage output yet" + (f" for {story}" if story else ""))
            return 0
        name, stage, path = found
        lines, ended = follow_lines(open(path, encoding="utf-8", errors="replace").read())
        lines = lines[-width:] if width > 0 else lines
        if fmt == "json":
            print(json.dumps({"story": name, "stage": stage, "file": os.path.relpath(path),
                              "running": not ended, "lines": lines}, ensure_ascii=False))
        else:
            print(f"══ {name} · {stage}{'' if ended else ' (running)'}")
            for line in lines:
                print(line)
        return 0
    current, offset, pending = None, 0, ""
    try:
        while True:
            found = follow_newest(runs, story, process)
            if found and found[2] != current:
                name, stage, current = found
                offset, pending = 0, ""
                print(f"══ {name} · {stage}", flush=True)
            if current:
                try:
                    with open(current, encoding="utf-8", errors="replace") as handle:
                        handle.seek(offset)
                        chunk = handle.read()
                        offset = handle.tell()
                except OSError:
                    chunk = ""
                if chunk:
                    pending += chunk
                    complete, _, pending = pending.rpartition("\n")
                    for line in follow_lines(complete)[0]:
                        print(line, flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


def main(argv):
    if argv[:1] == ["--run"]:                    # `factory.sh run` once its checks passed: the runner itself
        return run_main(argv[1:])
    parser = argparse.ArgumentParser(add_help=True, description="factory cli")
    parser.add_argument("--version", action="version", version=f"factory-cli {VERSION} (file contract {CONTRACT})")
    parser.add_argument("--story")
    parser.add_argument("--discover-list", action="store_true",
                        help="every discovery topic, its proposed epics (and which are epics) and its proposed description changes")
    parser.add_argument("--follow", action="store_true",
                        help="print what the stage in flight does, one line per tool call, as it happens (--once: the last lines and exit)")
    parser.add_argument("--once", action="store_true", help="with --follow: print the newest output's last lines and exit")
    parser.add_argument("--process", help="with --follow: only that process's output — builder, verifier, review-ddd, plan, …")
    parser.add_argument("--all", dest="every", action="store_true",
                        help="with --follow --story: every process of the story, in the order they began, and exit; "
                             "with --stages: every row of the table, the steps after the run order too; "
                             "with --status: every story by epic, with times and tokens, instead of the short view")
    parser.add_argument("--epic", help="with --status: one epic — its fields, its text, its stories with their state")
    parser.add_argument("--backfill-created", action="store_true",
                        help="write `created:` into every story and epic without one, from the commit that added the "
                             "file — once, never over a value there (`factory.sh update` runs it)")
    parser.add_argument("--lines", type=int, default=30, help="with --follow --once: how many lines (0: all)")
    parser.add_argument("--list-decisions", action="store_true",
                        help="print the decision inbox (all stories, or --story's) and exit")
    parser.add_argument("--claim", metavar="OWNER", help="take the checkout for one worker (exit 3: held by another)")
    parser.add_argument("--release", nargs="?", const="", metavar="OWNER",
                        help="give the checkout back (default: this session's claim)")
    parser.add_argument("--listening", action="store_true",
                        help="record that this session looked at the backlog (a listening loop's sign of life)")
    parser.add_argument("--status", action="store_true",
                        help="print what runs, what waits for a human and what comes next (--all: every story's state and the cost)")
    parser.add_argument("--brief", action="store_true", help="with --status: two lines, for a session's start")
    parser.add_argument("--format", choices=("text", "md", "json"), default="text",
                        help="with --status: aligned text for a terminal, Markdown for a session, JSON for tools")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                        help="with --status: colour on a terminal (auto), always (a screenshot) or never")
    parser.add_argument("--part", choices=("all", "backlog"), default="all",
                        help="with --status: the whole view, or only the backlog, its tokens and what comes next")
    parser.add_argument("--live", action="store_true",
                        help="with --status: add what depends on the clock — how long ago, the activity, the worker")
    parser.add_argument("--session-start", action="store_true",
                        help="with --status --brief: add what a session should do with them (the SessionStart hook)")
    parser.add_argument("--help-view", action="store_true",
                        help="print the factory explained: the flow and where the project stands, the commands, "
                             "the marks, the files (with --format, --color)")
    parser.add_argument("--usage", action="store_true",
                        help="print the tokens each story and stage used, from the runner's journals")
    parser.add_argument("--total", action="store_true", help="with --usage: print only the token total")
    parser.add_argument("--usage-from", nargs=2, metavar=("FORMAT", "FILE"),
                        help="read one invocation's usage from a tool's raw output (claude-json, codex-jsonl, opencode-json)")
    parser.add_argument("--usage-model", help="with --usage-from: the model, where the output does not name it")
    parser.add_argument("--window-start", metavar="WORK", help="with --story: start measuring work on the story "
                                                              "outside a stage — backlog or decisions")
    parser.add_argument("--window-end", metavar="WORK", help="with --story: end that measuring window")
    parser.add_argument("--stage-start", metavar="STAGE", help="mark a stage's start inside a session (with --story)")
    parser.add_argument("--refusals", action="store_true",
                        help="every story's gate refusals from its journal, form against substance (or --story)")
    parser.add_argument("--journal-line", metavar="STORY",
                        help="append the lines on stdin (<time>\\t<kind>\\t<name>\\t…) to the story's journal, numbered")
    parser.add_argument("--owned-confirm", metavar="STORY",
                        help="a person looked at the story and its answers after a stage changed them: the story runs on")
    parser.add_argument("--stage-end", metavar="STAGE",
                        help="mark its end and record what it used, read from the session's own log")
    parser.add_argument("--session-log", help="with --stage-end: the session log to read, where it is not found")
    parser.add_argument("--deliver-by-hand", metavar="STORY",
                        help="mark a story a person built as delivered by hand (claimed), and exit; needs --by")
    parser.add_argument("--by", metavar="WHO", help="with --deliver-by-hand: who delivers")
    parser.add_argument("--claim-story", metavar="STORY",
                        help="claim a story on the profile's `claim_remote:` (exit 3: another factory has it, 4: a person looks)")
    parser.add_argument("--claims-refresh", action="store_true",
                        help="fetch the claims of the profile's `claim_remote:`, release the delivered ones, and exit")
    parser.add_argument("--release-claim", metavar="STORY", help="delete this factory's claim on a story; --force for another's")
    parser.add_argument("--force", action="store_true",
                        help="with --release-claim: another factory's claim; with --deliver-by-hand: over another's claim")
    parser.add_argument("--free-id", metavar="PREFIX", help="the next story id `<PREFIX>-<n>` no factory uses")
    parser.add_argument("--undeliver-branch", metavar="STORY",
                        help="take a published story's delivery back on its branch, before it is integrated again")
    parser.add_argument("--spec-delta", metavar="STORY",
                        help="what holds before and after the story — per key its verb, feature and lines (--format json)")
    parser.add_argument("--spec-check", action="store_true",
                        help="whether every criterion of a delivered story stands in its spec (exit 1 when one does not)")
    parser.add_argument("--prove", metavar="STORY",
                        help="take a claimed delivery back to `status: adopted`, so the adopt path checks it, and exit")
    parser.add_argument("--reopen", metavar="STORY",
                        help="take a delivered story back for a human's correction (an answered acceptance "
                             "record the story cites), and exit")
    parser.add_argument("--kind", action="store_true",
                        help="with --story: print `story`, `journey` or `adopt` — the stages it runs — and exit")
    parser.add_argument("--resolve", metavar="ARGUMENT",
                        help="what /factory-run <argument> means: `story <id>`, `wish`, `backlog`, or `unknown <word>` "
                             "(exit 2), and exit")
    parser.add_argument("--start", action="store_true",
                        help="with --story: the story's state and the stage a run without --from begins at, and exit")
    parser.add_argument("--schedule", action="store_true",
                        help="print every story's state and the next one to run, and exit")
    parser.add_argument("--get", metavar="KEY", help="the profile's value for KEY, or nothing")
    parser.add_argument("--command-heads", action="store_true",
                        help="the first word of every command the profile declares, one per line")
    parser.add_argument("--findings", action="store_true",
                        help="the judge's confirmed findings that did not block, open ones first, from <story>/findings.md")
    parser.add_argument("--perspectives", action="store_true",
                        help="the judge's perspectives with their carriers, one `<name>\t<carrier>` per line")
    parser.add_argument("--carriers", action="store_true",
                        help="the skills the profile names as carrier, reviewer or knowledge, one per line")
    parser.add_argument("--carrier-lines", action="store_true", help="those keys with their values, `key value` per line")
    parser.add_argument("--model", nargs=2, metavar=("TOOL", "STAGE"),
                        help="the profile's model for that tool and stage (model.<tool>.<stage>, else model.<tool>)")
    parser.add_argument("--verdict", metavar="STORY", help="the judge's verdict of that story, or nothing")
    parser.add_argument("--back-to", metavar="STORY",
                        help="where a changes-requested verdict sends the story: test (the judge's `back: test`) or build; "
                             "with --stage build: `test` when build.md sends the story back, else nothing")
    parser.add_argument("--stage", choices=("build",), help="with --back-to: read that stage's file instead of judge.md")
    parser.add_argument("--needs-human", metavar="FILE",
                        help="the decision ids a stage file's needs-human section names; exit 1 when it asks nobody")
    parser.add_argument("--open-decisions", metavar="STORY",
                        help="the decision records that name the story and carry no answer, one path per line")
    parser.add_argument("--stages", action="store_true",
                        help="the gate's stage table: the run order, space-separated (--for-kind, --window, --all "
                             "narrow or widen it); with --shell the bash lines the runner reads once at its start "
                             "(and `PLACE_<KEY>=` for --place), and exit")
    parser.add_argument("--for-kind", choices=ALL_KINDS, help="with --stages: the stages a story of that kind runs")
    parser.add_argument("--window", choices=tuple(SHARED_WINDOWS), help="with --stages: the stages that shared process carries")
    parser.add_argument("--shell", action="store_true", help="with --stages: the stage and the tool table as bash "
                                                                "assignments")
    parser.add_argument("--tool-invocation", metavar="TOOL", choices=tuple(TOOL),
                        help="the command line that starts one stage with that tool, as shell words with the prompt "
                             "left as \"$prompt\", and exit")
    parser.add_argument("--tool-model", default="", help="with --tool-invocation: the model the stage runs on")
    parser.add_argument("--writable", action="append", default=[], metavar="DIR",
                        help="with --tool-invocation: a linked folder the stage writes into")
    parser.add_argument("--readable", action="append", default=[], metavar="DIR",
                        help="with --tool-invocation: a linked folder the stage only reads")
    parser.add_argument("--protect", action="append", default=[], metavar="DIR",
                        help="with --tool-invocation: a folder no stage writes (the pipeline, the evidence, the skills)")
    parser.add_argument("--allow", default="", help="with --tool-invocation: the shell allow-list, Bash(<head>:*),…")
    parser.add_argument("--tool-flags", metavar="TOOL", choices=tuple(TOOL),
                        help="the isolation flags that tool gets, as probed, and exit")
    parser.add_argument("--tool-probe", metavar="TOOL", choices=tuple(TOOL),
                        help="the flags of the tool's record its binary's help does not name: one a stage needs "
                             "(exit 1), an isolation flag only (named, exit 0), none (exit 0), no binary (exit 3)")
    parser.add_argument("--place", metavar="KEY",
                        help="where the factory reads KEY (product, tech, domain, epics, runs), from the profile or its default")
    parser.add_argument("--delivered", metavar="STORY",
                        help="exit 0 when the story carries the gate's delivered mark, 1 when it does not")
    parser.add_argument("--contract", metavar="STAGE",
                        help=f"the exact shape the gate holds that stage's file to ({', '.join(STAGE_ORDER)}), or "
                             "review or glossary, from the gate's own constants, and exit")
    parser.add_argument("--files-skeleton", nargs=2, metavar=("STORY", "STAGE"),
                        help="write the test, build or tidy hand-over's file list from what the tree changed "
                             "(the file's skeleton when it is missing, the missing paths when the stage wrote it)")
    parser.add_argument("--plan-skeleton", metavar="STORY",
                        help="write plan.md's headings and, under `## Acceptance criteria`, one line per criterion "
                             "key of the story (a stage gives each its level; an existing file is left as it is)")
    parser.add_argument("--document-skeleton", metavar="STORY",
                        help="write the document stage's file skeleton with every changed path and run file under "
                             "`## Paths`, as they resolve from the project root; an existing file is kept; and exit")
    parser.add_argument("--slots", type=int, metavar="N",
                        help="with --schedule: the runner's slots — every story in a worktree, up to N at once, "
                             "one `next:` line per story that may start now")
    parser.add_argument("--busy", default="", metavar="IDS",
                        help="with --schedule --slots: the stories this runner runs already, comma-separated")
    parser.add_argument("--skip", default="", metavar="IDS",
                        help="with --schedule: the stories that stopped in this run (`run --keep-going`), "
                             "comma-separated — stopped, and what depends on them blocked")
    parser.add_argument("--worktree-prepare", metavar="STORY",
                        help="make, update and link the story's worktree; print its path (or `none — <why>`)")
    parser.add_argument("--worktree-remove", metavar="STORY", help="remove the story's worktree and its branch")
    parser.add_argument("--worktree-prune", action="store_true",
                        help="remove the worktrees of superseded stories and of ids no story has any more")
    parser.add_argument("--worktree-link", metavar="STORY",
                        help="link the main checkout's places into the story's worktree again (an agent works in it)")
    parser.add_argument("--integrate-prepare", metavar="STORY",
                        help="commit the story's code, merge the main line in, squash; exit 3 with `conflict:` lines")
    parser.add_argument("--integrate-finish", metavar="STORY",
                        help="after the conflicts were resolved: commit the merge and squash; exit 1 while a marker is left")
    parser.add_argument("--migrate-layout", action="store_true",
                        help="move an older layout to one owner per place — what `factory.sh update` runs once — and exit")
    parser.add_argument("--epics", help="where the epics and stories are (default: the profile's `epics:`, else product/epics)")
    parser.add_argument("--runs", help="the run artefacts (default: the profile's `runs:`, else .dca-factory/runs)")
    parser.add_argument("--profile", help=f"the stack profile (default: FACTORY_PROFILE, else {PROFILE_FILE} at the root)")
    parser.add_argument("--root", default=".", help="the project's root directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.root)
    os.chdir(cwd)
    profile_path = resolve_profile(args.profile or os.environ.get("FACTORY_PROFILE") or None, cwd)
    set_places(read_profile(profile_path), epics=args.epics, runs=args.runs)
    args.epics, args.runs = place("epics"), place("runs")
    # the runner's questions first: they read one file and print one answer
    if args.tool_invocation:
        print(tool_invocation(TOOL[args.tool_invocation], args.tool_model, args.writable, args.readable, args.protect,
                              args.allow))
        return 0
    if args.tool_flags:
        print(" ".join(shlex.quote(w) for w in isolation_args(TOOL[args.tool_flags])))
        return 0
    if args.tool_probe:
        tool = TOOL[args.tool_probe]
        probed = unprobed_flags(tool)
        if probed is None:
            print(f"{tool.name}: no binary `{tool.help[0]}` on the PATH — not probed")
            return 3
        required, isolation = probed
        print(f"{tool.name}: " + (f"the help does not name {', '.join(required)} — a stage started with it fails"
                                   if required else "every flag a stage needs is in the help"))
        if isolation:
            print(f"{tool.name}: no {', '.join(isolation)} in this binary — its stages run with the tool's own setup")
        return 1 if required else 0
    if args.stages:
        if args.shell:
            if args.place and args.place not in DEFAULTS:
                parser.error(f"--place takes one of {', '.join(DEFAULTS)}")
            return stages_shell((args.place,) if args.place else ())
        print(" ".join(stage_names(args.for_kind, args.window, args.every)))
        return 0
    if args.contract:
        text = contract_text(args.contract, args.runs)
        if text is None:
            print(f"factory-cli: --contract takes one of {', '.join(STAGE_ORDER)}, review or glossary, not {args.contract!r}", file=sys.stderr)
            return 2
        print(text)
        return 0
    if args.files_skeleton:
        return files_skeleton(args.runs, args.files_skeleton[0], args.files_skeleton[1], cwd)
    if args.plan_skeleton:
        return plan_skeleton(args.runs, args.plan_skeleton, cwd)
    if args.document_skeleton:
        return document_skeleton(args.runs, args.document_skeleton, cwd)
    if args.migrate_layout:
        return migrate_layout(cwd)
    if args.place:
        if args.place not in DEFAULTS:
            parser.error(f"--place takes one of {', '.join(DEFAULTS)}")
        print(place(args.place))
        return 0
    if args.delivered:
        try:
            return 0 if is_delivered(read_front_matter(find_story(args.epics, args.delivered))[0]) else 1
        except GateError as error:
            print(f"factory: {error}", file=sys.stderr)
            return 2
    if args.get is not None:
        print(read_profile(profile_path).get(args.get, ""))
        return 0
    if args.command_heads:
        print("\n".join(command_heads(read_profile(profile_path))))
        return 0
    if args.findings:
        rows = open_findings(args.epics)
        if not rows:
            print("factory: no open finding — the judges confirmed nothing that did not block, or every row is closed")
            return 0
        for story, where, severity, defect, _perspective, _fix, plain in rows:
            print(f"{story}\t{severity}\t{where}\t" + (f"{plain} — {defect}" if plain else defect))
        print(f"factory: {len(rows)} open finding(s); set Status to done or wont-fix in the story's {FINDINGS_FILE} "
              f"or the project's file under product/findings/")
        return 0
    if args.perspectives:
        for name, carrier in perspectives_of(read_profile(resolve_profile(None, cwd))):
            print(f"{name}\t{carrier}")
        return 0
    if args.carriers:
        print("\n".join(carriers(read_profile(profile_path))))
        return 0
    if args.carrier_lines:
        print("\n".join(f"{key} {value}" for key, value in carrier_lines(read_profile(profile_path))))
        return 0
    if args.model:
        print(model_for(read_profile(profile_path), *args.model))
        return 0
    if args.verdict:
        print(verdict_of_story(args.runs, args.verdict))
        return 0
    if args.back_to:
        if args.stage:
            # the build stage found a defect in a test's own code, not in what it asserts: only `test` sends it back
            path = os.path.join(args.runs, args.back_to, STAGE_FILES[args.stage])
            print("test" if os.path.isfile(path) and back_in(read_text(path)) == "test" else "")
            return 0
        path = os.path.join(args.runs, args.back_to, "judge.md")
        print(back_in(read_text(path)) if os.path.isfile(path) else "build")
        return 0
    if args.needs_human:
        lines = needs_human_lines(args.needs_human, args.story)
        if lines is None:
            return 1
        print("\n".join(lines))
        return 0
    if args.open_decisions:
        print("\n".join(open_decision_files(cwd, args.open_decisions)))
        return 0
    if args.follow:
        return follow(args.runs, args.story, args.once, args.format, args.lines, args.process, args.every)
    if args.list_decisions:
        return list_decisions(cwd, args.story, args.format, args.color)
    if args.discover_list:
        return discovery_list(cwd, args.epics, args.format, args.color)
    if args.kind:
        if not args.story:
            parser.error("--kind needs --story")
        print(story_kind(read_front_matter(find_story(args.epics, args.story))[0]))
        return 0
    if args.resolve is not None:
        return resolve(args.epics, args.resolve)
    if args.schedule:
        return schedule(cwd, args.epics, args.runs, args.slots,
                        tuple(s.strip() for s in args.busy.split(",") if s.strip()),
                        tuple(s.strip() for s in args.skip.split(",") if s.strip()))
    if args.worktree_prepare:
        return worktree_prepare(cwd, args.runs, args.worktree_prepare)
    if args.worktree_remove:
        return worktree_remove(cwd, args.worktree_remove)
    if args.worktree_prune:
        return worktree_prune(cwd, args.epics)
    if args.worktree_link:
        if not has_worktree(args.worktree_link, cwd):
            print(f"factory: {args.worktree_link} has no worktree", file=sys.stderr)
            return 1
        link_places(worktree_of(args.worktree_link, cwd), cwd, args.runs)
        return 0
    if args.integrate_prepare:
        return integrate_prepare(cwd, args.runs, args.epics, args.integrate_prepare)
    if args.integrate_finish:
        return integrate_finish(cwd, args.runs, args.epics, args.integrate_finish)
    if args.start:
        if not args.story:
            parser.error("--start needs --story")
        return start(cwd, args.epics, args.runs, args.story, args.slots)
    if args.reopen:
        return reopen(cwd, args.runs, args.epics, args.reopen)
    if args.deliver_by_hand:
        return deliver_by_hand(cwd, args.runs, args.epics, args.deliver_by_hand, args.by, args.force)
    if args.prove:
        return prove(cwd, args.runs, args.epics, args.prove)
    if args.spec_check:
        return spec_check(cwd, args.runs, args.epics)
    if args.spec_delta:
        return print_spec_delta(spec_delta_view(args.runs, args.epics, args.spec_delta), args.format)
    if args.claim_story:
        return claim_command(cwd, args.runs, args.epics, args.claim_story)
    if args.claims_refresh:
        config = claim_config_here(cwd)
        return refresh_claims(cwd, args.runs, config, claim_target(cwd)) if config else 0
    if args.release_claim:
        config = claim_config_here(cwd)
        if not config:
            print("release: the profile names no `claim_remote:` — there is no claim to release")
            return 1
        return release_claim(cwd, args.runs, config, args.release_claim, args.force)
    if args.free_id:
        print(free_id(cwd, args.epics, claim_config_here(cwd), claim_target(cwd), args.free_id))
        return 0
    if args.undeliver_branch:
        return undeliver_branch(cwd, args.runs, args.epics, args.undeliver_branch)
    if args.listening or args.claim or args.release is not None:
        freeze_all(args.runs)
    if args.listening:
        return mark_listening(cwd)
    if args.claim:
        return claim(cwd, args.claim)
    if args.release is not None:
        return release(cwd, args.release or session_owner())
    if args.backfill_created:
        return backfill_created(cwd, args.epics)
    if args.status and args.brief:
        try:
            return status_brief(cwd, args.epics, args.runs, args.session_start)
        except Exception as error:                      # a hook must never break a session's start
            print(f"factory: status unavailable ({error.__class__.__name__})")
            return 0
    if args.help_view:
        return factory_help(cwd, args.epics, args.runs, args.format, args.color)
    if args.status:
        return status(cwd, args.epics, args.runs, args.story, args.format, args.color, args.live, args.part,
                      every=args.every, epic_filter=args.epic)
    if args.window_start or args.window_end:
        if not args.story:
            parser.error("--window-start/--window-end need --story")
        return mark_window(cwd, args.runs, args.story, args.window_start or args.window_end,
                           "start" if args.window_start else "end", args.session_log)
    if args.stage_start or args.stage_end:
        if not args.story:
            parser.error("--stage-start/--stage-end need --story")
        code = mark_stage(cwd, args.runs, args.story, args.stage_start or args.stage_end,
                          "start" if args.stage_start else "end", args.session_log)
        if args.stage_start and code == 0:
            record_owned(args.runs, args.story)
        return (owned_end(args.runs, args.story, args.stage_end, str(code)) or code) if args.stage_end else code
    if args.owned_confirm:
        return owned_confirm(args.runs, args.owned_confirm)
    if args.refusals:
        return refusals_report(args.runs, args.story, args.format)
    if args.journal_line:
        journal_writer(args.runs, args.journal_line).write(sys.stdin.read())
        return 0
    if args.usage_from:
        return usage_from(args.usage_from[0], args.usage_from[1], args.usage_model)
    if args.usage:
        return usage_report(args.runs, args.story, args.total, cwd, args.epics, args.format)
    parser.error("nothing asked — --status, --schedule, --usage, --list-decisions, … (a stage's gate is story-gate.py's)")
