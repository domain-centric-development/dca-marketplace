"""A unit's tool started as a process of its own: its output kept in a file, a time limit and an interrupt that stop it
with what it started, the wait at the tool's usage limit, and the usage line the journal gets per process."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import typing

from ..files.journal_files import journal_path
from ..files.stream_records import freeze_stream
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from .agents import TOOL, tool_command
from .streams import stream_limit, usage_lines
from .tool_choice import seconds_of, ToolChoice
from ....application.shared.run_stop import SIGNAL_EXITS, Stopped  # noqa: F401 — raised by the processes, caught by the runner

TIMED_OUT = 124
#: The usage limit (#161): the wait where the tool names no reset, the margin past the one it names, how often the
#: wait looks at the stop file and renews the claim — seconds.
LIMIT_FALLBACK, LIMIT_MARGIN, LIMIT_POLL = 1800, 60, 60
def utc(fmt: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
    return time.strftime(fmt, time.gmtime())


def flush() -> None:
    sys.stdout.flush()
    sys.stderr.flush()


def err(text: str) -> None:
    sys.stdout.flush()
    print(text, file=sys.stderr, flush=True)


def stop_group(process: "subprocess.Popen[bytes]", first: typing.Optional[int] = None) -> None:
    """A tool and what it started, stopped: <first> (TERM by default), then KILL after five seconds."""
    if os.name == "nt":
        process.kill()
        process.wait()
        return
    for sig, grace in ((first or signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        with contextlib.suppress(OSError):
            os.killpg(process.pid, sig)
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def spawnable(argv: typing.List[str]) -> typing.List[str]:
    """On Windows a tool found on the PATH may be a script or a `.cmd`, which no process starts by itself."""
    if os.name != "nt":
        return argv
    found = shutil.which(argv[0]) or argv[0]
    if found.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", found, *argv[1:]]
    if not found.lower().endswith((".exe", ".com")):
        return ["sh", found, *argv[1:]]
    return [found, *argv[1:]]


def exit_field(code: int) -> str:
    return "0" if code == 0 else "timeout" if code == TIMED_OUT else "nonzero"


class ToolHost(typing.Protocol):
    """What of the run a tool process reads: who runs it and where, which folders it may write and read, how long it
    may take, and the run's own journal, claim and pause."""

    worker: str
    runs: str
    stop_file: str
    request_in_flight: str
    add_dirs: typing.List[str]
    read_dirs: typing.List[str]
    timeout: int

    def protected_dirs(self) -> typing.List[str]: ...

    def journal_line(self, story: typing.Optional[str], line: str) -> None: ...

    def renew(self) -> bool: ...

    def sleep(self, seconds: float) -> None: ...

    def wait(self, process: "subprocess.Popen[bytes]", timeout: typing.Optional[float] = None) -> int: ...


class ToolProcesses:
    """The tool processes of one run (<host>), started as <choice> says."""

    def __init__(self, host: ToolHost, choice: ToolChoice) -> None:
        self._host = host
        self._choice = choice

    def dry_lines(self, tool: str, prompt: str, model_stage: str) -> None:
        print(f"   would run: {prompt}")
        isolation = os.environ.get("FACTORY_ISOLATION")
        print(f"   tool flags: {self._choice.isolation_flags(tool)}"
              + (f"(FACTORY_ISOLATION={isolation})" if isolation else ""))
        print(f"   shell allowed: {self._choice.allowed_commands()}")
        flags, note = self._choice.model_choice(tool, model_stage)
        print(f"   model: {flags}{note}")

    def invoke(self, tool: str, prompt: str, raw: str, stage: str, story: typing.Optional[str]) -> int:
        """One stage's tool process; its output kept in <raw>, where the tool also says what the stage cost. A process
        that ran into the tool's usage limit is kept beside it (`<raw>` with `-limit<n>` before `.out`, its usage
        journaled), the runner waits for the reset and the same stage runs again — no round counted, no story set
        aside (#161)."""
        attempt = 0
        while True:
            code = self.invoke_once(tool, prompt, raw, stage, story)
            fmt = self._choice.usage_format(tool)
            limited = stream_limit(raw, None if fmt == "none" else fmt) if raw != os.devnull else None
            if not limited:
                return code
            attempt += 1
            kept = f"{raw[:-len('.out')]}-limit{attempt}.out" if raw.endswith(".out") else f"{raw}.limit{attempt}"
            with contextlib.suppress(OSError):
                os.replace(raw, kept)
            self.record_usage(story, stage, tool, kept)
            if not self.wait_for_limit(story, stage, tool, limited):
                return code if code != 0 else 1
            if attempt == 1:
                prompt += (" An earlier process of this stage stopped at the tool's usage limit before it finished: "
                           "read the files as they are and go on from there.")

    def wait_for_limit(self, story: typing.Optional[str], stage: str, tool: str, limited: typing.Mapping[str, typing.Any]) -> bool:
        """Until a minute past the reset the tool named — or FACTORY_LIMIT_WAIT (30m) where it named none, or one past.
        The claim is renewed while it waits, and the journal says until when, so the schedule reads the stage as
        running, not as interrupted. False where the stop file, another worker or a signal ends the wait."""
        host = self._host
        now = time.time()
        fallback = seconds_of(os.environ.get("FACTORY_LIMIT_WAIT", "")) or LIMIT_FALLBACK
        until = limited["until"] + LIMIT_MARGIN if limited.get("until") and limited["until"] > now else now + fallback
        when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(until))
        host.journal_line(story, f"{utc()}\tlimit\t{stage}\ttool={tool}\tuntil={when}")
        said = f" ({limited['text']})" if limited.get("text") else ""
        print(f"factory: {tool} reached its usage limit during {stage}{said} — waiting until {when}, then {stage} runs "
              f"again; {host.stop_file} ends the wait.")
        main = threading.current_thread() is threading.main_thread()
        while time.time() < until:
            if os.path.isfile(host.stop_file):
                err(f"factory: {host.stop_file} exists — the wait for the usage limit ends; {stage} did not finish.")
                return False
            if main and not host.renew():
                err("factory: another worker took over this checkout while the run waited for the usage limit.")
                return False
            host.sleep(min(LIMIT_POLL, max(1, until - time.time())))
        print(f"factory: the usage limit reset — {stage} runs again.")
        return True

    def invoke_once(self, tool: str, prompt: str, raw: str, stage: str, story: typing.Optional[str]) -> int:
        """One tool process, as `invoke` starts it."""
        host, choice = self._host, self._choice
        flags, _note = choice.model_choice(tool, stage)
        command = os.environ.get("FACTORY_TOOL_CMD")
        env = dict(os.environ, FACTORY_WORKER=host.worker, FACTORY_STAGE=stage or "", FACTORY_STORY=story or "",
                   FACTORY_REQUEST=host.request_in_flight)
        if command:
            env.update(FACTORY_PROMPT=prompt, FACTORY_RUNS=host.runs, FACTORY_MODEL=choice.model_key(tool, stage))
            code = self.tool_process(["sh", "-c", command], env, raw, stdin=None, stage=stage)
            if raw != os.devnull and not os.environ.get("FACTORY_USAGE_FORMAT"):
                with contextlib.suppress(OSError):
                    sys.stdout.write(read_text(raw))
                    flush()
            return code
        if tool not in TOOL:
            err(f"factory: unknown tool '{tool}'")
            return 2
        level, _note = choice.effort_choice(tool, stage)
        variables, argv = tool_command(TOOL[tool], model=flags.split(" ", 1)[1] if flags else "",
                                       writable=host.add_dirs, readable=host.read_dirs,
                                       protected=host.protected_dirs(), allowed=choice.allowed_commands(), effort=level)
        env.update(variables)
        return self.tool_process(spawnable(argv + [prompt]), env, raw, stdin=subprocess.DEVNULL, stage=stage)

    def tool_process(self, argv: typing.List[str], env: typing.Mapping[str, str], raw: str,
                     stdin: typing.Optional[int], stage: str) -> int:
        """A tool started in a session of its own, so a time limit or an interrupt stops it with what it started."""
        flush()
        with open(raw, "wb") as out:
            try:
                process = subprocess.Popen(argv, env=env, stdin=stdin, stdout=out, start_new_session=os.name != "nt")
            except OSError as error:
                err(f"factory: the tool could not be started — {error}")
                return 127
            try:
                return self._host.wait(process, timeout=self._host.timeout or None)
            except subprocess.TimeoutExpired:
                stop_group(process)
                err(f"factory: stage '{stage}' ran past its time limit of {self._host.timeout}s (FACTORY_STAGE_TIMEOUT, "
                    f"the profile's stageTimeout:) — the tool was stopped.")
                return TIMED_OUT
            except KeyboardInterrupt:
                stop_group(process, signal.SIGINT)
                raise Stopped(SIGNAL_EXITS["SIGINT"])

    def record_usage(self, story: typing.Optional[str], stage: str, tool: str, raw: str, seconds: typing.Optional[int] = None,
                     request: str = "") -> str:
        """One `usage` line in the story's journal per invocation — a request's in the request journal, with its id —
        and the stage's final message on screen. Returns the measured fields."""
        fmt = self._choice.usage_format(tool)
        model = self._choice.model_flag(tool, stage)
        try:
            lines = "\n".join(usage_lines(fmt, raw, model)).split("\n")
        except Exception:                   # a raw output no reader understands costs the line, never the run
            lines = ["unknown"]
        fields = lines[0]
        if seconds is not None:
            fields += f"\tseconds={seconds}"
        if fmt != "none" and len(lines) > 1:
            print("\n".join(lines[1:]))
        self._host.journal_line(story, f"{utc()}\tusage\t{stage}\ttool={tool}"
                                + (f"\trequest={request}" if request else "") + f"\t{fields}")
        # what only the stream says — a shared window's parts, the denied calls — goes into the journal now (WP-150)
        if story and os.path.isfile(raw):
            with contextlib.suppress(OSError, GateError, ValueError):
                freeze_stream(journal_path(place("runs"), story), raw)
        return fields
