"""What `factory.sh run` checks before any stage is paid for: not inside an agent session, the carriers the profile
names in the project, the profile against the gate, a local model's context window, the tool's binary against its
record — each said in the lines the shell runner said them in, each with its exit."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

from .shell_root import ShellRoot

GATE = ".agents/factory/story-gate.py"


def err(text: str) -> None:
    sys.stdout.flush()
    print(text, file=sys.stderr, flush=True)


def isolated() -> bool:
    """A stage process sees the project and nothing else; FACTORY_ISOLATION=off runs it with the tool's full setup."""
    return os.environ.get("FACTORY_ISOLATION", "on") != "off"


def refuse_nested() -> int:
    """Inside an agent session the stages run in that session; a runner started from there would start a tool process
    per stage on top of it. FACTORY_ALLOW_NESTED=1 is the deliberate way past it; a stand-in starts no tool."""
    if os.environ.get("FACTORY_TOOL_CMD") or os.environ.get("FACTORY_ALLOW_NESTED") == "1":
        return 0
    if any(os.environ.get(name) for name in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID",
                                             "CODEX_THREAD_ID")):
        err("factory: this shell belongs to an agent session — the runner would start a tool process per")
        err("factory:   stage on top of it. In the session, run the stages with /factory-run; start the")
        err("factory:   runner from a terminal of its own. FACTORY_ALLOW_NESTED=1 starts it here anyway.")
        return 6
    return 0


def check_carriers(root: ShellRoot, tool: str) -> int:
    """The craft a profile names has to be in the project's own skill folder, because an isolated stage sees nothing
    else — checked before the first invocation, so a missing carrier stops the run instead of every stage quietly
    falling back. A profile that names a skill by an old name would run yesterday's copy."""
    renames = root.profile_renames()
    if renames:
        err("factory: the profile names skills by names they no longer have — nothing was started:")
        for rename in renames:
            err(f"factory:   {rename}")
        err("factory:   change those lines; a copy under the old name would run yesterday's skill. 'factory.sh")
        err("factory:   update' removes such a copy where the project did not edit it.")
        return 2
    if os.environ.get("FACTORY_TOOL_CMD") or not isolated():
        return 0
    folder = root.tool_skills(tool)
    if not folder:
        return 0
    missing = [name for name in root.cli_captured(["--carriers"])[1].split()
               if not os.path.isfile(os.path.join(folder, name, "SKILL.md"))]
    if not missing:
        return 0
    err(f"factory: the profile names carrier(s) the project does not hold in {folder}:" + "".join(f" {n}" for n in missing))
    err("factory:   a stage process sees only the project — 'factory.sh update' links them there (a tool the")
    err(f"factory:   project has no skills for yet: 'factory.sh setup --tool {tool}'), or FACTORY_ISOLATION=off")
    err("factory:   uses the tool's own setup.")
    return 2


def check_contract_first(root: ShellRoot) -> int:
    """The profile's contract and model keys, before any stage is paid for: a run started --from a later stage has no
    plan gate in front of it, and a stage run on the wrong model is spent money. The gate and the cli are two entry
    points of one package: without the package beside the gate, or without the cli, nothing runs."""
    if not os.path.isfile(GATE):
        return 0
    if not os.path.isdir(os.path.join(os.path.dirname(GATE), "dca_factory")):
        err("factory: no dca_factory/ beside the gate — 'factory.sh update' puts it there. Nothing was started.")
        return 2
    if not os.path.isfile(".agents/factory/factory-cli.py"):
        err("factory: no factory-cli.py beside the gate — 'factory.sh update' puts it there. Nothing was started.")
        return 2
    code, out = root.gate_merged(["--check-contract"])
    if code == 1:
        err(out.rstrip("\n"))
        err("factory: the stack profile does not hold for this gate — nothing was started.")
        return 2
    return 0                                  # an older gate without the check: its stage gates still run


def model_flag(root: ShellRoot, tool: str) -> str:
    """The model a local tool runs with: the -m/--model in its extra flags."""
    for line in root.tool_args(tool).splitlines():
        found = re.match(r".*(-m|--model)[ =]([^ ]*).*", line)
        if found:
            return found.group(2)
    return ""


def check_local_context(root: ShellRoot, tool: str) -> None:
    """A local model loaded with a context window smaller than a stage grows to truncates or aborts in silence. LM
    Studio says how large the loaded window is; below the minimum, the run warns before it starts."""
    if tool != "opencode":
        return
    model = model_flag(root, tool)
    if not re.fullmatch(r"lmstudio[^/]*/.*", model):
        return
    least = int(os.environ.get("FACTORY_LOCAL_CONTEXT_MIN") or 65536)
    wanted, loaded = model.split("/", 1)[1], ""
    url = (os.environ.get("FACTORY_LMSTUDIO_URL") or "http://localhost:1234") + "/api/v0/models"
    try:
        with urllib.request.urlopen(url, timeout=2) as answer:
            data = json.loads(answer.read().decode("utf-8", "replace"))
        loaded = "\n".join(str(m.get("loaded_context_length") or 0) for m in data.get("data", [])
                           if m.get("id") == wanted)
    except Exception:                               # noqa: BLE001 — no answer, or not JSON: the window is unknown
        loaded = ""
    if not loaded:
        err(f"factory: note — the context window of {model} could not be read; a stage needs {least}+ tokens")
    elif loaded.isdigit() and int(loaded) < least:
        err(f"factory: {model} is loaded with a {loaded}-token context window; a stage grows past {least}.")
        err("factory:   reload it with a larger context length in LM Studio, or set FACTORY_LOCAL_CONTEXT_MIN.")


def check_tool(root: ShellRoot, tool: str) -> int:
    """The tool, before any stage is paid for: its binary is asked once whether it knows every flag its record passes
    — a flag a stage needs and the binary lacks stops the run; an isolation flag it lacks is left out and named, as is a
    run without isolation or OpenCode without the pipeline's permission block."""
    if not isolated():
        err("factory: FACTORY_ISOLATION=off — stages run with the tool's full setup, user plugins included")
    if not tool or not root.tool_skills(tool) or os.environ.get("FACTORY_TOOL_CMD"):
        return 0
    code, out, _said = root.cli_captured(["--tool-probe", tool])
    out = out.rstrip("\n")
    if code == 1:
        err(f"factory: {out}")
        err("factory:   nothing was started — update the tool, or run with another (--tool).")
        return 2
    if isolated():
        for line in out.splitlines():
            found = re.match(r"^([a-z]*): no (.*)$", line)
            if found:
                err(f"factory: {found.group(1)} knows no {found.group(2)}")
    if tool == "opencode" and os.environ.get("FACTORY_OPENCODE_PERMISSIONS", "on") == "off" \
            and not os.environ.get("OPENCODE_CONFIG_CONTENT"):
        err("factory: FACTORY_OPENCODE_PERMISSIONS=off — OpenCode runs the stages with its own permissions")
    return 0
