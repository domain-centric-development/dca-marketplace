"""Which tool, model and effort a unit of a run starts with, what shell it may use and how long it may run — read from
the profile and the person's environment against the tool records.

A unit is what one process carries: the shared builder and verifier, a review, a separate stage, the integrate step.
The profile is asked again on every question: a person may edit it while a run waits.
"""

from __future__ import annotations

import os
import re
import shlex
import sys
import typing

from ....application.profile.profile_rules import command_heads, effort_for, first_word, model_for, tool_for
from .agents import isolation_args, TOOL

Profile = typing.Mapping[str, typing.Any]

#: The shell a stage may use without asking, beside the gate, the cli and the profile's commands: the ordinary
#: reading and text tools, the git verbs that look without changing anything (`git apply --check` is how a stage
#: tries a break patch), and `git rm` — how a stage removes a file its plan says `removed`; it takes tracked files
#: only, which git still holds, and the pipeline's own files are watched by the run (WP-102). What writes or runs
#: anything else stays out — `rm`, `sed -i`, `xargs`, `find -exec`, a redirect of `echo`/`printf`, `mkdir`: each
#: allowed head is allowed with every argument (WP-94). Measured on the bench: without the reading tools a stage hit
#: the allow-list about three times per story, each a wasted turn; without a delete the build left a planned removal.
STAGE_SHELL_HEADS = ("cd", "ls", "cat", "head", "tail", "wc", "sort", "grep", "diff", "pwd",
                     "git status", "git diff", "git log", "git ls-files", "git apply --check", "git rm")

#: Where a tool ran past this many seconds, it is stopped (0: no limit) — FACTORY_STAGE_TIMEOUT, else the profile's
#: `stageTimeout:`. A number with `s`, `m` or `h`; a bare number is seconds.
TIMEOUT_UNITS = {"": 1, "s": 1, "m": 60, "h": 3600}

def seconds_of(text: typing.Any) -> typing.Optional[int]:
    """`90`, `90s`, `30m`, `2h` → seconds; None for anything else."""
    match = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text or ""))
    return int(match.group(1)) * TIMEOUT_UNITS[match.group(2)] if match else None


class ToolChoice:
    """The choices of one run: <profile> reads the profile as it stands, <py> and <gate> are how a stage calls the
    gate. `allowed_override` replaces the shell a stage may use while a request's skill runs."""

    def __init__(self, profile: typing.Callable[[], Profile], py: str, gate: str) -> None:
        self._profile = profile
        self._py = py
        self._gate = gate
        self.allowed_override: typing.Optional[str] = None

    def stage_timeout(self, gate_installed: bool) -> int:
        given = os.environ.get("FACTORY_STAGE_TIMEOUT")
        if given is None:
            given = first_word(self._profile().get("stageTimeout", "")) if gate_installed else ""
        value = seconds_of(given) if given else 0
        if given and value is None:
            sys.stdout.flush()
            print(f"factory: the stage time limit '{given}' is no number of seconds (90, 90s, 30m, 2h) — no limit "
                  f"applies", file=sys.stderr, flush=True)
        return value or 0

    @staticmethod
    def isolated() -> bool:
        return os.environ.get("FACTORY_ISOLATION", "on") != "off"

    def isolation_flags(self, tool: str) -> str:
        if not self.isolated():
            return ""
        return (" ".join(shlex.quote(w) for w in isolation_args(TOOL[tool])) if tool in TOOL else "") + " "

    def allowed_commands(self) -> str:
        if self.allowed_override:
            return self.allowed_override
        heads = [f"Bash({self._py} {self._gate}:*)", f"Bash({self._py} .agents/factory/factory-cli.py:*)"]
        for head in command_heads(self._profile()) + list(STAGE_SHELL_HEADS):
            if f"Bash({head}:*)" not in heads:
                heads.append(f"Bash({head}:*)")
        return ",".join(heads)

    def model_key(self, tool: str, stage: typing.Optional[str]) -> str:
        return model_for(self._profile(), tool, (stage or "").split(":")[0])

    @staticmethod
    def tool_args(tool: str) -> str:
        record = TOOL.get(tool)
        return os.environ.get(record.args_env, "") if record and record.args_env else ""

    def env_model(self, tool: str) -> str:
        match = re.search(r".*(?:^| )(?:-m|--model)[ =]([^ ]*)", self.tool_args(tool))
        return match.group(1) if match else ""

    def tool_for(self, unit: str, given: str) -> str:
        """The tool one unit runs with: `--tool` when the person named one for this run (FACTORY_TOOL_EXPLICIT), else
        the profile's `tool.<unit>` (a review `tool.review.<perspective>`, then `tool.review`), else `tool:`, else
        the run's tool."""
        if os.environ.get("FACTORY_TOOL_EXPLICIT") or os.environ.get("FACTORY_TOOL_CMD"):
            return given
        return tool_for(self._profile(), unit) or given

    def effort_choice(self, tool: str, unit: typing.Optional[str]) -> typing.Tuple[str, str]:
        """(level, note) — the reasoning effort of one unit: the profile's `effort.<tool>.<unit>`, else
        `effort.<tool>`; a `--effort`/`model_reasoning_effort` in FACTORY_<TOOL>_ARGS wins, and a tool that takes no
        effort gets a note, never a silent drop."""
        level = effort_for(self._profile(), tool, unit)
        if not level:
            return "", ""
        if re.search(r"(--effort|model_reasoning_effort)", self.tool_args(tool)):
            return "", f"overridden by FACTORY_{tool.upper()}_ARGS"
        if tool not in TOOL or not TOOL[tool].effort:
            return "", f"effort not applied — tool {tool} takes none"
        return level, ""

    def effort_field(self, tool: str, unit: str) -> str:
        level, note = self.effort_choice(tool, unit)
        if note:
            print(f"factory: effort for {unit}: {note}")
        return f"\teffort={level}" if level else (f"\teffort=no ({note})" if note else "")

    def tools_of_run(self, given: str) -> typing.List[str]:
        """Every tool this run may start: the given one and every `tool`/`tool.<unit>` the profile names."""
        named = {first_word(v) for k, v in self._profile().items() if (k == "tool" or k.startswith("tool.")) and v}
        return sorted({given} | {n for n in named if n})

    def model_choice(self, tool: str, stage: typing.Optional[str]) -> typing.Tuple[str, str]:
        """The model flag for one stage, and why a request does not become one: (flag words, note). The model is
        the project's choice, stated in the profile per tool and stage (`model.<tool>.<stage>`, falling back to
        `model.<tool>`); the pipeline names none. A `--model`/`-m` in FACTORY_<TOOL>_ARGS wins — the person's local
        override — and the run says so. Exactly one model flag is ever passed."""
        requested = self.model_key(tool, stage)
        if not requested:
            return "", ""
        if os.environ.get("FACTORY_TOOL_CMD"):
            return "", "passed as FACTORY_MODEL to the custom command"
        if self.env_model(tool):
            return "", f"overridden by FACTORY_{tool.upper()}_ARGS ({self.env_model(tool)})"
        flag = TOOL[tool].model_flag if tool in TOOL else ""
        return (f"{flag} {requested}", "") if flag else ("", f"no model flag for tool {tool}")

    def model_flag(self, tool: str, stage: typing.Optional[str] = "") -> str:
        """The model a tool ran with, where its output does not say."""
        if stage and self.model_key(tool, stage) and not self.env_model(tool):
            return self.model_key(tool, stage)
        match = re.search(r".*(?:-m|--model)[ =]([^ ]*)", self.tool_args(tool))
        return match.group(1) if match else ""

    @staticmethod
    def usage_format(tool: str) -> str:
        if os.environ.get("FACTORY_TOOL_CMD"):
            return os.environ.get("FACTORY_USAGE_FORMAT") or "none"
        return (TOOL[tool].usage if tool in TOOL else "") or "none"
