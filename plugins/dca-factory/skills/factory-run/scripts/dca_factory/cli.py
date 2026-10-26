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
import sys
import textwrap
import time
from .delivery.adapter.outgoing.pipeline.stage_rows import SHARED_WINDOWS, STAGE_ORDER
from .contract import CONTRACT, VERSION
from .sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .delivery.adapter.outgoing.files.migrations import layout_hint
from .delivery.adapter.outgoing.files.findings_files import FINDINGS_FILE, open_findings
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, evidence_dir, evidence_rel, location, place, PROFILE_FILE, read_profile,
    resolve_profile, set_places, shown)
from .delivery.adapter.outgoing.files.story_layout import find_story, story_kind
from .sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from .delivery.adapter.outgoing.tools.streams import follow_lines, tokens_of, usage_from
from .infrastructure.schedule import schedule_data, start_of
from .infrastructure.profile import ask_profile
from .delivery.application.profile.ask_profile import AskProfileQuery, Question
from .delivery.adapter.outgoing.claims.remote_claims import (
    claim_config_here, free_id, refresh_claims, release_claim)
from .delivery.adapter.outgoing.claims.checkout_claim import (
    claim, claim_path, listener_line, mark_listening, read_claim, release, session_owner)
from .delivery.adapter.outgoing.files.story_record import ignore_journals_in
from .delivery.adapter.outgoing.files.windows import freeze_all, mark_stage, mark_window
from .delivery.adapter.outgoing.files.usage_files import journal_usage
from .delivery.adapter.outgoing.files.owned_files import owned_end
from .delivery.adapter.outgoing.files.run_marks import run_stories
from .delivery.adapter.outgoing.git.worktrees import has_worktree, worktree_of
from .delivery.adapter.outgoing.files.owned_files import record_owned
from .delivery.adapter.outgoing.files.journal_files import journal_writer
from .delivery.adapter.outgoing.tools.agents import TOOL, TOOLS, unprobed_flags
from .delivery.adapter.outgoing.files.status_facts import (
    follow_newest, story_facts)
from .delivery.application.status import actions
from .delivery.application.status.actions import offered
from .delivery.application.status.show_status import ShowStatusQuery
from .delivery.application.status.show_story import ShowStoryQuery, UnknownStory
from .delivery.application.status.show_epic import ShowEpicQuery, UnknownEpic
from .delivery.application.status.show_help import ShowHelpQuery
from .delivery.application.status.texts import stamp_text
from .discovery.api import list_reports
from .delivery.adapter.outgoing.files.request_files import out_path
from .delivery.adapter.outgoing.files.story_files import names_story
from .delivery.application.decisions.list_decisions import ListDecisionsQuery
from .delivery.application.requests.list_requests import ListRequestsQuery
from .delivery.application.requests.pending import mark_pending
from .delivery.application.requests.pending_requests import PendingRequestsQuery
from .delivery.application.requests.retry_request import RetryRequestCommand
from .delivery.application.requests.take_back_request import TakeBackRequestCommand
from .delivery.application.requests.write_request import WriteRequestCommand
from .delivery.application.shared.requests import DuplicateRequest, KIND, KINDS, RequestRefused
from .building_blocks import UseCaseException
from .delivery.adapter.outgoing.claims.story_claims import claim_target
from .delivery.application.shared.story_repository import StoryNotFound
from .delivery.application.backlog.backfill_created import BackfillCreatedCommand
from .delivery.application.delivery.claim_story import ClaimStoryCommand
from .delivery.application.delivery.confirm_owned import ConfirmOwnedCommand, NothingToConfirm
from .delivery.application.shared.story_claims import Claim
from .delivery.application.delivery.deliver_by_hand import ChangesWhatHolds, ClaimedElsewhere, DeliverByHandCommand
from .delivery.application.delivery.prove_delivery import ProveDeliveryCommand
from .delivery.application.delivery.reopen_story import CheckoutHeld, NewWish, NoCorrection, NotCited, ReopenStoryCommand
from .delivery.domain.model.moment import Moment
from .delivery.domain.model.person import Person
from .delivery.domain.model.story import AlreadyDelivered, NotDelivered, NothingToDeliver, NothingToProve, StoryId
from .infrastructure import delivery as wiring
from .delivery.application.run.resolve_run_argument import ResolveRunArgumentQuery
from .delivery.application.status.show_refusals import ShowRefusalsQuery
from .delivery.domain.model.run_argument import ArgumentMeaning
from .delivery.adapter.incoming.cli import spec_delta_view as spec_delta_text
from .delivery.application.delivery.check_spec import CheckSpecQuery
from .delivery.application.delivery.show_spec_delta import ShowSpecDeltaQuery
from .delivery.application.delivery.take_back_delivery import TakeBackDeliveryCommand
from .delivery.adapter.outgoing.process import factory_process
from .web import service as web
from .delivery.adapter.outgoing.files.skeletons import contract_text, document_skeleton, files_skeleton, plan_skeleton
from .delivery.adapter.outgoing.git.worktree_steps import (
    integrate_finish, integrate_prepare, link_places, worktree_prepare, worktree_prune, worktree_remove)
from .delivery.adapter.outgoing.files.migrations import migrate_layout
from .runner import stage_names, stages_shell
from .delivery.adapter.incoming.runner.run_command import request_main, run_main, settle_command
from .delivery.adapter.incoming.cli.terminal import MARKS_MD, MARKS_TEXT, bold, decision_mark, dim, heading, how_lines, how_md, json_ready, paint, section, table_md, table_text, use_colour, view_width
from .delivery.adapter.incoming.cli.status_view import render_short_md, render_short_text, render_status_md, render_status_text, token_rows
from .delivery.adapter.incoming.cli.story_view import render_story_md, render_story_text, stage_caption, stage_cells
from .delivery.adapter.incoming.cli.epic_view import render_epic_md, render_epic_text
from .delivery.adapter.incoming.cli.schedule_view import schedule_lines, start_lines
from .delivery.adapter.incoming.cli.help_view import render_help_md, render_help_text


def resolve(epics, argument):
    """What `/factory-run <argument>` means — decided here, not by a model: one word naming a story is that
    story; one word naming none is an unknown id, never a new story (a typo stays a typo); more than one
    word is a wish, for the backlog skill to turn into a story; nothing is the backlog."""
    resolved = wiring.resolve_run_argument(".").execute(ResolveRunArgumentQuery(argument))
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


def discovery_model(cwd, epics):
    """Every discovery topic with its proposed epics — and which of them the backlog already holds — and its
    proposed description changes, as discovery says them; with what a person can do with each."""
    folder = location(read_profile(resolve_profile(None, cwd)), "discovery")
    model = list_reports(cwd, folder)
    for topic in model["topics"]:
        for proposal in topic["proposals"]:
            proposal["actions"] = [] if proposal["epic"] else offered(make_action(
                text="the proposal, written as an epic",
                skill=f"/factory-backlog epic {proposal['id']} --from {topic['report']}", label="make epic",
                primary=True))
        for change in topic["description_changes"]:
            change["actions"] = offered(make_action(text="the change, written into the description",
                                                    skill=f"/dca-describe {change['target']}: {change['change']}",
                                                    label="apply"))
        mark_pending([a for item in topic["proposals"] + topic["description_changes"] for a in item["actions"]],
                     pending_requests(cwd))
    return dict(project=os.path.basename(os.path.abspath(cwd)), store=model["store"], topics=model["topics"])


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
    model = wiring.list_decisions(cwd).execute(ListDecisionsQuery(story_id))
    records = model["records"]
    waiting = [r for r in records if r["state"] in ("open", "draft", "unreadable")]
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


def owned_confirm(runs, story_id, cwd="."):
    """The person's word that the story and its answers are as they want them after a stage changed them
    (`ConfirmOwnedUseCase`): the mark goes, what changed is journaled, and the story runs on from its files."""
    result = wiring.confirm_owned(cwd, runs).execute(ConfirmOwnedCommand(StoryId(story_id)))
    if isinstance(result, NothingToConfirm):
        print(f"owned: nothing to confirm for {story_id} — no stage changed its story or an answer")
    else:
        print(f"owned: {story_id} — {', '.join(result.parts)} confirmed as the person's; the story runs on")
    return 0

def refusals_report(runs, story_filter=None, fmt="text"):
    """`--refusals`: every story's refusals, form against substance — what a bench counts (`ShowRefusalsUseCase`)."""
    model = wiring.show_refusals(runs).execute(ShowRefusalsQuery(story_filter))
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


def make_action(text="", skill="", shell="", look="", label="", primary=False):
    """An action, every way — `actions.make_action`, with this project's stories to tell a story's id from a wish."""
    return actions.make_action(names_story, text=text, skill=skill, shell=shell, look=look, label=label,
                               primary=primary)


def status_model(cwd, epics, runs, live=False):
    """Where the factory stands — the status read model, over the project's files."""
    return wiring.show_status(cwd, epics, runs).execute(ShowStatusQuery(live))


def foreign_claim_lines(claims):
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


def story_spent(runs, story_id):
    """What a story cost so far, from the runner's journal — kept per story on disk, so a restart, a second session
    or a new run never resets it. An in-session run writes none."""
    if not os.path.isfile(os.path.join(evidence_dir(runs, story_id), "journal.tsv")):
        return ""
    used = journal_usage(runs, story_id)
    count = sum(e["invocations"] for e in used.values())
    tokens = sum(tokens_of(e) for e in used.values())
    return (f" · {count} stage invocation(s)" + (f", {tokens:,} tokens" if tokens else "")) if count else ""


def schedule(cwd, epics, runs, slots=None, busy=(), skip=()):
    """Print every story's state and the next one to run; return 0. The runner and the tests read these lines
    (`schedule_view.py`)."""
    data = schedule_data(cwd, epics, runs, slots, busy, skip)
    for line in schedule_lines(data, epics, {story: story_spent(runs, story) for story in data["order"]}):
        print(line)
    return 0


def start(cwd, epics, runs, story_id, slots=None):
    """Where the story starts, printed as `state:`, `start:` (a stage, or `none`) and `detail:`. Exit 2 for an
    unknown story."""
    found = start_of(cwd, epics, runs, story_id, slots)
    if found is None:
        print(f"factory: no story {story_id} under {epics}/", file=sys.stderr)
        return 2
    for line in start_lines(found):
        print(line)
    return 0


def status_brief(cwd, epics, runs, session_start=False):
    """Two lines: what is ready, what waits, who works, what it cost — for a session's start."""
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
    for line in foreign_claim_lines(view["claims"]):
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
    elif not view["rows"]:
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


def story_model(cwd, epics, runs, story_id, live=False):
    try:
        return wiring.show_story(cwd, epics, runs).execute(ShowStoryQuery(story_id, live))
    except UnknownStory:
        raise GateError(f"no story {story_id} under {epics}/") from None


def epic_model(cwd, epics, runs, epic_id, live=False):
    try:
        return wiring.show_epic(cwd, epics, runs).execute(ShowEpicQuery(epic_id, live))
    except UnknownEpic as unknown:
        raise GateError(f"no epic {epic_id} under {epics}/ — the epics: {', '.join(unknown.known) or 'none'}") from None


def help_model(cwd, epics, runs):
    return wiring.show_help(cwd, epics, runs).execute(ShowHelpQuery())


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


def backfill_created(cwd, epics):
    """WP-146: `created:` into every story and every epic that has none (`BackfillCreatedUseCase`). Prints what it
    wrote."""
    done = wiring.backfill_created(cwd, epics).execute(BackfillCreatedCommand())
    if not done.stories and not done.epics:
        print("backfill: every story and epic has its created: — nothing written")
        return 0
    print(f"backfill: created: written into {done.stories} stor{'y' if done.stories == 1 else 'ies'} and "
          f"{done.epics} epic{'' if done.epics == 1 else 's'}, from the commit that added each"
          + (f" — {done.from_file} not in git yet, from the file's own time" if done.from_file else ""))
    return 0

def story_command(run):
    """A story command's use case run; a story not found is the gate's error, as the readers raise it."""
    try:
        return run()
    except StoryNotFound as error:
        raise GateError(str(error)) from None


def reopen(cwd, runs, epics, story_id):
    """Take a delivered story back for a correction a human gave on looking at it (`ReopenStoryUseCase`)."""
    try:
        result = story_command(lambda: wiring.reopen_story(cwd, epics, runs).execute(
            ReopenStoryCommand(StoryId(story_id))))
    except NotDelivered:
        print(f"reopen: {story_id} is not delivered — a correction before delivery goes into the story, "
              f"and the schedule runs it from plan")
        return 1
    if isinstance(result, NoCorrection):
        print(f"reopen: {story_id} has no answered correction — /factory-decisions records the human's "
              f"correction as an acceptance record first")
    elif isinstance(result, CheckoutHeld):
        print(f"reopen: {', '.join(h.value for h in result.holders)} holds the checkout with unfinished code — one "
              f"story at a time; reopen {story_id} once it is delivered")
    elif isinstance(result, NotCited):
        rid = result.record.value
        print(f"reopen: the story does not cite {rid} — write the correction into it first (criteria and "
              f"an `answered:` line naming {rid})")
    elif isinstance(result, NewWish):
        print(f"reopen: after its acceptance the correction changes {', '.join(result.changed)} — that is a new "
              f"wish: a new story with `## Changed expectations`, not this one reopened")
    else:
        print(f"reopen: {story_id} taken back for {result.record.value} — it runs again from plan; the delivered pass "
              f"is kept as {shown(result.kept) if result.kept else 'nothing (no run folder)'}, and the story no "
              f"longer says delivered")
        return 0
    return 1


def deliver_by_hand(cwd, runs, epics, story_id, who, force=False):
    """A story a person built: `status: delivered`, `delivered:` (UTC), `delivered_by: hand:<who>`
    (`DeliverByHandUseCase`). Works where the factory never ran; `--prove` checks it later."""
    who = " ".join(str(who or "").split())
    if not who:
        print("deliver-by-hand: `--by <who>` names the person who delivers — the line is their claim")
        return 1
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        result = story_command(lambda: wiring.deliver_by_hand(cwd, epics, runs).execute(
            DeliverByHandCommand(StoryId(story_id), Person(who), Moment(stamp), force)))
    except AlreadyDelivered as error:
        print(f"deliver-by-hand: {story_id} is delivered already ({error.by.value or 'before delivered_by'}) — "
              f"a change of its behaviour is a new story with `## Changed expectations`")
        return 1
    except NothingToDeliver:
        print(f"deliver-by-hand: {story_id} is superseded — nothing to deliver")
        return 1
    if isinstance(result, ClaimedElsewhere):
        held = result.claim
        print(f"deliver-by-hand: {story_id} is claimed by {held.who} ({held.host}) since {held.since} — "
              f"another factory builds it; `--force` delivers it anyway")
        return 1
    if isinstance(result, ChangesWhatHolds):
        print(f"deliver-by-hand: {story_id} changes what holds ({', '.join(result.change.keys)} in "
              f"{shown(result.change.where)}) — the delta of a change is planned: `factory-cli.py --prove {story_id}` "
              f"once it is delivered, or run it through the factory")
        return 1
    if result.unproven.keys:
        print(f"deliver-by-hand: {len(result.unproven.keys)} criterion(s) into {shown(result.unproven.where)}, without "
              f"a test line — unproven until `--prove`")
    print(f"deliver-by-hand: {shown(find_story(epics, story_id))} carries `status: delivered`, `delivered: {stamp}`, "
          f"`delivered_by: hand:{who}` — delivered, claimed. Commit it with the trailer `Story: {story_id}`; "
          f"`factory-cli.py --prove {story_id}` turns the claim into proof.")
    return 0


#: A claim's exit codes, as the runner reads them.
CLAIM_EXIT = {Claim.OWN: 0, Claim.NO_REMOTE: 0, Claim.ELSEWHERE: 3, Claim.NEEDS_PERSON: 4}


def claim_command(cwd, runs, epics, story_id):
    """`--claim-story`: claim one story on the remote (WP-93, `ClaimStoryUseCase`). 0 claimed or own, 3 another
    factory has it, 4 needs a person; 0 and nothing pushed where the profile names no `claim_remote:`."""
    outcome = wiring.claim_story(cwd, epics, runs).execute(ClaimStoryCommand(StoryId(story_id)))
    for line in outcome.said:
        print(line)
    return CLAIM_EXIT[outcome.claim]

def undeliver_branch(cwd, runs, epics, story_id):
    """WP-93 F: a published branch whose merge request lost the race goes back to before its delivery
    (`TakeBackDeliveryUseCase`), so the integrate step merges the remote main line and the delivering function merges
    again under the new rules."""
    taken = wiring.take_back_delivery(cwd, runs, epics).execute(TakeBackDeliveryCommand(story_id))
    if taken is None:
        print(f"integrate: {story_id} has no published branch in this checkout")
        return 1
    print(f"integrate: {story_id}'s delivery taken back on its branch ({len(taken.spec_files)} spec file(s) as "
          f"{taken.main} has them) — the integrate step merges {taken.main} and delivers it again")
    return 0


def spec_check(cwd, runs, epics):
    """Story and spec agree (WP-98, `CheckSpecUseCase`): one line per disagreement; exit 1 when there is one."""
    checked = wiring.check_spec(runs, epics).execute(CheckSpecQuery())
    for line in checked.problems:
        print(f"spec: {line}")
    if not checked.problems:
        count = checked.delivered
        print(f"spec: every criterion of the {count} delivered stor{'y' if count == 1 else 'ies'} stands in its "
              "spec, and every spec file holds its shape")
    return 1 if checked.problems else 0


def prove(cwd, runs, epics, story_id):
    """A claimed delivery checked through the adopt path (`ProveDeliveryUseCase`): the story becomes
    `status: adopted`, its claim kept as one line of the evidence; the adopt gate then proves it and delivers it."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        result = story_command(lambda: wiring.prove_delivery(cwd, epics, runs).execute(
            ProveDeliveryCommand(StoryId(story_id), Moment(stamp))))
    except NotDelivered:
        print(f"prove: {story_id} is not delivered — `--prove` checks a claimed delivery; an open story runs as it is")
        return 1
    except NothingToProve:
        print(f"prove: {story_id} is delivered by the gate with its pass on record — nothing to prove")
        return 1
    if isinstance(result, CheckoutHeld):
        print(f"prove: {', '.join(h.value for h in result.holders)} holds the checkout with unfinished code — one "
              f"story at a time; prove {story_id} once it is delivered")
        return 1
    by = result.claim.by.value or "unknown"
    print(f"prove: {story_id} is `status: adopted` — the adopt path checks it (`factory.sh run --story {story_id}`); "
          f"the claim ({by}) is kept in {shown(result.claim_kept)}"
          + (f", the earlier pass as {shown(result.kept)}" if result.kept else ""))
    return 0


# --- the carriers the profile names ------------------------------------------------------

def answer(profile_path, question, **fields):
    """The profile's answer to one question, a line per item (`AskProfileUseCase`)."""
    print("\n".join(ask_profile(profile_path).execute(AskProfileQuery(question, **fields))))
    return 0


def follow_outputs(runs, story, process=None):
    """[(stage, path)] of one story's stage outputs in the order they began, or of one process (`builder`,
    `review-ddd`, `plan`, …) alone."""
    pattern = os.path.join(evidence_dir(runs, story), f"{process}.*.out" if process else "*.out")
    outs = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    return [(os.path.basename(p).split(".")[0], p) for p in sorted(outs, key=lambda p: (os.path.getmtime(p), p))]


def follow(runs, story, once, fmt, width, process=None, every=False, request=None):
    if request:
        # a request's process (WP-91): its one output beside the requests, read as a stage's
        path = out_path(request)
        newest = lambda: ("request", request, path) if os.path.isfile(path) else None
    else:
        newest = lambda: follow_newest(runs, story, process)
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
    found = newest()
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
            found = newest()
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


# --- the factory as a process of its own, and what a person asks of it (WP-91) -----------------------------------------
def placed(profile_arg=None):
    """The places as the profile names them, for a command that reads no other option."""
    set_places(read_profile(resolve_profile(profile_arg, os.getcwd())))


def request_command(argv):
    """`factory.sh request <kind> [<target>…] [<words>…] [--story|--epic|--record|--topic|--proposal <id>]
    [--option <key>] [--from <stage>] [--by <who>] [--settle]` — `-` as the words reads them from stdin. `--settle`
    settles it at once where the factory can, writing no request (exit 3 where a skill must work it)."""
    parser = argparse.ArgumentParser(prog="factory.sh request",
                                     description="write one request the factory works before its next story")
    parser.add_argument("kind", choices=[k.name for k in KINDS])
    parser.add_argument("rest", nargs="*", help="the target the kind names, then the person's words")
    parser.add_argument("--story")
    parser.add_argument("--epic")
    parser.add_argument("--record")
    parser.add_argument("--topic")
    parser.add_argument("--proposal")
    parser.add_argument("--option", help="an answer's option key, a correction's reason code")
    parser.add_argument("--from", dest="start", help="with run: the stage the story starts at")
    parser.add_argument("--by", help="who asks (default: git user.name)")
    parser.add_argument("--settle", action="store_true",
                        help="settle it now where the factory can, no request written; exit 3 where a skill must work it")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    placed()
    kind, rest = KIND[args.kind], list(args.rest)
    fields = {key: getattr(args, key) for key in ("story", "epic", "record", "topic", "proposal", "option")
              if getattr(args, key)}
    if args.start:
        fields["from"] = args.start
    for spec in kind.keys:
        names = spec.split("|")
        if any(name in fields for name in names) or not rest:
            continue
        if kind.name == "release":                  # every id given: the stories, or the one epic
            fields[names[0]] = " ".join(rest)
            rest = []
        else:
            fields[names[0]] = rest.pop(0)
    words = " ".join(rest)
    if words == "-":
        words = sys.stdin.read()
    if args.settle:
        return settle_press(kind.name, fields, words, args.by or "", args.format)
    try:
        written = wiring.write_request(os.getcwd()).execute(WriteRequestCommand(kind.name, fields, words, args.by or ""))
        request_id, path = written.id, written.path
    except DuplicateRequest as same:
        print(f"factory: {same}")
        return 0
    except (UseCaseException, GateError) as error:
        print(f"factory: request refused — {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(dict(id=request_id, path=shown(path))))
    else:
        print(f"factory: request {request_id} written ({shown(path)}) — the factory works it before its next story")
    return 0


def settle_press(kind_name, fields, words, by, fmt):
    """`request … --settle`: settled now, or exit 3 — the caller then runs the action's skill, as before."""
    try:
        # the runner's own lines go to stderr where the caller reads one JSON object from stdout
        with contextlib.redirect_stdout(sys.stderr) if fmt == "json" else contextlib.nullcontext():
            code, request_id, commit = settle_command(os.getcwd(), kind_name, fields, words, by)
    except DuplicateRequest as same:
        print(json.dumps(dict(id=same.existing, settled=False, queued=True)) if fmt == "json" else f"factory: {same}")
        return 0
    except (UseCaseException, GateError) as error:
        print(f"factory: request refused — {error}", file=sys.stderr)
        return 2
    if fmt == "json":
        print(json.dumps(dict(id=request_id, settled=code == 0, commit=commit)))
    elif code == 0:
        print(f"factory: {kind_name} settled by the factory, no tool" + (f" — committed {commit}" if commit else ""))
    elif code == 3:
        print(f"factory: {kind_name} needs its skill — nothing written")
    return code


def requests_command(argv):
    parser = argparse.ArgumentParser(prog="factory.sh requests", description="the requests and their state")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--drop", metavar="ID", help="take a request back (not while it runs)")
    parser.add_argument("--retry", metavar="ID", help="queue a failed request again")
    args = parser.parse_args(argv)
    placed()
    try:
        if args.drop:
            wiring.take_back_request(os.getcwd()).execute(TakeBackRequestCommand(args.drop))
            print(f"factory: request {args.drop} dropped")
            return 0
        if args.retry:
            wiring.retry_request(os.getcwd()).execute(RetryRequestCommand(args.retry))
            print(f"factory: request {args.retry} queued again")
            return 0
    except (RequestRefused, OSError) as error:
        print(f"factory: {error}", file=sys.stderr)
        return 2
    return requests_view(os.getcwd(), args.format)


def pending_requests(cwd):
    """The requests not done — what a view's press may be pending on."""
    return wiring.pending_requests(cwd).execute(PendingRequestsQuery()).requests


def request_counts(cwd):
    """The requests by state."""
    return wiring.list_requests(cwd).execute(ListRequestsQuery())["counts"]


def requests_view(cwd, fmt="text"):
    """`factory.sh requests`: every request with its state, oldest first."""
    model = wiring.list_requests(cwd).execute(ListRequestsQuery())
    if fmt == "json":
        print(json.dumps(model, indent=2, ensure_ascii=False))
        return 0
    rows = model["requests"]
    if not rows:
        print(f"requests: none — `factory.sh request <kind> …` writes one ({model['store']})")
        return 0
    for row in rows:
        extra = row["error"] or (f"asks: {row['record']}" if row["record"] else "") or \
            (f"{row['worker']} since {row['started']}" if row["state"] == "running" else "")
        print(f"{row['id']}  {row['state']:<8} {row['kind']:<9} {row['target']}  ({row['by']})"
              + (f" — {extra}" if extra else ""))
    print("requests: " + ", ".join(f"{n} {s}" for s, n in model["counts"].items() if n))
    return 0


def up_command(argv):
    parser = argparse.ArgumentParser(prog="factory.sh up", description="start the factory in the background")
    parser.add_argument("--serve", action="store_true", help="the page too")
    parser.add_argument("--port", type=int)
    parser.add_argument("--by")
    args, run_args = parser.parse_known_args(argv)
    allowed = {"--tool", "--parallel", "--interval", "--max-stages", "--story-budget", "--keep-going",
               "--separate-stages", "--shared-builder", "--shared-verifier"}
    stray = [a for a in run_args if a.startswith("-") and a not in allowed]
    if stray:
        print(f"factory: up takes no {' '.join(stray)} — the runner's flags it passes on: {' '.join(sorted(allowed))}",
              file=sys.stderr)
        return 2
    placed()
    return factory_process.up(os.getcwd(), run_args, args.serve, args.port, args.by or "")


def down_command(argv):
    parser = argparse.ArgumentParser(prog="factory.sh down", description="end the factory after its running stage")
    parser.add_argument("--now", action="store_true", help="interrupt the running stage too")
    parser.add_argument("--no-wait", action="store_true", help="say stop and return at once")
    parser.add_argument("--by")
    args = parser.parse_args(argv)
    placed()
    return factory_process.down(os.getcwd(), args.now, not args.no_wait, args.by or "")


def serve_command(argv):
    parser = argparse.ArgumentParser(prog="factory.sh serve", description="the factory's page, on this machine alone")
    parser.add_argument("--port", type=int)
    parser.add_argument("--open", action="store_true", help="open it in the browser")
    parser.add_argument("--background", action="store_true", help="start it detached and return")
    parser.add_argument("--by-up", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    placed()
    if args.by_up:
        return web.serve_here(os.getcwd(), args.port, by_up=True)
    served = factory_process.running_page(os.getcwd())
    if served:
        factory_process.say(f"the page runs already — {served['url']}")
        return 0
    if args.background:
        return factory_process.start_page(os.getcwd(), args.port)
    return web.serve_here(os.getcwd(), args.port, args.open)


def worker_command(argv):
    parser = argparse.ArgumentParser(prog="factory-cli.py --worker")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    placed()
    info = factory_process.worker(os.getcwd())
    print(json.dumps(info) if args.format == "json" else factory_process.worker_line(info))
    return 0


LIFECYCLE = {"--request": request_command, "--requests": requests_command, "--work-request": request_main,
             "--up": up_command, "--down": down_command, "--serve": serve_command, "--worker": worker_command}


def main(argv):
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
    parser.add_argument("--window", choices=tuple(SHARED_WINDOWS), help="with --stages: the stages that shared process carries")
    parser.add_argument("--shell", action="store_true", help="with --stages: the stage and the tool table as bash "
                                                                "assignments")
    parser.add_argument("--tool-probe", metavar="TOOL", choices=tuple(TOOL),
                        help="the flags of the tool's record its binary's help does not name: one a stage needs "
                             "(exit 1), an isolation flag only (named, exit 0), none (exit 0), no binary (exit 3)")
    parser.add_argument("--place", metavar="KEY",
                        help="where the factory reads KEY (product, tech, domain, epics, runs), from the profile or its default")
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
        print(" ".join(stage_names(args.window, args.every)))
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
    if args.get is not None:
        return answer(profile_path, Question.VALUE, key=args.get)
    if args.command_heads:
        return answer(profile_path, Question.COMMAND_HEADS)
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
        view = wiring.show_spec_delta(args.runs, args.epics).execute(ShowSpecDeltaQuery(args.spec_delta))
        print(spec_delta_text.render(view, args.format))
        return 0
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
    if args.ignore_journals:
        if ignore_journals_in(cwd, evidence_rel()):
            print(f"journals: .gitignore lets the story journals ({evidence_rel()}/<story>/journal.tsv) into git — the "
                  f"rest of the pipeline's folder stays out")
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
        return owned_confirm(args.runs, args.owned_confirm, cwd)
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
