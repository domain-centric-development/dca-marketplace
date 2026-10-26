"""Story gate — the deterministic part of a factory run: what decides.

Reads the backlog (markdown with front matter) and the stack profile, then checks what a stage may
not decide for itself. Exit code 0 means the stage may proceed. What only *shows* the pipeline —
status, help, usage, session logs, the checkout claim, the schedule — is `factory-cli.py` beside this
file; a flag that moved there is handed over, so an older caller still gets its answer.

    story-gate.py --story <id> --stage <plan|test|build|tidy|document|adopt> [options]
    story-gate.py --change [--staged] [--checks <c>]   the profile's checks outside a story; --staged
                                                       checks what the commit contains (the hook, CI)
    story-gate.py --parity <config>                    every implementation's reports prove every
                                                       mandatory scenario of a scenario contract
    story-gate.py --check-backlog [--story <id>]       the plan gate's backlog checks over every story
                                                       that is not done; exit 1 when one is refused
    story-gate.py --project                            the project description (product and technical)
                                                       alone; exit 3 while a part is missing, 1 when
                                                       one is incomplete
    story-gate.py --check-contract                     the profile's contract and model keys alone
    story-gate.py --record-base | --record-changes <stage>   the tree a story's diff is taken against,
                                                       and what a stage changed (with --story)

Options:
    --epics <dir>       where the epics and stories are (default: the profile's `epics:`, else product/epics)
    --runs <dir>        the run artefacts (default: the profile's `runs:`, else .dca-factory/runs)
    --root <dir>        the project's root (default: .)
    --profile <file>    stack profile (default: dca-factory.profile.yaml in the project root)
    --json              additionally print the result as one JSON object

Checks by stage:
    plan   epic completeness (intent, goal, metric, domain_contact), story well-formed and not
           left in draft, its bounded context present in the context map, the round limit not
           reached, and a note when the project instructions are too large for a tool to load
    test   epic + every acceptance criterion mapped to a test in <runs>/<story>/tests.md,
           the test exists in the sources, the test sources compile, every mapped test is red.
           Which selectors were red is recorded in <evidence>/<story>/.tests-red
    build  epic + mapping + every mapped test is green **and was recorded red by the test stage**,
           every test command the profile's `required:` names, run whole (the stories before this
           one still hold), plus every extra check the profile declares for this stage
           (architecture suite, formatter, …). Without the record the green run is skipped and named, never taken as
           evidence: a runner that matched no test at all exits 0 exactly like a passing one. Every file
           the plan's `## Files` says `new` is there, every one it says `removed` is gone (contract 22)
    tidy   the same as build: nothing the refactor touched may have changed what the code does
    document  every path, file and identifier the document stage claims actually exists, every
           row of its glossary table names where its definition came from, and every term the plan
           proposed has landed in a glossary
    change the profile's compile, test, architecture and format commands against the working tree
           (or, with --staged, the Git index — refused when the working tree differs from it). A test
           command passes only when its reports show executed cases. The profile's `required:` line
           makes checks mandatory: a required check that is not declared, not run or ran nothing fails
    test, build, tidy  a test file that existed before the story (recorded by the plan gate) still
           holds every line it had; a changed or removed one needs an answered decision of stage test
    every stage  the story's decision records in its folder (`<story>/decisions/`): a `## needs-human`
           section names one, an open one stops the story, an answered one is applied by the
           stage that asked and then stamped `## Applied` here

Where things are — one owner per place: `product/` is the people's (the description, the epics with
their stories, each story a folder with its decisions), `.agents/factory/` is the installed pipeline,
the profile at the root is the person's, and `.dca-factory/` is the run's protocol (hand-overs, marks,
the journal), disposable at any time: what is delivered stands in the story itself (`status:
delivered`, written by the gate alone), so deleting the run folder loses history, never state.

A command the profile does not declare is skipped and named, never failed.
"""

import argparse
import contextlib
import json
import os
import subprocess
import sys
from .contract import CONTRACT, VERSION
from .sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .delivery.adapter.outgoing.files.migrations import layout_hint
from .delivery.adapter.outgoing.pipeline.stage_rows import STAGE, STAGES
from .delivery.adapter.outgoing.files.story_layout import (
    find_story, story_folder)
from .sharedkernel.adapter.outgoing.profile.profile_files import (
    location, place, PROFILE_FILE, read_profile,
    resolve_profile, set_places)
from .delivery.application.description.check_description import CheckDescriptionCommand
from .discovery.api import check_report
from .infrastructure.description import check_description
from .infrastructure.gate import check_backlog as backlog_use_case, check_change, check_parity, stage_run
from .delivery.application.delivery.check_change import CheckChangeCommand
from .delivery.application.delivery.check_parity import CheckParityCommand
from .delivery.application.backlog.check_backlog import CheckBacklogCommand
from .delivery.domain.model.story import StoryId
from .sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from .delivery.adapter.outgoing.files.snapshots import (
    record_base, record_changes)
from .delivery.adapter.outgoing.files.owned_files import owned_end
from .delivery.adapter.outgoing.files.run_marks import (
    backlog_digest, step_open)
from .delivery.adapter.outgoing.files.owned_files import observe_writes, record_owned
from .delivery.adapter.outgoing.files.journal_files import journal_append
from .delivery.domain.model.verdict import FindingState
from .delivery.domain.service.profile_checks import ProfileChecks
from .delivery.application.delivery.check_stage import (
    run_checks, run_passed, Verdict)
from .delivery.adapter.outgoing.files.stage_evidence_files import StageEvidenceFiles
from .delivery.adapter.outgoing.build.commands import MISSING_TOOLS
from .delivery.adapter.outgoing.files.criteria_files import criteria_of


def check_contract(result, profile):
    """The profile's contract and its unknown keys (`ProfileChecks.contract`)."""
    result.take(ProfileChecks.contract(StageEvidenceFiles(".", "", "", profile)))


def check_models(result, profile):
    """The profile's model keys, each bound to a tool (`ProfileChecks.models`)."""
    result.take(ProfileChecks.models(StageEvidenceFiles(".", "", "", profile)))


#: Where the method keeps the project's conventions; `verify_command:` there is the architecture command the
#: profile's `architecture:` was copied from at setup. Two files, two owners — the method's and the factory's —
#: and nothing merges them, so the pair is compared and a difference is named.
def check_project(result, cwd, profile):
    """The two mandatory parts of the project description — the description feature's check, said as the gate
    says its checks."""
    checked = check_description(cwd, profile).execute(CheckDescriptionCommand())
    for verdict in checked.verdicts:
        getattr(result, verdict.state)(verdict.part, verdict.said)
    return checked.complete


def check_backlog(cwd, epics, profile, only=None):
    """The plan gate's backlog checks over every story that is not done, or over `only` (`CheckBacklogUseCase`),
    said one line per finding that did not pass."""
    if layout_hint(cwd, profile):
        print(f"gate:note layout — {layout_hint(cwd, profile)}")
    checked = backlog_use_case(cwd, epics, profile).execute(CheckBacklogCommand(StoryId(only) if only else None))
    for verdict in checked.verdicts:
        for finding in verdict.findings:
            if finding.state is not FindingState.PASS:
                print(f"gate:{finding.state.value} {verdict.label.value} {finding.check.value} — {finding.said.value}")
    refused = [label.value for label in checked.refused]
    if not checked.checked and not refused:
        if only:
            print(f"backlog: no story {only} to check under {epics}/ (not there, delivered or superseded)")
            return 1
        print(f"backlog: no story to check under {epics}/")
        return 0
    print(f"backlog: {checked.checked} story(ies) checked" + (f", refused: {', '.join(refused)}" if refused
                                                             else " — every one holds for the plan gate"))
    return 1 if refused else 0


class Result(Verdict):
    """A gate run's verdict, as the gate reports it."""

    def report(self, story_id, stage, as_json, brief=False):
        if MISSING_TOOLS and not any(check == "environment" for _s, check, _m in self.entries):
            tools = sorted({tool for tool, _c in MISSING_TOOLS})
            self.fail("environment", f"the shell running the gate found no {', '.join(f'`{t}`' for t in tools)} "
                                     f"(`{MISSING_TOOLS[0][1]}`) — the process that runs the gate lacks a tool on "
                                     f"its PATH. No stage can fix that: put it on the PATH, then run the story again")
        if brief:
            # A stage that runs its own gate reads the report into its context: what passed is one line
            # there, what did not stays verbatim — the fail line is the stage's next instruction. The
            # runner's own runs keep the long form, in the report it files for the observer.
            passed = [check for state, check, _ in self.entries if state == "pass"]
            if passed:
                names = sorted(set(passed))
                print(f"gate:pass {len(passed)} check(s) — {', '.join(names)}")
            for state, check, message in self.entries:
                if state != "pass":
                    print(f"gate:{state} {check} — {message}")
        else:
            for state, check, message in self.entries:
                print(f"gate:{state} {check} — {message}")
        skipped = [check for state, check, _ in self.entries if state == "skip"]
        if skipped:
            print(
                f"gate:note stage {stage} ran without {', '.join(sorted(set(skipped)))} — "
                f"a green run here does not cover them"
            )
        verdict = "fail" if self.failed else "wait" if self.waiting else "pass"
        print(f"gate:{verdict} {stage}" if story_id == stage else f"gate:{verdict} story {story_id} stage {stage}")
        if as_json:
            print(
                json.dumps(
                    {
                        "story": story_id,
                        "stage": stage,
                        "verdict": verdict,
                        "checks": [
                            {"state": s, "check": c, "message": m}
                            for s, c, m in self.entries
                        ],
                    },
                    indent=2,
                )
            )
        return 1 if self.failed else 3 if self.waiting else 0


#: The flags that moved to the CLI beside this file. An older caller — a hook, an instruction file, a
#: skill of an earlier release — is handed over rather than refused; the gate itself does no showing.
MOVED_TO_CLI = frozenset((
    "--list-decisions", "--claim", "--release", "--listening", "--status", "--brief", "--part", "--live",
    "--session-start", "--help-view", "--usage", "--total", "--usage-from", "--usage-model",
    "--window-start", "--window-end", "--stage-start", "--stage-end", "--session-log", "--reopen",
    "--kind", "--resolve", "--start", "--schedule",
))


def hand_over_to_cli(argv):
    """Run the CLI beside this file with the same arguments, where a moved flag is asked of the gate."""
    cli = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "factory-cli.py")
    if not os.path.isfile(cli):
        print(f"gate:fail cli — {' '.join(a for a in argv if a in MOVED_TO_CLI)} moved to factory-cli.py, "
              f"which is not beside this gate; 'factory.sh update' puts it there", file=sys.stderr)
        return 2
    completed = subprocess.run([sys.executable, cli, *argv])
    return completed.returncode


def main(argv):
    # `--brief` is the gate's own beside `--stage` (a stage's compact report); alone it is the status's, moved.
    moved = MOVED_TO_CLI - ({"--brief"} if "--stage" in argv else set())
    if any(token.split("=", 1)[0] in moved for token in argv):
        return hand_over_to_cli(argv)
    parser = argparse.ArgumentParser(add_help=True, description="story gate")
    parser.add_argument(
        "--version", action="version",
        version=f"story-gate {VERSION} (file contract {CONTRACT})",
    )
    parser.add_argument("--story")
    parser.add_argument(
        "--stage",
        choices=tuple(s.name for s in STAGES if s.gated),
    )
    parser.add_argument("--change", action="store_true",
                        help="run the profile's checks outside a story and exit")
    parser.add_argument("--staged", action="store_true",
                        help="with --change: check the Git index, refuse when the working tree differs")
    parser.add_argument("--checks", help="with --change: only these checks (compile test architecture format)")
    parser.add_argument("--record-suites", action="store_true",
                        help="the runner's gates: record every passing suite run in the evidence folder's suites.tsv, signed "
                             "with FACTORY_SUITES_KEY, and reuse the runner's own record on an unchanged tree")
    parser.add_argument("--parity", metavar="CONFIG",
                        help="check every implementation's reports against a scenario contract and exit")
    parser.add_argument("--check-contract", action="store_true",
                        help="check the profile's contract and model keys alone (the runner, before its first stage)")
    parser.add_argument("--record-base", action="store_true",
                        help="with --story: record the tree the story's diff is taken against (the first stage)")
    parser.add_argument("--owned", nargs="+", metavar="start|end WINDOW [EXIT]",
                        help="with --story: a stage window's start and end — the person's parts recorded and compared, "
                             "the hand-overs it wrote journaled; EXIT is the window's tool exit (0 by default)")
    parser.add_argument("--record-changes", metavar="STAGE",
                        help="with --story: write changed-<stage>.txt, changed.txt and story.diff from the snapshots")
    parser.add_argument("--project", action="store_true",
                        help="check the project description — product and technical — alone, and exit")
    parser.add_argument("--check-discovery", metavar="TOPIC",
                        help="check the discovery report of one topic (product/discovery/<topic>/) and exit")
    parser.add_argument("--check-backlog", action="store_true",
                        help="the plan gate's backlog checks over every story that is not done (or --story), "
                             "writing nothing, and exit")
    parser.add_argument("--epics", help="where the epics and stories are (default: the profile's `epics:`, else product/epics)")
    parser.add_argument("--runs", help="the run artefacts (default: the profile's `runs:`, else .dca-factory/runs)")
    parser.add_argument("--profile", help=f"the stack profile (default: {PROFILE_FILE} at the project root)")
    parser.add_argument("--root", default=".", help="the project's root directory")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--brief", action="store_true",
                        help="with --story --stage: the checks that passed as one line, the rest verbatim "
                             "(for a stage that runs its own gate and reads the report)")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.root)
    os.chdir(cwd)
    # Every place once: the flag, else the profile's key, else the default. None reads an older layout —
    # the gate names the move instead.
    set_places(read_profile(resolve_profile(args.profile, cwd)), epics=args.epics, runs=args.runs)
    args.epics, args.runs = place("epics"), place("runs")
    if args.check_backlog:
        return check_backlog(cwd, args.epics, read_profile(resolve_profile(args.profile, cwd)), args.story)
    if args.check_contract:
        result = Result()
        profile = read_profile(resolve_profile(args.profile, cwd))
        check_contract(result, profile)
        check_models(result, profile)
        for state, check, message in result.entries:
            if state != "pass":
                print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else 0
    if args.owned:
        if not args.story:
            parser.error("--owned needs --story")
        if args.owned[0] == "start":
            record_owned(args.runs, args.story)
            return 0
        if len(args.owned) < 2:
            parser.error("--owned takes start|end and the window's name")
        return owned_end(args.runs, args.story, args.owned[1], args.owned[2] if len(args.owned) > 2 else "0")
    if args.record_base or args.record_changes:
        if not args.story:
            parser.error("--record-base/--record-changes need --story")
        if args.record_base:
            record_base(cwd, args.runs, args.story)
        if args.record_changes:
            record_changes(cwd, args.runs, args.story, args.record_changes)
        return 0
    if args.check_discovery:
        result = Result()
        try:
            folder = location(read_profile(resolve_profile(args.profile, cwd)), "discovery")
            checked = check_report(cwd, folder, args.check_discovery)
            (result.ok if checked.passed else result.fail)("discovery", checked.said)
        except GateError as error:
            result.fail("discovery", str(error))
        for state, check, message in result.entries:
            print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else 0
    if args.project:
        result = Result()
        try:
            profile = read_profile(resolve_profile(args.profile, cwd))
            check_project(result, cwd, profile)
            if layout_hint(cwd, profile):
                result.note("layout", layout_hint(cwd, profile))
        except GateError as error:
            result.fail("project", str(error))
        for state, check, message in result.entries:
            print(f"gate:{state} {check} — {message}")
        return 1 if result.failed else (3 if any(e[0] == "note" for e in result.entries) else 0)
    if args.change or args.parity:
        result, label = Result(), "change" if args.change else "parity"
        try:
            if args.change:
                profile = read_profile(resolve_profile(args.profile, cwd))
                if layout_hint(cwd, profile):
                    result.fail("layout", layout_hint(cwd, profile))
                check_contract(result, profile)
                changed = check_change(cwd, profile).execute(CheckChangeCommand(args.staged, args.checks))
                result.entries += changed.entries
                result.flaky += changed.flaky
            else:
                result.take(check_parity().execute(CheckParityCommand(args.parity)))
        except GateError as error:
            result.fail("gate", str(error))
        return result.report(label, label, args.json)
    if not args.story or not args.stage:
        parser.error("--story and --stage are required (or --change, --parity, --check-backlog, --project; "
                     "status, schedule, usage and the inbox are factory-cli.py's)")
    result = Result()
    hint = layout_hint(cwd, read_profile(resolve_profile(args.profile, cwd)))
    if hint:
        # Not a note: a profile or a story the gate does not read would leave every check skipped and named,
        # and a green run that covers nothing.
        result.fail("layout", hint)
    story_path = story_id = None
    try:
        story_path = find_story(args.epics, args.story)
        front, body = read_front_matter(story_path)
        story_id = str(front.get("id") or os.path.basename(story_folder(story_path)))
        observe_writes(args.runs, story_id)
        criteria = criteria_of(story_path, body, front)
        run = stage_run(lambda run: close_record(run), result=result, args=args, cwd=cwd, runs=args.runs, stage=STAGE[args.stage], story_id=story_id,
                      story_path=story_path, front=front, body=body, criteria=criteria,
                      profile=read_profile(resolve_profile(args.profile, cwd)))
        run_checks(run)
    except GateError as error:
        result.fail("gate", str(error))
        return journal_gate(result, args, story_id, story_path, result.report(args.story, args.stage, args.json,
                                                                              args.brief))
    if not result.failed:
        run_passed(run)
    return journal_gate(result, args, story_id, story_path, result.report(story_id, args.stage, args.json, args.brief))


def close_record(run):
    """A delivery's last events, journaled before its commit: the gate's passing verdict and the end of the runner's
    integrate step it runs in, where that step is open. The commit then holds the story's record whole — a delivered
    story leaves no journal line behind in the checkout. A commit that fails after it is journaled as the refusal."""
    journal_append(run.runs, run.story_id, "gate", run.args.stage, *gate_fields(run.result, run.args, 0))
    run.result.closed = True
    if step_open(run.runs, run.story_id, "integrate"):
        journal_append(run.runs, run.story_id, "step-end", "integrate", "exit=0")


def gate_fields(result, args, code):
    """A gate run's event fields: `exit=<code> fail=<checks> by=<who>` — the runner's (`by=runner`, the one that
    signs suites), a stage's own under a runner (`by=<stage>`), a session's (`by=session`)."""
    failed = sorted({check for state, check, _ in result.entries if state == "fail"})
    by = "runner" if args.record_suites else (os.environ.get("FACTORY_STAGE") or "stage") \
        if os.environ.get("FACTORY_WORKER") else "session"
    fields = [f"exit={code}"] + ([f"fail={','.join(failed)}"] if failed else []) + [f"by={by}"]
    if result.flaky:
        fields.append(f"flaky={','.join(dict.fromkeys(result.flaky))}")
    return fields


def journal_gate(result, args, story_id, story_path, code):
    """Every gate run over a story is an event (`gate_fields`); a delivery journaled its passing verdict before its
    commit (`close_record`). The plan gate's refusal carries the backlog's digest, so a repair is seen without a
    clock."""
    if not story_id or code == 0 and result.closed:
        return code
    fields = gate_fields(result, args, code)
    if args.stage == "plan" and code == 1 and story_path:
        fields.append(f"backlog={backlog_digest(story_path)}")
    with contextlib.suppress(OSError):
        journal_append(args.runs, story_id, "gate", args.stage, *fields)
    return code
