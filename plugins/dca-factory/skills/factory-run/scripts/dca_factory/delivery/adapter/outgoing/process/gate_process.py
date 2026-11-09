"""The gate beside the runner — a process of its own, or its command line in the runner's process where the two are one
package (WP-94: the evidence out of a stage's reach; WP-197): a stage's gate run
with its report kept, the person's parts recorded and compared across a stage window, the story's base and changes
recorded, and the snapshot of the working tree before and after a window."""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import typing

from ..files.owned_files import OWNED_DIGEST, WINDOW_DIGEST
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, place
from ..tools.tool_processes import err, flush, utc

#: The first line of a snapshot written without a hash: the observer reads such a snapshot as absent, because a
#: snapshot of empty digests compares equal to every other and would read as "this stage changed nothing".
NO_HASHES = "# no-sha256-command: names only, no content hashes"


def hashing() -> bool:
    return os.environ.get("FACTORY_SHA256", "") != "none"


def file_sha(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


class GateHost(typing.Protocol):
    """What of the run the gate's process reads: where the gate and the run folder are, the key that signs the suites
    it records, and the run's own journal, profile and child processes."""

    gate_path: str
    runs: str
    suites_key: str

    def evidence(self, story: str) -> str: ...

    def journal_line(self, story: str, line: str) -> None: ...

    def profile(self) -> typing.Mapping[str, typing.Any]: ...

    def run(self, argv: typing.List[str], *, capture: bool = False, quiet: bool = False, merge: bool = False,
            cwd: typing.Optional[str] = None, env: typing.Optional[typing.Mapping[str, str]] = None,
            stdin: typing.Optional[int] = None, stdout: typing.Optional[int] = None) -> typing.Tuple[int, str]: ...

    def runs_the_gate(self, gate_path: str) -> bool: ...

    def gate_here(self, argv: typing.Sequence[str], *, quiet: bool = False) -> int: ...


class GateProcess:
    """The gate's process for one run (<host>)."""

    def __init__(self, host: GateHost) -> None:
        self._host = host

    def installed(self) -> bool:
        return os.path.isfile(self._host.gate_path)

    def call(self, argv: typing.List[str], *, quiet: bool = False) -> int:
        """The gate's command line: in the runner's process where the runner's package is the installed gate's, by
        content (WP-197: a process start is what the run pays most for on Windows) — else as a process of its own."""
        host = self._host
        if host.runs_the_gate(host.gate_path):
            return host.gate_here(argv, quiet=quiet)
        return host.run([sys.executable, host.gate_path, *argv], quiet=quiet,
                        stdout=subprocess.DEVNULL if quiet else None)[0]

    def owned(self, edge: str, window: str, story: str, code: typing.Optional[int] = None) -> int:
        """What is the person's is unchanged across a stage window — recorded at its start, compared at its end."""
        if not self.installed():
            return 0
        return self.call(["--owned", edge, window, *([str(code)] if code is not None else []), "--story", story])

    def fresh_window(self, story: str) -> None:
        """`--from <stage>`: a person names where the story starts, so a window a killed run left open is closed —
        its digest of the story is gone, and a story the person changed since reads as changed after its plan,
        never as changed under a stage."""
        self._host.profile()
        folder = evidence_dir(place("runs"), story)
        left = [name for name in (OWNED_DIGEST, WINDOW_DIGEST) if os.path.isfile(os.path.join(folder, name))]
        for name in left:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(folder, name))
        if OWNED_DIGEST in left:
            self._host.journal_line(story, f"{utc()}\twindow-closed\t-\tby=--from")
            print(f"factory: --from closes the stage window an earlier run of {story} left open.")

    def record(self, flag: str, story: str, *more: str) -> None:
        """`--record-base` / `--record-changes <stage>`: what the story's diff is taken against, and what it changed."""
        if self.installed():
            self.call([flag, *more, "--story", story], quiet=True)

    def gate(self, stage: str, story: str, gate_path: str) -> int:
        """The gate of <stage> run over <story>, its report shown and kept for the observer; a refusal is kept where
        the next stage reads it."""
        host = self._host
        report = f"{host.runs}/{story}/.gate-{stage}.txt"
        journal = host.evidence(story)
        flush()
        argv = ["--story", story, "--stage", stage, "--record-suites"]
        if host.runs_the_gate(gate_path):
            code = self._gate_here(argv, report)
        else:
            env = dict(os.environ, FACTORY_SUITES_KEY=host.suites_key)
            process = subprocess.Popen([sys.executable, gate_path, *argv],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            assert process.stdout is not None
            with open(report, "wb") as kept:
                for chunk in iter(process.stdout.readline, b""):
                    kept.write(chunk)
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.flush()
            code = process.wait()
        # Every gate run is kept for the observer, with its verdict; only a refusal is kept where the next stage
        # reads it. 3 is not a refusal: every check passed and a human is asked (acceptance).
        shutil.copy(report, f"{journal}/gate-{stage}.{utc('%H%M%S')}.txt")
        if code in (0, 3):
            os.remove(report)
        return code

    def _gate_here(self, argv: typing.List[str], report: str) -> int:
        """The stage's gate in the runner's process: what it prints, its errors among it, into the report and onto
        the terminal, as its process's lines would go; the suites key in the environment for this call alone."""
        before = os.environ.get("FACTORY_SUITES_KEY")
        os.environ["FACTORY_SUITES_KEY"] = self._host.suites_key
        try:
            with open(report, "w", encoding="utf-8", newline="\n") as kept:
                both = _Both(kept, sys.stdout)
                with contextlib.redirect_stdout(both), contextlib.redirect_stderr(both):
                    return self._host.gate_here(argv)
        finally:
            if before is None:
                os.environ.pop("FACTORY_SUITES_KEY", None)
            else:
                os.environ["FACTORY_SUITES_KEY"] = before

    def snapshot(self, story: str, label: str) -> None:
        """What the working tree looks like right now, so a later stage's claim about what it changed can be
        checked rather than believed."""
        journal = self._host.evidence(story)
        os.makedirs(journal, exist_ok=True)
        hashed = hashing()
        if not hashed:
            err("factory: no sha256 command found (shasum, sha256sum, openssl) — the tree snapshots")
            err("factory:   record file names without content, and factory-verify reports every check")
            err("factory:   that needs a digest as not observed. Install one of the three for full evidence.")
        lines = [NO_HASHES] if not hashed else []
        prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], capture_output=True, text=True).stdout.strip()
        status = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain", "-z", "-uall", "--", "."],
                                capture_output=True).stdout.decode("utf-8", errors="replace")

        def strip(name: str) -> str:
            return name[len(prefix):] if prefix and name.startswith(prefix) else name
        origin = ""
        for entry in status.split("\0"):
            if not entry:
                continue
            if origin:                          # -z writes a rename's source as the next entry
                if origin == "R":
                    lines.append(f"deleted  {strip(entry)}")
                origin = ""
                continue
            code, name = entry[:2], strip(entry[3:])
            if code[:1] in ("R", "C"):
                origin = code[:1]
            if "D" in code:
                lines.append(f"deleted  {name}")
                continue
            if not os.path.isfile(name):
                continue
            lines.append(f"{file_sha(name) if hashed else '-'}  {name}")
        with contextlib.suppress(OSError):
            with open(f"{journal}/tree-{label}.txt", "w", encoding="utf-8", newline="\n") as handle:
                handle.write("".join(line + "\n" for line in lines))


class _Both(io.TextIOBase):
    """Every line written to the report and to the terminal, the terminal's flushed at once."""

    def __init__(self, kept: typing.TextIO, shown: typing.TextIO) -> None:
        self._kept, self._shown = kept, shown

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._kept.write(text)
        self._shown.write(text)
        self._shown.flush()
        return len(text)

    def flush(self) -> None:
        self._kept.flush()
        self._shown.flush()
