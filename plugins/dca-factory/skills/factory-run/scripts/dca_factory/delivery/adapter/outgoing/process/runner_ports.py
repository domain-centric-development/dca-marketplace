"""The ports of a run's use cases on the runner's process: a story's stages (`RunnerStages` for `RunStoryUseCase`),
its integration (`RunnerIntegration` for `IntegrateStoryUseCase`), the backlog (`RunnerBacklog` for
`RunBacklogUseCase`), a request's skill (`RunnerRequestSkill`). Each asks the run (`runner_process.Run`) for what it
holds."""

from __future__ import annotations

import os
import time
import typing
from ..git.worktree_steps import integrate_prepare, worktree_prune
from .....sharedkernel.adapter.outgoing.profile.profile_files import place, shown
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..claims.remote_claims import claim_config_here
from ..git.integration import lost_text, main_tests_lost
from ..tools.agents import TOOL
from ..tools.tool_processes import TIMED_OUT, utc
from ..files.request_files import out_path, prune_outputs, stamp_utc
from ..files.decision_record_files import project_record_path
from ....application.shared.request_skill import SkillRun
from ....application.shared.backlog_schedule import ScheduleRead
from ....domain.model.stage import StageName, StoryKind
from ....domain.model.story_state import GateReport, Rounds, VerdictWord
from ..files.decision_record_files import request_records
from ....application.shared.requests import KIND, Kind, Request
from ....application.shared.backlog_worker import Child
from ....application.shared.story_integration import Lost
from .runner_process import Run

#: The cli flags a skill run for a request may call (WP-91): what the dialog skills read and record with — never one
#: that starts a run, a request, the factory or its page (`--run`, `--work-request`, `--request`, `--up`, `--serve`).
REQUEST_CLI_FLAGS = ("--contract", "--free-id", "--window-start", "--window-end", "--list-decisions", "--spec-delta",
                     "--spec-check", "--findings", "--reopen", "--owned-confirm", "--status", "--discover-list",
                     "--help-view", "--journal-line")


def newer(path: str, than: str) -> bool:
    """`[ path -nt than ]`: path exists and is newer, or than does not exist."""
    if not os.path.exists(path):
        return False
    return not os.path.exists(than) or os.path.getmtime(path) > os.path.getmtime(than)


class RunnerRequestSkill:
    """A request's skill as the runner starts it: the prompt that names the skill, the request's arguments, the rules
    for a skill run for a request and where things are; the shell narrowed to what the dialog skills read and record
    with; the tool's process, its usage journaled and booked to the request."""

    def __init__(self, run: Run) -> None:
        self._run = run

    def tool_for(self, unit: str, given: str) -> str:
        return self._run.tools.tool_for(unit, given)

    @staticmethod
    def known(tool: str) -> bool:
        return bool(os.environ.get("FACTORY_TOOL_CMD")) or tool in TOOL

    def run(self, request: Request, kind: Kind, unit: str, tool: str) -> SkillRun:
        run = self._run
        run.tool_in_flight = tool
        raw = out_path(request["id"])
        os.makedirs(os.path.dirname(raw), exist_ok=True)
        run.tools.allowed_override = self.request_allowed()
        started = time.time()
        run.request_in_flight = request["id"]
        try:
            code = run.invoke(tool, self.request_prompt(request, tool), raw, unit, None)
        finally:
            run.tools.allowed_override = None
            run.request_in_flight = ""
        measured = run.processes.record_usage(None, unit, tool, raw, int(time.time() - started), request["id"])
        run.cases.book_request_cost(run, request["id"], tool, measured)
        prune_outputs()
        return SkillRun(code, code == TIMED_OUT, shown(raw))

    def request_skill(self, kind: Kind) -> str:
        """The skill a request's kind runs, as its prompt names it."""
        if kind.skill == "description":
            return ("the project's description skill — the skill whose description says it writes the project "
                    "description, `dca-describe` in a DCA project —")
        return f"the {kind.skill} skill"

    @staticmethod
    def request_arguments(request: Request) -> str:
        """The arguments a session would give the skill for this request — the same words the cockpit sends."""
        kind, words, option = request["kind"], request.get("words", ""), request.get("option", "")
        story, record = request.get("story", ""), request.get("record", "")
        if kind in ("wish", "discover", "describe"):
            return words
        if kind == "release":
            return f"release {request.get('story') or request.get('epic')}"
        if kind in ("stories", "journey"):
            return f"{kind} {request['epic']}"
        if kind == "epic-from":
            return f"epic {request['proposal']} --from {request['report']}"
        if kind == "answer":
            given = option or words
            why = f" — rationale: {words}" if option and words else ""
            return f"{story + ' ' if story else ''}{record}: answer {given}{why}"
        if kind == "accept":
            return f"{story} {record}: answer accepted"
        if kind == "correct":
            code = f"{option}: " if option else ""
            return f"{story}{' ' + record if record else ''}: correction: {code}{words}"
        return words

    def request_prompt(self, request: Request, tool: str) -> str:
        kind = KIND[request["kind"]]
        reference = next((f"{d}/factory-run/reference/requests.md" for d in self._run.skill_dirs(tool)
                          if os.path.isfile(f"{d}/factory-run/reference/requests.md")), "")
        if not reference:
            own = os.path.abspath(os.path.join(self._run.scripts, "..", "reference", "requests.md"))
            reference = own[len(self._run.pwd) + 1:] if own.startswith(self._run.pwd + "/") else own
        by = request.get("by") or "a person"
        topic_file = shown(project_record_path(request["id"], request["kind"]))
        lines = [
            f"Apply {self.request_skill(kind)} with the arguments: {self.request_arguments(request)}",
            f"This is request {request['id']} of the factory, written by {by} at {request.get('asked', '?')}. You run "
            f"headless: no person reads this session and nobody answers in it. The rules for a skill run for a request "
            f"are in {reference} — read them first.",
            f"In short: the request is {by}'s confirmation of what it names — write it as theirs (`by: {by}`), as the "
            f"skill would on their confirmation. Where the skill would ask the person and the files do not settle it, do "
            f"not guess and do not ask here: write the question as one decision record with `request: {request['id']}` "
            f"in its front matter and its file name without `.md` as its `id:` — beside the story it concerns, else as "
            f"{topic_file} — and end. The factory shows it "
            f"and runs this request again once it is answered. Start no stage and no `factory.sh run`, commit nothing: "
            f"the factory commits what this request wrote.",
            f"Now is {stamp_utc()} (UTC) — the time a field such as `created:` takes.",
        ]
        if kind.name == "wish":
            lines.append("A wish becomes a backlog item kept as a draft (`status: draft`): the person releases it.")
        if kind.name == "correct" and not request.get("option"):
            lines.append("The person named no reason code for the correction: where their words point to exactly one, "
                         "write that one; else ask it as a record whose options are the codes.")
        answered = request.get("answered", "")
        if answered:
            records = [shown(path) for path, rid, _s in request_records(self._run.home, request["id"])]
            lines.append(f"This request ran before and asked; its question is answered now ({answered}: "
                         f"{', '.join(records)}). Read the answer and go on from there — write nothing the answer and "
                         f"the request do not settle.")
        story = (request.get("story") or "").split()
        lines.append(self._run.where_things_are(tool, story[0] if len(story) == 1 else None)
                     + " For a request, also `bash .agents/factory/factory.sh` backlog, status, decisions, discover, "
                     "spec-delta and help.")
        return "\n\n".join(lines)

    def request_allowed(self) -> str:
        """A request's shell: a stage's, with the cli narrowed to the flags the dialog skills read and record with, and
        the runner's reading verbs — no flag and no verb that starts a run, a request, the factory or its page."""
        cli = f"Bash({self._run.py} .agents/factory/factory-cli.py:*)"
        heads = [head for head in self._run.tools.allowed_commands().split(",") if head != cli]
        heads += [f"Bash({self._run.py} .agents/factory/factory-cli.py {flag}:*)" for flag in REQUEST_CLI_FLAGS]
        heads += [f"Bash(bash .agents/factory/factory.sh {verb}:*)"
                  for verb in ("backlog", "status", "decisions", "discover", "spec-delta", "help")]
        heads.append("Bash(date:*)")                # the backlog skill dates what it writes
        return ",".join(heads)


class RunnerStages:
    """A story's stages on the runner (`StoryStages`): its files read with the package's readers, in the checkout or
    the worktree it runs in, its gates and its processes as the runner starts them."""

    def __init__(self, run: Run, tool: str) -> None:
        self._run = run
        self._tool = tool

    def open_decisions(self, story: str) -> typing.List[str]:
        return self._run.open_decisions(story).split()

    def kind(self, story: str) -> StoryKind:
        return StoryKind(self._run.kind_of(story))

    def red_stale(self, story: str, start: StageName) -> bool:
        return self._run.red_proof_stale(story, start.value)

    def pause(self, story: str) -> None:
        self._run.between_stages(story, self._tool)

    def gate(self, stage: str, story: str) -> int:
        return self._run.gate(stage, story)

    def quiet_gate(self, stage: str, story: str) -> int:
        return self._run.quiet_gate(stage, story)

    def report(self, story: str, stage: str) -> GateReport:
        path = f"{self._run.runs}/{story}/.gate-{stage}.txt"
        return GateReport(read_text(path) if os.path.isfile(path) else "")

    def artefact(self, story: str, stage: str) -> str:
        return self._run.artefact(story, stage)

    def holds(self, story: str, stage: str) -> bool:
        return os.path.isfile(self._run.artefact(story, stage))

    def refused_before(self, story: str, stage: str) -> bool:
        return os.path.isfile(f"{self._run.runs}/{story}/.gate-{stage}.txt")

    def delivered(self, story: str) -> bool:
        return self._run.delivered(story)

    def asks_human(self, story: str, stage: str) -> bool:
        return self._run.asks_human(self._run.artefact(story, stage))

    def stopped_for_human(self, story: str, stage: str) -> int:
        return self._run.stopped_for_human(self._run.artefact(story, stage), stage, story)

    def stage(self, story: str, stage: str) -> int:
        self._announce(stage)
        return self._run.run_one(story, self._tool, stage)

    def dry(self, story: str, stage: str) -> None:
        tool = self._announce(stage)
        self._run.processes.dry_lines(tool, self._run.prompt_for(stage, story), stage)

    def _announce(self, stage: str) -> str:
        tool = self._run.tools.tool_for(stage, self._tool)      # the run's tool stays: every stage resolves its own
        print(f"── stage {stage}  (tool: {tool}, fresh context)")
        self._run.tool_in_flight = tool
        return tool

    def builder(self, story: str, stages: typing.Sequence[str], start: str, dry: bool) -> int:
        return self._run.builder_window(story, self._tool, stages, start, dry)

    def reviews(self, story: str, dry: bool) -> int:
        return self._run.run_reviews(story, self._tool, dry)

    def verifier(self, story: str, stages: typing.Sequence[str], dry: bool) -> int:
        return self._run.verifier_window(story, self._tool, stages, dry)

    def sent_back(self, story: str) -> bool:
        return self._run.back_to(story, "build") == "test"

    def repaired(self, story: str) -> bool:
        return newer(f"{self._run.runs}/{story}/tidy.md", f"{self._run.runs}/{story}/build.md")

    def red_proof(self, story: str) -> bool:
        ledger = self.red_ledger(story)
        return os.path.isfile(ledger) and os.path.getsize(ledger) > 0

    def red_ledger(self, story: str) -> str:
        return f"{self._run.evidence(story)}/.tests-red"

    def bump(self, story: str) -> Rounds:
        return Rounds(self._run.bump_rounds(story))

    def resumes(self, story: str) -> typing.Optional[StageName]:
        start = self._run.start_stage(story)
        return StageName(start) if start and start != "none" else None

    def verdict(self, story: str) -> VerdictWord:
        return VerdictWord(self._run.verdict_of(story) or "")

    def back(self, story: str) -> typing.Optional[StageName]:
        back = self._run.back_to(story)
        return StageName(back) if back else None

    def in_worktree(self) -> bool:
        return bool(os.environ.get("FACTORY_HOME"))

    def integrate(self, story: str, dry: bool) -> typing.Optional[int]:
        return self._run.cases.integrate(self._run, self._tool, story, dry)


class RunnerIntegration:
    """A story's integration on the runner (`StoryIntegration`): from the story's worktree into the main checkout,
    the cli's integrate steps run there, the integrate stage and the gate as the runner starts them."""

    def __init__(self, run: Run, tool: str) -> None:
        self._run = run
        self._tool = tool

    def lock(self) -> None:
        self._run.take_lock()

    def unlock(self) -> None:
        self._run.drop_lock()

    def step(self, story: str, work: typing.Callable[[], typing.Optional[int]]) -> typing.Optional[int]:
        with self._run.step(story, "integrate"):
            return work()

    def prepare(self, story: str) -> typing.Tuple[int, str]:
        return self._run.as_home(
            lambda home, story: integrate_prepare(home, place("runs"), place("epics"), story), story)

    def session(self, story: str, conflicts: str, lost: Lost) -> typing.Optional[int]:
        return self._run.integrate_stage(story, self._tool, conflicts, list(lost) or None)

    def lost(self, story: str) -> Lost:
        return main_tests_lost(self._run.pwd, self._run.runs, story)

    def lost_text(self, lost: Lost) -> str:
        return lost_text(lost)

    def gate(self, story: str) -> int:
        home = os.environ.get("FACTORY_HOME") or self._run.home
        return self._run.gate("integrate", story, gate_path=f"{home}/{self._run.gate_rel}")

    def report(self, story: str) -> GateReport:
        path = self.report_place(story)
        return GateReport(read_text(path) if os.path.isfile(path) else "")

    def report_place(self, story: str) -> str:
        return f"{self._run.runs}/{story}/.gate-integrate.txt"

    def published(self) -> bool:
        return bool(claim_config_here(self._run.home))

    def worktree(self) -> str:
        return self._run.pwd

    def relink(self, story: str) -> None:
        self._run.take_lock()
        try:
            self._run.link_worktree(story)
        finally:
            self._run.drop_lock()
        self._run.journal_line(story, f"{utc()}\toutdated\tdocument.md\tby=integrate")

    def bump(self, story: str) -> Rounds:
        return Rounds(self._run.bump_rounds(story))


class RunnerBacklog:
    """The backlog run's ports on the runner (`BacklogSchedule`, `BacklogCheckout`, `BacklogWorker`): the schedule
    the cli prints, the checkout under the claim, the stories and requests as processes."""

    def __init__(self, run: Run, tool: str) -> None:
        self._run = run
        self._tool = tool

    def read(self, slots: int, busy: typing.Sequence[str], skip: typing.Sequence[str]) -> ScheduleRead:
        args = ["--schedule", "--slots", str(slots), "--busy", ",".join(busy)]
        args += ["--skip", ",".join(skip)] if skip else []
        code, out = self._run.cli(*args, merge=True)
        if code != 0:
            return ScheduleRead(False, out)
        lines = out.split("\n")
        named = [line[len("next: "):] for line in lines if line.startswith("next: ")]
        following = tuple((text.split(" ", 1)[0], text.split(" ", 1)[-1]) for text in named if not text.startswith("none"))
        return ScheduleRead(True, out, following, any(line.startswith("wait: yes") for line in lines))

    def prune(self) -> None:
        with self._run.locked():
            self._run.as_home(lambda home: worktree_prune(home, place("epics")), capture="none")

    def renew(self) -> bool:
        return self._run.renew()

    def stop_asked(self) -> typing.Optional[str]:
        return self._run.stop_file if os.path.isfile(self._run.stop_file) else None

    def stop_place(self) -> str:
        return self._run.stop_file

    def claims(self) -> str:
        if not claim_config_here(self._run.home):
            return ""
        return self._run.cli("--claims-refresh", quiet=False)[1]

    def signalled(self) -> typing.Optional[int]:
        code, self._run.pending = self._run.pending, None
        return code

    def wait(self, interval: int) -> None:
        self._run.wait_or_wake(interval)

    def pause(self) -> None:
        time.sleep(2)

    def run(self, story: str, start: str) -> int:
        return self._run.run_story(story, self._tool, start, False)

    def fresh(self, story: str, start: str) -> None:
        self._run.reset_rounds(story, start)
        self._run.gates.fresh_window(story)

    def start(self, story: str, start: str) -> Child:
        os.makedirs(f"{self._run.home}/{self._run.evidence_rel()}/{story}", exist_ok=True)
        return self._run.start_child(story, self._tool, start)

    def work(self, busy: typing.Sequence[str]) -> None:
        self._run.work_requests(self._tool, busy)

    def start_request(self, request: Request) -> Child:
        return self._run.start_request_child(request, self._tool)

    def capped(self) -> bool:
        return bool(self._run.max_stages and self._run.invocations >= self._run.max_stages)
