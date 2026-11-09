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
import json
import os
import sys
import textwrap
import time
import typing
from ....application.decisions.list_decisions import UNREADABLE, record_waits
from .....contract import CONTRACT, VERSION
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, place, PROFILE_FILE, read_profile, resolve_profile, set_places)
from ....application.description.show_part import ShowPartQuery
from ....application.profile.ask_profile import AskProfileQuery, Question
from ....application.status.show_status import ShowStatusQuery
from ....application.status.show_story import ShowStoryQuery, UnknownStory
from ....application.status.show_epic import ShowEpicQuery, UnknownEpic
from ....application.status.show_help import ShowHelpQuery
from ....application.status.texts import stamp_text
from ....application.decisions.list_decisions import ListDecisionsQuery
from ....application.requests.list_requests import ListRequestsQuery
from ....application.requests.pending_requests import PendingRequestsQuery
from ....domain.model.story import StoryId
from ....application.run.resolve_run_argument import ResolveRunArgumentQuery
from ....application.status.show_refusals import ShowRefusalsQuery
from ....application.status.show_journal_story import ShowJournalStoryQuery
from ....application.cost.show_spent import ShowSpentQuery
from ....application.shared.usage_ledger import Spent
from ....application.status.list_findings import ListFindingsQuery
from ....application.delivery.show_brief import ShowBriefQuery
from ....application.delivery.show_story_kind import ShowStoryKindQuery
from .brief_view import brief_model, markdown as brief_markdown
from ....application.delivery.show_stage_table import ShowStageTableQuery
from ....application.delivery.next_free_story_id import NextFreeStoryIdQuery
from ....application.lifecycle.show_worker import ShowWorkerQuery
from ....application.status.show_discovery import ShowDiscoveryQuery
from ....application.delivery.probe_tool import Probed, ProbeToolQuery
from ....application.cost.read_tool_usage import ReadToolUsageQuery
from ....application.delivery.show_hand_over_contract import ShowHandOverContractQuery
from ....application.delivery.write_skeleton import Skeleton
from ....application.status.follow_output import FollowOutputQuery
from ....application.status.show_stage_outputs import ShowStageOutputsQuery
from ....domain.model.run_argument import ArgumentMeaning
from ....domain.model.stage import StageName, StoryKind, Window
from . import spec_delta_view as spec_delta_text
from ....application.delivery.check_spec import CheckSpecQuery
from ....application.delivery.show_spec_delta import ShowSpecDeltaQuery
from ..runner.run_command import request_main, run_main
from .terminal import (
    MARKS_MD, MARKS_TEXT, bold, decision_mark, dim, heading, how_lines, how_md, json_ready, paint, section, table_md, table_text, use_colour, view_width)
from .status_view import render_short_md, render_short_text, render_status_md, render_status_text, token_rows
from .story_view import render_story_md, render_story_text, stage_caption, stage_cells
from .epic_view import render_epic_md, render_epic_text
from .schedule_view import schedule_lines, start_lines
from .help_view import render_help_md, render_help_text
from ....application.delivery.pipeline_workflow import workflow

from . import checkout_commands, delivery_commands, root, session_commands, upkeep_commands
from .common import placed
from .question_command import stages_shell
from .delivery_commands import owned_confirm, reopen, deliver_by_hand, claim_command, undeliver_branch, prove
from .backlog_commands import backfill_created
from .lifecycle_commands import up_command, down_command, serve_command
from .requests_commands import request_command, requests_command


Model = typing.Dict[str, typing.Any]
RESULT = typing.TypeVar("RESULT")


def resolve(epics: str, argument: str) -> int:
    """What `/factory-run <argument>` means — decided here, not by a model: one word naming a story is that
    story; one word naming none is an unknown id, never a new story (a typo stays a typo); more than one
    word is a wish, for the backlog skill to turn into a story; nothing is the backlog."""
    resolved = root.wiring.resolve_run_argument(".").execute(ResolveRunArgumentQuery(argument))
    if resolved.meaning is ArgumentMeaning.STORY and resolved.story:
        print(f"story {resolved.story.value}")
        return 0
    if resolved.meaning is ArgumentMeaning.UNKNOWN:
        known = [story.value for story in resolved.known]
        print(f"unknown {resolved.word} — no story by that id under {epics.replace(os.sep, '/')}/"
              + (f"; the backlog has: {', '.join(known)}" if known else "; the backlog has no story yet")
              + ". A wish takes more than one word.")
        return 2
    print(resolved.meaning.value)
    return 0


def discovery_model(cwd: str, epics: str) -> Model:
    """Every discovery topic with its proposals and changes and what a person can do with each (`ShowDiscoveryUseCase`)."""
    return root.wiring.show_discovery(cwd).execute(ShowDiscoveryQuery(os.path.basename(os.path.abspath(cwd))))


def discovery_list(cwd: str, epics: str, fmt: str = "text", colour: str = "auto") -> int:
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


def list_decisions(cwd: str, story_id: typing.Optional[str] = None, fmt: str = "text", colour: str = "auto") -> int:
    """The inbox: every record, what waits for a person first — open, drafts, answered, applied — read
    from the files alone; the same view as the status, in text, Markdown or JSON."""
    model = root.wiring.list_decisions(cwd).execute(ListDecisionsQuery(story_id))
    records = model["records"]
    waiting = [r for r in records if (record_waits(r["state"]) or r["state"] == UNREADABLE)]
    mark = lambda r: "look" if r["kind"] == "acceptance" and record_waits(r["state"]) else \
        "stopped" if r["state"] == UNREADABLE else decision_mark(r)
    headers = ["record", "state", "story / stage", "asked (UTC)", "question → answer"]
    cells = lambda marks: [[f"{marks[mark(r)]} {r['id']}", r["state"], f"{r['story']} / {r['stage']}",
                            stamp_text(r["asked"]), r["text"]] for r in records]
    summary = f"{len(records)} record" + ("" if len(records) == 1 else "s") + " · " + \
        (f"{len(waiting)} wait" + ("s" if len(waiting) == 1 else "") + " for you" if waiting else "nothing waits for you")
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
        return 0
    first = next((r for r in records if r in waiting), None)
    how = model["how"]
    if fmt == "md":
        lead = "look" if first and first["kind"] == "acceptance" else "question" if waiting else "done"
        out = [f"### Decisions — {model['project']}" + (f" · {story_id}" if story_id else ""), "",
               f"{MARKS_MD[lead]} {summary}", ""]
        if records:
            # the question beside the record would make the table too wide to read: a list below it
            out += table_md(headers[:-1], [c[:-1] for c in cells(MARKS_MD)], first_bold=True)
            out += ["", "**Questions and answers**", ""] + [f"- **{r['id']}** — {r['text']}" for r in records]
        out += ["", f"**Next:** answer {first['id']} — {how_md(how)}" if how and first else "**Next:** Nothing waits for you."]
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
    if how and first:
        out += [f"  {bold('Next', use)}   answer {first['id']}."] + how_lines(how, use, "         ")
    else:
        out.append(f"  {bold('Next', use)}   Nothing waits for you.")
    print("\n".join(out + [""]))
    return 0


def refusals_report(runs: str, story_filter: typing.Optional[str] = None, fmt: str = "text") -> int:
    """`--refusals`: every story's refusals, form against substance — what a bench counts (`ShowRefusalsUseCase`)."""
    model = root.wiring.show_refusals(runs).execute(ShowRefusalsQuery(story_filter))
    if fmt == "json":
        print(json.dumps(model, indent=2, sort_keys=True))
        return 0
    for story, counts in model["stories"].items():
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


def usage_report(runs: str, story_filter: typing.Optional[str] = None, total_only: bool = False, cwd: str = ".",
                 epics: typing.Optional[str] = None, fmt: str = "text") -> int:
    """Tokens by class, as the status shows them: one story's stages, or every story by epic."""
    epics = epics or place("epics")
    if total_only:
        spent = root.wiring.show_spent(runs).execute(ShowSpentQuery((story_filter,) if story_filter else None))
        print(spent.tokens)
        return 0
    colour = use_colour("auto")
    if story_filter:
        try:
            model = story_model(cwd, epics, runs, story_filter)
        except GateError:
            model = root.wiring.show_journal_story(cwd, epics, runs).execute(ShowJournalStoryQuery(story_filter))
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


def status_model(cwd: str, epics: str, runs: str, live: bool = False) -> Model:
    """Where the factory stands — the status read model, over the project's files."""
    return root.wiring.show_status(cwd, epics, runs).execute(ShowStatusQuery(live))


def foreign_claim_lines(claims: typing.Sequence[Model]) -> typing.List[str]:
    """The foreign claims as the session's start says them: one line each kind, like the findings."""
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


def spent_text(spent: typing.Optional[Spent]) -> str:
    """What a story cost so far, as the schedule's line shows it; nothing for a story without a journal."""
    if not spent or not spent.invocations:
        return ""
    return f" · {spent.invocations} stage invocation(s)" + (f", {spent.tokens:,} tokens" if spent.tokens else "")


def schedule(cwd: str, epics: str, runs: str, slots: typing.Optional[int] = None,
             busy: typing.Sequence[str] = (), skip: typing.Sequence[str] = ()) -> int:
    """Print every story's state and the next one to run; return 0. The runner and the tests read these lines
    (`schedule_view.py`)."""
    data = root.wiring.schedule_data(cwd, epics, runs, slots, busy, skip)
    spent = root.wiring.show_spent(runs).execute(ShowSpentQuery(tuple(data["order"]))).by_story
    for line in schedule_lines(data, epics, {story: spent_text(spent[story]) for story in data["order"]}):
        print(line)
    return 0


def start(cwd: str, epics: str, runs: str, story_id: str, slots: typing.Optional[int] = None) -> int:
    """Where the story starts, printed as `state:`, `start:` (a stage, or `none`) and `detail:`. Exit 2 for an
    unknown story."""
    found = root.wiring.start_of(cwd, epics, runs, story_id, slots)
    if found is None:
        print(f"factory: no story {story_id} under {epics}/", file=sys.stderr)
        return 2
    for line in start_lines(found):
        print(line)
    return 0


def status_brief(cwd: str, epics: str, runs: str, session_start: bool = False) -> int:
    """Two lines: what is ready, what waits, who works, what it cost — for a session's start."""
    view = status_model(cwd, epics, runs)
    words: typing.Dict[str, typing.List[str]] = {}
    for row in view["rows"]:
        words.setdefault(row["state"], []).append(row["story"])
    summary = " · ".join(f"{len(v)} {k}" for k, v in sorted(words.items())) or "no stories yet"
    print(f"factory: {summary}" + (f" · {view['tokens']:,} tokens so far" if view["measured"] else ""))
    waiting = "; ".join(f"{MARKS_TEXT[w['mark']]} {w['story']} {w['what']}" for w in view["waiting"])
    print("factory: " + (f"waiting for you: {waiting} · " if waiting else "nothing waits for you · ")
          + (f"worker {view['holder']} holds the checkout · " if view["holder"] else "no worker running · ")
          + f"next: {view['next']['text']}")
    if view["listening"]:
        print(f"factory: {view['listening']}")
    for line in foreign_claim_lines(view["claims"]):
        print(f"factory: {line}")
    findings = view["findings"]
    if findings:
        stories = sorted({f["story"] for f in findings})
        print(f"factory: {len(findings)} open finding(s) in {len(stories)} file(s) "
              f"(<story>/{view['findings_name']} in the story's folder, product/findings/ for the project's own) — "
              f"`factory-cli.py --findings` lists them")
    # A skill link that points nowhere — its plugin version pruned from the cache, a checkout moved: the
    # skills are then missing for a session and a runner stage alike, and only the update relinks them.
    dangling = view["dangling"]
    if dangling:
        more = f" and {len(dangling) - 1} more" if len(dangling) > 1 else ""
        print(f"factory: skill link {dangling[0]} points nowhere{more} — /factory-update relinks them (or copies, with --copy)")
    # The part of the factory that is missing, where the files show it: the description, the backlog.
    undescribed = [part["path"] for part in view["description"] if part["part"] in ("product", "tech")
                   and not part["present"]]
    if view["hint"]:
        print(f"factory: {view['hint']}")
    elif undescribed:
        print(f"factory: no project description ({', '.join(undescribed)}) — /factory-setup")
    elif not view["rows"]:
        print("factory: the backlog is empty — /factory-backlog writes the first epic and story")
    if session_start and os.environ.get("FACTORY_WORKER"):
        # A stage the runner started: the hook runs in its session too, and the claim it names is the
        # runner's — this session's own. Said plainly, or a careful model takes itself for a second writer.
        # A shared builder or verifier is named by what it carries out: told it is "stage builder", a model read
        # that as the build stage alone and refused the plan, test and tidy its prompt asked for.
        stage = os.environ.get("FACTORY_STAGE") or "?"
        covered = [s.name.value for s in workflow().stages if s.window and s.window.value == stage]
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


def story_model(cwd: str, epics: str, runs: str, story_id: str, live: bool = False) -> Model:
    try:
        return root.wiring.show_story(cwd, epics, runs).execute(ShowStoryQuery(story_id, live))
    except UnknownStory:
        raise GateError(f"no story {story_id} under {epics}/") from None


def epic_model(cwd: str, epics: str, runs: str, epic_id: str, live: bool = False) -> Model:
    try:
        return root.wiring.show_epic(cwd, epics, runs).execute(ShowEpicQuery(epic_id, live))
    except UnknownEpic as unknown:
        raise GateError(f"no epic {epic_id} under {epics}/ — the epics: {', '.join(unknown.known) or 'none'}") from None


def help_model(cwd: str, epics: str, runs: str) -> Model:
    return root.wiring.show_help(cwd, epics, runs).execute(ShowHelpQuery())


def status(cwd: str, epics: str, runs: str, story_filter: typing.Optional[str] = None, fmt: str = "text", colour: str = "auto",
           live: bool = False, part: str = "all", every: bool = False, epic_filter: typing.Optional[str] = None) -> int:
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


def factory_help(cwd: str, epics: str, runs: str, fmt: str = "text", colour: str = "auto") -> int:
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


def spec_check(cwd: str, runs: str, epics: str) -> int:
    """Story and spec agree (WP-98, `CheckSpecUseCase`): one line per disagreement; exit 1 when there is one."""
    checked = root.wiring.check_spec(runs, epics).execute(CheckSpecQuery())
    for line in checked.problems:
        print(f"spec: {line}")
    if not checked.problems:
        count = checked.delivered
        print(f"spec: every criterion of the {count} delivered stor{'y' if count == 1 else 'ies'} stands in its "
              "spec, and every spec file holds its shape")
    return 1 if checked.problems else 0


# --- the carriers the profile names ------------------------------------------------------

#: A name the shell runner takes as one word: a stage, a shared process, a kind — and a hand-over's file.
def answer(profile_path: typing.Optional[str], question: Question, **fields: str) -> int:
    """The profile's answer to one question, a line per item (`AskProfileUseCase`)."""
    print("\n".join(root.wiring.ask_profile(profile_path).execute(AskProfileQuery(question, **fields))))
    return 0


def follow(runs: str, story: typing.Optional[str], once: bool, fmt: str, width: int, process: typing.Optional[str] = None, every: bool = False,
           request: typing.Optional[str] = None) -> int:
    """What the stage in flight does: every process of a story (`every`), the newest output's last lines (`once`), or
    the newest output as it is written until interrupted."""
    if every and not story:
        print("factory: follow --all names a story (--story <id>)", file=sys.stderr)
        return 2
    if every or once:
        shown = root.wiring.show_stage_outputs(runs).execute(ShowStageOutputsQuery(
            story, process, request, every=every, lines=width))
        if fmt == "json":
            if every:
                print(json.dumps({"story": story, "processes": [
                    dict(stage=e["stage"], file=e["file"], running=e["running"], lines=e["lines"]) for e in shown]},
                    ensure_ascii=False))
            else:
                print(json.dumps(shown[0] if shown else {"story": story or "", "stage": "", "file": "",
                                                         "running": False, "lines": []}, ensure_ascii=False))
            return 0
        if not shown:
            print("factory: no stage output yet" + (f" for {story}" if story else ""))
        for entry in shown:
            print(f"══ {entry['story'] if not every else story} · {entry['stage']}"
                  + (" (running)" if entry["running"] else ""))
            for line in entry["lines"]:
                print(line)
            if every:
                print()
        return 0
    following = root.wiring.follow_output(runs)
    current, offset, pending = None, 0, ""
    try:
        while True:
            followed = following.execute(FollowOutputQuery(story, process, request, current, offset, pending))
            if followed.started and followed.current:
                print(f"══ {followed.current.name} · {followed.current.stage}", flush=True)
            for line in followed.lines:
                print(line, flush=True)
            current, offset, pending = followed.current, followed.offset, followed.pending
            time.sleep(1)
    except KeyboardInterrupt:
        return 0


# --- the factory as a process of its own, and what a person asks of it (WP-91) -----------------------------------------


def pending_requests(cwd: str) -> typing.List[Model]:
    """The requests not done — what a view's press may be pending on."""
    return root.wiring.pending_requests(cwd).execute(PendingRequestsQuery()).requests


def request_counts(cwd: str) -> Model:
    """The requests by state."""
    return root.wiring.list_requests(cwd).execute(ListRequestsQuery())["counts"]


def worker_command(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory-cli.py --worker")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    placed()
    info, line = root.wiring.show_worker().execute(ShowWorkerQuery())
    print(json.dumps(info) if args.format == "json" else line)
    return 0


LIFECYCLE = {"--request": request_command, "--requests": requests_command, "--work-request": request_main,
             "--up": up_command, "--down": down_command, "--serve": serve_command, "--worker": worker_command}


def main(argv: typing.Sequence[str]) -> int:
    if argv[:1] == ["--run"]:                    # `factory.sh run` once its checks passed: the runner itself
        return run_main(argv[1:])
    lifecycle = LIFECYCLE.get(argv[0]) if argv else None
    if lifecycle:                                # the factory as a process, its requests and its page (WP-91)
        return lifecycle(argv[1:])
    parser = argparse.ArgumentParser(add_help=True, description="factory cli")
    parser.add_argument("--version", action="version", version=f"factory-cli {VERSION} (file contract {CONTRACT})")
    parser.add_argument("--story")
    parser.add_argument("--discover-list", action="store_true",
                        help="every discovery topic, its proposed epics (and which are epics) and its proposed description changes")
    parser.add_argument("--follow", action="store_true",
                        help="print what the stage in flight does, one line per tool call, as it happens (--once: the last lines and exit)")
    parser.add_argument("--once", action="store_true", help="with --follow: print the newest output's last lines and exit")
    parser.add_argument("--process", help="with --follow: only that process's output — builder, verifier, review-ddd, plan, …")
    parser.add_argument("--request", help="with --follow: the output of that request's process")
    parser.add_argument("--all", dest="every", action="store_true",
                        help="with --follow --story: every process of the story, in the order they began, and exit; "
                             "with --stages: every row of the table, the steps after the run order too; "
                             "with --status: every story by epic, with times and tokens, instead of the short view")
    parser.add_argument("--epic", help="with --status: one epic — its fields, its text, its stories with their state")
    parser.add_argument("--backfill-created", action="store_true",
                        help="write `created:` into every story and epic without one, from the commit that added the "
                             "file — once, never over a value there (`factory.sh update` runs it)")
    parser.add_argument("--ignore-journals", action="store_true",
                        help="let the story journals into git: the .gitignore line that ignores the pipeline's folder "
                             "becomes lines that keep everything but the journals out (`factory.sh setup`/`update`)")
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
    parser.add_argument("--description-part", choices=("product", "tech", "domain"),
                        help="one part of the project description as written, section by section (--format json)")
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
    parser.add_argument("--stages", action="store_true",
                        help="the gate's stage table: the run order, space-separated (--window, --all "
                             "narrow or widen it); with --shell the bash lines the runner reads once at its start "
                             "(and `PLACE_<KEY>=` for --place), and exit")
    parser.add_argument("--window", choices=tuple(w.value for w in Window), help="with --stages: the stages that shared process carries")
    parser.add_argument("--shell", action="store_true", help="with --stages: the stage and the tool table as bash "
                                                                "assignments")
    parser.add_argument("--tool-probe", metavar="TOOL",
                        help="the flags of the tool's record its binary's help does not name: one a stage needs "
                             "(exit 1), an isolation flag only (named, exit 0), none (exit 0), no binary (exit 3)")
    parser.add_argument("--place", metavar="KEY",
                        help="where the factory reads KEY (product, tech, domain, epics, runs), from the profile or its default")
    parser.add_argument("--stage-brief", nargs=2, metavar=("STORY", "STAGE"),
                        help="print what the stage is told for the story — its brief, from the workflow, the rules "
                             "and the profile (with --format md or json)")
    parser.add_argument("--contract", metavar="STAGE",
                        help=f"the exact shape the gate holds that stage's file to ({', '.join(s.value for s in workflow().order(StoryKind.STORY))}), or "
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
    if args.tool_probe:
        name = args.tool_probe
        probe = root.wiring.probe_tool().execute(ProbeToolQuery(name))
        if probe.outcome is Probed.UNKNOWN:
            parser.error(f"--tool-probe takes one of {', '.join(probe.known)}, not {name!r}")
        if probe.outcome is Probed.NOT_INSTALLED or not probe.found:
            print(f"{name}: no binary `{probe.binary}` on the PATH — not probed")
            return 3
        required, isolation = probe.found.required, probe.found.isolation
        print(f"{name}: " + (f"the help does not name {', '.join(required)} — a stage started with it fails"
                             if required else "every flag a stage needs is in the help"))
        if isolation:
            print(f"{name}: no {', '.join(isolation)} in this binary — its stages run with the tool's own setup")
        return 1 if required else 0
    if args.stages:
        if args.shell:
            if args.place and args.place not in DEFAULTS:
                parser.error(f"--place takes one of {', '.join(DEFAULTS)}")
            return stages_shell(root.wiring.show_stage_table().execute(
                ShowStageTableQuery((args.place,) if args.place else (), with_tools=True)))
        table = root.wiring.show_stage_table().execute(ShowStageTableQuery())
        print(" ".join(row["name"] for row in table["rows"] if (args.every or row["in_order"])
                       and (args.window is None or row["window"] == args.window)))
        return 0
    if args.contract:
        text = root.wiring.show_hand_over_contract(cwd, args.runs).execute(ShowHandOverContractQuery(args.contract))
        if text is None:
            print(f"factory-cli: --contract takes one of {', '.join(s.value for s in workflow().order(StoryKind.STORY))}, review or glossary, not {args.contract!r}", file=sys.stderr)
            return 2
        print(text)
        return 0
    if args.files_skeleton:
        return delivery_commands.skeleton(cwd, args.runs, Skeleton.FILES, args.files_skeleton[0], args.files_skeleton[1])
    if args.plan_skeleton:
        return delivery_commands.skeleton(cwd, args.runs, Skeleton.PLAN, args.plan_skeleton)
    if args.document_skeleton:
        return delivery_commands.skeleton(cwd, args.runs, Skeleton.DOCUMENT, args.document_skeleton)
    if args.migrate_layout:
        return upkeep_commands.migrate_layout(cwd)
    if args.place:
        if args.place not in DEFAULTS:
            parser.error(f"--place takes one of {', '.join(DEFAULTS)}")
        print(place(args.place))
        return 0
    if args.get is not None:
        return answer(profile_path, Question.VALUE, key=args.get)
    if args.command_heads:
        return answer(profile_path, Question.COMMAND_HEADS)
    if args.findings:
        found = root.wiring.list_findings(cwd, args.epics, args.runs).execute(ListFindingsQuery())
        rows = found["rows"]
        if not rows:
            print("factory: no open finding — the judges confirmed nothing that did not block, or every row is closed")
            return 0
        for row in rows:
            print(f"{row['story']}\t{row['severity']}\t{row['where']}\t"
                  + (f"{row['plain']} — {row['defect']}" if row["plain"] else row["defect"]))
        print(f"factory: {len(rows)} open finding(s); set Status to done or wont-fix in the story's {found['name']} "
              f"or the project's file under product/findings/")
        return 0
    if args.perspectives:
        return answer(resolve_profile(None, cwd), Question.PERSPECTIVES)
    if args.carriers:
        return answer(profile_path, Question.CARRIERS)
    if args.carrier_lines:
        return answer(profile_path, Question.CARRIER_LINES)
    if args.model:
        return answer(profile_path, Question.MODEL, tool=args.model[0], stage=args.model[1])
    if args.follow:
        return follow(args.runs, args.story, args.once, args.format, args.lines, args.process, args.every,
                      args.request)
    if args.list_decisions:
        return list_decisions(cwd, args.story, args.format, args.color)
    if args.discover_list:
        return discovery_list(cwd, args.epics, args.format, args.color)
    if args.stage_brief:
        try:
            brief = root.wiring.show_brief(cwd).execute(ShowBriefQuery(StoryId(args.stage_brief[0]),
                                                                  StageName(args.stage_brief[1])))
        except ValueError as refused:
            print(f"factory-cli: {refused}", file=sys.stderr)
            return 2
        print(json.dumps(brief_model(brief), ensure_ascii=False) if args.format == "json" else brief_markdown(brief), end="")
        return 0
    if args.kind:
        if not args.story:
            parser.error("--kind needs --story")
        print(root.wiring.show_story_kind(cwd).execute(ShowStoryKindQuery(StoryId(args.story))).value)
        return 0
    if args.resolve is not None:
        return resolve(args.epics, args.resolve)
    if args.schedule:
        return schedule(cwd, args.epics, args.runs, args.slots,
                        tuple(s.strip() for s in args.busy.split(",") if s.strip()),
                        tuple(s.strip() for s in args.skip.split(",") if s.strip()))
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
    if args.description_part:
        view = root.wiring.show_part(cwd).execute(ShowPartQuery(args.description_part))
        print(json.dumps(view, indent=2) if args.format == "json"
              else "\n\n".join(f"## {s['heading']}\n\n{s['text']}" for s in view["sections"]) or f"{view['path']}: missing")
        return 0
    if args.spec_delta:
        view = root.wiring.show_spec_delta(args.runs, args.epics).execute(ShowSpecDeltaQuery(args.spec_delta))
        print(spec_delta_text.render(view, args.format))
        return 0
    if args.claim_story:
        return claim_command(cwd, args.runs, args.epics, args.claim_story)
    if args.claims_refresh:
        return delivery_commands.refresh_claims(cwd, args.epics, args.runs)
    if args.release_claim:
        return delivery_commands.release_claim(cwd, args.epics, args.runs, args.release_claim, args.force)
    if args.free_id:
        print(root.wiring.next_free_story_id(cwd, args.epics, args.runs).execute(NextFreeStoryIdQuery(args.free_id)))
        return 0
    if args.undeliver_branch:
        return undeliver_branch(cwd, args.runs, args.epics, args.undeliver_branch)
    if args.listening:
        return checkout_commands.mark_listening(cwd, args.runs)
    if args.claim:
        return checkout_commands.take_checkout(cwd, args.runs, args.claim)
    if args.release is not None:
        return checkout_commands.give_checkout_back(cwd, args.runs, args.release or None)
    if args.backfill_created:
        return backfill_created(cwd, args.epics)
    if args.ignore_journals:
        journals = upkeep_commands.let_journals_into_git(cwd)
        if journals:
            print(f"journals: .gitignore lets the story journals ({journals}/<story>/journal.tsv) and the page's theme "
                  f"(.dca-factory/theme/) into git — the rest of the pipeline's folder stays out")
        return 0
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
        if args.window_start:
            return session_commands.open_window(cwd, args.runs, args.story, args.window_start, args.session_log)
        return session_commands.close_window(cwd, args.runs, args.story, args.window_end, args.session_log)
    if args.stage_start or args.stage_end:
        if not args.story:
            parser.error("--stage-start/--stage-end need --story")
        if args.stage_start:
            return session_commands.start_stage(cwd, args.runs, args.story, args.stage_start, args.session_log)
        return session_commands.end_stage(cwd, args.runs, args.story, args.stage_end, args.session_log)
    if args.owned_confirm:
        return owned_confirm(args.runs, args.owned_confirm, cwd)
    if args.refusals:
        return refusals_report(args.runs, args.story, args.format)
    if args.journal_line:
        return session_commands.append_journal(cwd, args.runs, args.journal_line, sys.stdin.read())
    if args.usage_from:
        print("\n".join(root.wiring.read_tool_usage().execute(
            ReadToolUsageQuery(args.usage_from[0], args.usage_from[1], args.usage_model))))
        return 0
    if args.usage:
        return usage_report(args.runs, args.story, args.total, cwd, args.epics, args.format)
    parser.error("nothing asked — --status, --schedule, --usage, --list-decisions, … (a stage's gate is story-gate.py's)")
