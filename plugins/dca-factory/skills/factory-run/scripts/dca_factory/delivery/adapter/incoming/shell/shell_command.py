"""`factory.sh`'s command line — the verbs a person and a tool type. The script finds a Python 3.12 or newer and hands
over at once; everything it decided before the runner, and the setup and the update, is here (WP-202 step 3): the
reading verbs pass on to the cli's command line, the checking ones to the gate's — both in this process —, `run` checks
and becomes the runner, `setup` and `update` are the installer's use cases. The verbs, their flags and their exits are
the script's usage, at its top.

`run` exits 0 when the story ran through, 3 when it stopped for a decision, 4 at --max-stages, 5 when another worker
holds the checkout, 6 when started inside an agent session with a real tool (FACTORY_ALLOW_NESTED=1 overrides),
anything else on a failure; a usage error is 2.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import typing

from ....application.setup.check_detected_profile import CheckDetectedProfile
from ....application.setup.install_pipeline import AlreadyInstalled, OtherRelease, InstallPipeline
from ....application.setup.refresh_pipeline import HandedOver, RefreshPipeline
from ....application.setup.write_detected_profile import WriteDetectedProfile
from ....application.shared.pipeline_install import InstallStopped, ProfileOutcome, Proposal, SkillMode, Stop
from .run_checks import (GATE, check_carriers, check_contract_first, check_local_context, check_tool, err,
                         refuse_nested)
from .shell_root import ShellRoot

#: the composition root, given by `wire` before the command line runs
wiring: ShellRoot

#: A step's exit, as the profile check's outcomes end the shell's command.
EXITS = {ProfileOutcome.HOLDS: 0, ProfileOutcome.LACKS: 1, ProfileOutcome.REFUSED: 2}


def wire(root: ShellRoot) -> None:
    """The composition root this command line builds its use cases from."""
    global wiring
    wiring = root


class Usage(Exception):
    """The command line is not one the script takes: its usage on stderr, exit 2."""


def main(argv: typing.Sequence[str]) -> int:
    try:
        return command_line(list(argv))
    except Usage:
        sys.stdout.flush()
        sys.stderr.write("".join(f"{line}\n" for line in wiring.runner_header()))
        return 2
    except InstallStopped as stopped:
        if stopped.why is Stop.USAGE:
            sys.stdout.flush()
            sys.stderr.write("".join(f"{line}\n" for line in wiring.runner_header()))
            return 2
        return 1 if stopped.why is Stop.FAILED else 2


def needs(args: typing.Sequence[str], least: int, most: typing.Optional[int] = None) -> None:
    if len(args) < least or (most is not None and len(args) > most):
        raise Usage()


def read_command(argv: typing.Sequence[str]) -> int:
    """A reading verb: the cli's, beside the gate the project installed."""
    if not os.path.isfile(GATE):
        err(f"factory: no gate at {GATE} — run 'factory.sh setup' from the plugin")
        return 2
    return wiring.cli(argv)


def gate_command(argv: typing.Sequence[str]) -> int:
    """A check, not a view: the project's gate."""
    if not os.path.isfile(GATE):
        err(f"factory: no gate at {GATE} — run 'factory.sh setup' from the plugin")
        return 2
    return wiring.gate(argv)


def command_line(argv: typing.List[str]) -> int:
    if not argv:
        raise Usage()
    command, args = argv[0], argv[1:]
    passed = PASSED_ON.get(command)
    if passed is not None:
        return passed(args)
    if command in ("up", "down", "serve", "request", "requests"):
        # the factory as a process of its own and what a person asks of it (WP-91): the cli's, like every view
        return read_command([f"--{command}", *args])
    if command not in ("setup", "update", "run"):
        flags(command, args)                       # a flag the verb does not know is a usage error first
        raise Usage()
    options = flags(command, args)
    if command == "setup":
        return setup(options)
    if command == "update":
        mode = SkillMode.LINK if options.link else SkillMode.COPY if options.copy else None
        done = wiring.update().execute(RefreshPipeline(options.source, mode, tuple(options.adopt)))
        return done.code if isinstance(done, HandedOver) else 0
    return run(options)


# --- the verbs that pass on ------------------------------------------------------------------------------------------


def status(args: typing.List[str]) -> int:
    story, view = "", []
    usage = refusals = brief = session_start = live = False
    while args:
        word = args.pop(0)
        if word == "--story":
            needs(args, 1)
            story = args.pop(0)
        elif word == "--epic":
            needs(args, 1)
            view += ["--epic", args.pop(0)]
        elif word == "--all":
            view.append("--all")
        elif word == "--usage":
            usage = True
        elif word == "--refusals":
            refusals = True
        elif word == "--brief":
            brief = True
        elif word == "--session-start":
            session_start = True
        elif word in ("--format", "--color"):
            needs(args, 1)
            view += [word, args.pop(0)]
        elif word == "--live":
            live = True
            view.append("--live")
        else:
            raise Usage()
    told = ["--story", story] if story else []
    if brief:
        if not os.path.isfile(GATE):
            return 0
        wiring.check_detected().execute(CheckDetectedProfile(Proposal.BRIEF))
        return read_command(["--status", "--brief", *(["--session-start"] if session_start else [])])
    if usage:
        return read_command(["--usage", *told])
    if refusals:
        return read_command(["--refusals", *told, *view])
    # Which pipeline this machine has is not the project's state: said with --live only, so the same files give the
    # same view everywhere.
    if live:
        wiring.freshness()
    return read_command(["--status", *told, *view])


def backlog(args: typing.List[str]) -> int:
    # The person's view of the backlog; the runner reads the schedule's lines from the gate itself.
    if args[:1] == ["--check"]:
        return gate_command(["--check-backlog"])
    return read_command(["--status", "--part", "backlog", *args])


def brief(args: typing.List[str]) -> int:
    # What a stage is told for a story (WP-169): its brief, from the workflow's stages and rules and the profile.
    needs(args, 2)
    return read_command(["--stage-brief", *args])


def spec_delta(args: typing.List[str]) -> int:
    # What holds before and after a story (WP-105): what a person accepting it looks at.
    needs(args, 1)
    return read_command(["--spec-delta", *args])


def release(args: typing.List[str]) -> int:
    # A claim on the remote given up by hand (WP-93): this factory's, or with --force another's.
    needs(args, 1)
    return read_command(["--release-claim", *args])


def integrate(args: typing.List[str]) -> int:
    """A published story whose merge request lost the race (WP-93 F): its delivery taken back on its branch, then the
    integrate step against the remote main line again — the spec merged again, never resolved by text."""
    needs(args, 1, 1)
    if not os.path.isfile(GATE):
        err(f"factory: no gate at {GATE} — run 'factory.sh setup' from the plugin")
        return 2
    code = wiring.cli(["--undeliver-branch", args[0]])
    if code != 0:
        return code
    return command_line(["run", "--story", args[0], "--from", "integrate"])


def discover(args: typing.List[str]) -> int:
    # The discovery report's check; the report itself is written in a session, by `factory-discover`.
    if args[:1] == ["--check"]:
        needs(args, 2, 2)
        return gate_command(["--check-discovery", args[1]])
    if args[:1] == ["--list"]:
        return read_command(["--discover-list", *args[1:]])
    raise Usage()


def check(args: typing.List[str]) -> int:
    if args[:1] == ["--parity"]:
        needs(args, 2, 2)
        return gate_command(["--parity", args[1]])
    return gate_command(["--change", *args])


def verify(args: typing.List[str]) -> int:
    if args[:1] == ["--story"]:
        needs(args, 2, 2)
        if not os.path.isfile(".agents/factory/observe.py"):
            err("factory: no observer at .agents/factory/observe.py — 'factory.sh update' copies it there")
            return 2
        return started([sys.executable, ".agents/factory/observe.py", "--story", args[1]])
    if args[:1] == ["--fixtures"]:
        skills = wiring.pipeline_found()
        suite = os.path.join(skills, "factory-verify", "scripts", "verify.py") if skills else ""
        if not skills or not os.path.isfile(suite):
            err("factory: no pipeline found whose fixtures could run — FACTORY_PLUGIN_DIR names one")
            return 2
        print(f"factory: the machinery of {skills}", flush=True)
        return started([sys.executable, suite, *args[1:]])
    raise Usage()


def started(argv: typing.Sequence[str]) -> int:
    """A program of its own — the observer, the fixture suite —, its exit."""
    sys.stdout.flush()
    sys.stderr.flush()
    return subprocess.run(list(argv)).returncode


PASSED_ON: typing.Dict[str, typing.Callable[[typing.List[str]], int]] = {
    "status": status,
    "backlog": backlog,
    "decisions": lambda args: read_command(["--list-decisions", *args]),
    # What holds (WP-173): each context with its domain model, its features, rules and criteria.
    "spec": lambda args: read_command(["--spec", *args]),
    # The rulebook (WP-166): generated from where each rule is written.
    "rules": lambda args: read_command(["--rules", *args]),
    "brief": brief,
    "spec-delta": spec_delta,
    "release": release,
    "integrate": integrate,
    "follow": lambda args: read_command(["--follow", *args]),
    "discover": discover,
    # The help works before the pipeline is installed too: then the plugin's cli explains it.
    "help": lambda args: wiring.cli(["--help-view", *args]),
    "check": check,
    "verify": verify,
}


# --- setup, update, run: their flags ---------------------------------------------------------------------------------


class Options:
    """The flags of `setup`, `update` and `run`, as one loop reads them for all three."""

    def __init__(self) -> None:
        self.story = self.tool = self.start = self.source = ""
        self.copy = self.link = self.dry = self.watch = self.stay = self.lane = False
        self.keep_going = self.separate = False
        self.adopt: typing.List[str] = []
        self.setup_mode = self.replace = ""
        self.interval = "60"
        self.max_stages = self.story_budget = ""
        self.parallel = os.environ.get("FACTORY_PARALLEL", "")
        self.shared_builder = shared_default(os.environ.get("FACTORY_SHARED_BUILDER", ""))
        self.shared_verifier = shared_default(os.environ.get("FACTORY_SHARED_VERIFIER", ""))
        self.builder_set = bool(os.environ.get("FACTORY_SHARED_BUILDER"))
        self.verifier_set = bool(os.environ.get("FACTORY_SHARED_VERIFIER"))


def shared_default(value: str) -> bool:
    """FACTORY_SHARED_BUILDER / FACTORY_SHARED_VERIFIER set to 0, off, no or false separate that half."""
    return bool(value) and value.lower() not in ("0", "off", "no", "false")


def value(args: typing.List[str], flag: str) -> str:
    if not args:
        err(f"factory: {flag} takes a value")
        raise Usage()
    return args.pop(0)


def flags(command: str, args: typing.List[str]) -> Options:
    options = Options()
    args = list(args)
    while args:
        word = args.pop(0)
        if word == "--story":
            options.story = value(args, word)
        elif word == "--tool":
            options.tool = value(args, word)
            os.environ["FACTORY_TOOL_EXPLICIT"] = "1"
        elif word == "--from":
            if command in ("setup", "update"):
                options.source = value(args, word)
            else:
                options.start = value(args, word)
        elif word == "--copy":
            options.copy = True
        elif word == "--link":
            options.link = True
        elif word == "--adopt":
            needs(args, 1)
            options.adopt += args.pop(0).replace(",", " ").split()
        elif word in ("--check", "--write") and command == "setup":
            options.setup_mode = word[2:]
        elif word == "--replace" and command == "setup":
            needs(args, 1)
            options.replace = args.pop(0)
        elif word == "--dry-run":
            options.dry = True
        elif word == "--watch":
            options.watch = True
        elif word == "--stay":
            options.stay = True
        elif word == "--lane":
            options.lane = True
        elif word == "--interval":
            options.interval = value(args, word)
        elif word == "--max-stages":
            options.max_stages = value(args, word)
        elif word == "--story-budget":
            options.story_budget = value(args, word)
        elif word == "--shared-builder":
            options.shared_builder = options.builder_set = True
        elif word == "--shared-verifier":
            options.shared_verifier = options.verifier_set = True
        elif word == "--separate-stages":
            options.separate = True
        elif word == "--parallel":
            needs(args, 1)
            options.parallel = args.pop(0)
        elif word == "--keep-going":
            options.keep_going = True
        else:
            raise Usage()
    return options


def setup(options: Options) -> int:
    if options.replace and options.setup_mode != "write":
        raise Usage()
    if not in_repository():
        return 1
    if options.setup_mode == "check":
        return EXITS[wiring.check_detected().execute(CheckDetectedProfile(Proposal.FULL))]
    if options.setup_mode == "write":
        return EXITS[wiring.write_detected().execute(WriteDetectedProfile(options.replace or None))]
    mode = SkillMode.COPY if options.copy else SkillMode.LINK if options.link else None
    done = wiring.set_up().execute(InstallPipeline(options.tool or None, options.source or None, mode,
                                                 tuple(options.adopt)))
    if isinstance(done, OtherRelease):
        err(f"factory: adding {options.tool} would also replace the installed pipeline {done.have} with {done.new} —")
        err("factory:   update first ('factory.sh update', or /factory-update), then add the tool; nothing was changed")
        return 2
    if isinstance(done, AlreadyInstalled):
        print("factory: the pipeline is installed here — setup installs nothing ('factory.sh update' replaces its "
              "files)")
        wiring.check_detected().execute(CheckDetectedProfile(Proposal.FULL))
    return 0


def in_repository() -> bool:
    """The commit hook and the worker lock live in .git, so the pipeline needs a repository — asked with `rev-parse`,
    not "has a commit": a repository without one is a fine place to start."""
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode == 0
    if not inside:
        err("factory: not a git repository — 'git init' first; the commit hook and the worker lock live in .git.")
    return inside


def numbers(text: str) -> bool:
    return re.fullmatch(r"[0-9]*", text) is not None


def resolve_stages(options: Options) -> bool:
    """Whether this run shares its stages: --separate-stages, else an explicit FACTORY_SHARED_* or flag per half, else
    the profile's `stages:` line, else shared."""
    if options.separate:
        options.shared_builder = options.shared_verifier = False
        return True
    said = wiring.cli_captured(["--get", "stages"])[1].split()
    mode = said[0] if said else ""
    if mode not in ("", "shared", "separate"):
        err(f"factory: the profile's stages: '{mode}' is neither shared nor separate")
        return False
    if not options.builder_set:
        options.shared_builder = mode != "separate"
    if not options.verifier_set:
        options.shared_verifier = mode != "separate"
    return True


def run(options: Options) -> int:
    tool = options.tool or next((name for name in wiring.tool_names() if shutil.which(name)), "")
    if not tool and not os.environ.get("FACTORY_TOOL_CMD"):
        err("factory: no agent tool found on PATH.")
        return 2
    if not numbers(options.max_stages):
        err("factory: --max-stages takes a number")
        return 2
    if not numbers(options.story_budget):
        err("factory: --story-budget takes a number of tokens")
        return 2
    if not resolve_stages(options):
        return 2
    if options.story:
        if options.watch or options.stay:
            err("factory: --watch works the backlog off — it takes no --story")
            return 2
        if options.keep_going:
            err("factory: --keep-going works the backlog off — it takes no --story")
            return 2
        tool = tool or "stand-in"
        code = checks(options, tool)
        if code:
            return code
        return runner(options, ["--story", options.story, "--tool", tool,
                                *(["--from", options.start] if options.start else [])])
    # Without --story: the backlog, story after story in the order the schedule names.
    if not options.interval or not numbers(options.interval):
        err("factory: --interval takes whole seconds")
        return 2
    # Bounded both ways: below a second the watch is a busy loop, above an hour an answer waits longer than anyone
    # expects to.
    interval = min(max(int(options.interval), 1), 3600)
    code = checks(options, tool)
    if code:
        return code
    if options.stay and not options.watch:
        err("factory: --stay keeps a --watch waiting — it takes --watch")
        return 2
    if options.lane and not options.watch:
        err("factory: --lane is the factory's worker — it takes --watch")
        return 2
    return runner(options, ["--tool", tool or "stand-in", *(["--watch"] if options.watch else []),
                            *(["--stay"] if options.stay else []), *(["--lane"] if options.lane else []),
                            "--interval", str(interval)])


def checks(options: Options, tool: str) -> int:
    """Everything before the first stage, in the order the shell runner checked it; the first exit that is not 0."""
    wiring.freshness()
    code = 0 if options.dry else refuse_nested()
    code = code or check_carriers(wiring, tool) or check_contract_first(wiring)
    if code:
        return code
    check_local_context(wiring, tool)
    return check_tool(wiring, tool)


def runner(options: Options, argv: typing.List[str]) -> int:
    """The run itself is the package's runner: the checks passed, this process becomes it — the same process id, so
    the worker's name on the claim is the one the checks saw. It takes the claim, guards the pipeline's hash, runs the
    story or the backlog and gives the claim and the lock back however it ends."""
    os.environ["FACTORY_RUNNER_PYTHON"] = wiring.python
    argv = ["--run", *argv, *(["--dry-run"] if options.dry else [])]
    argv += ["--max-stages", options.max_stages] if options.max_stages else []
    argv += ["--story-budget", options.story_budget] if options.story_budget else []
    argv += ["--keep-going"] if options.keep_going else []
    argv += ["--builder", "shared" if options.shared_builder else "separate",
             "--verifier", "shared" if options.shared_verifier else "separate"]
    argv += ["--parallel", options.parallel] if options.parallel else []
    return wiring.run(argv)
