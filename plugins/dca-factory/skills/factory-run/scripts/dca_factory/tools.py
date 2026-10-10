"""An agent tool is a record — what the runner needs to start one, probed once against its binary.

One `Tool` per tool (command, help probe, isolation, usage format, skill folder, model flag, add-dir mode, deny
rules, allow-list, permission block, plugins). The runner asks `tool_invocation` for the command line; a fourth
tool is one more row.
"""

import contextlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import typing


class Tool(typing.NamedTuple):
    """One agent tool the runner can start a stage with. Everything the runner knows about a tool is here; bash
    asks for an invocation (`--tool-invocation`) and runs it."""
    name: str
    command: tuple            #: the binary and its fixed arguments; the prompt goes last
    help: tuple               #: how its flags are probed: the help of the subcommand the command runs
    isolation: tuple          #: flag groups that keep the person's own setup out, each passed only where probed
    usage: str                #: the raw output's format, for `--usage-from`
    skills: str               #: the project folder the tool discovers skills in
    model_flag: str           #: the flag that names a model
    args_env: str             #: the person's extra flags (FACTORY_<TOOL>_ARGS), word-split, appended last
    add_dirs: str             #: which linked folders it is named: "all" (writable and read-only), "writable", or
                              #: "permission" — no flag, the permission block names them
    deny: bool = False        #: the protected folders are refused through `--disallowedTools Edit(//<dir>/**)`
    allow_list: bool = False  #: the shell a stage has is passed as `--allowed-tools`
    permission_env: str = ""  #: the environment variable a permission block is passed in
    isolation_env: tuple = () #: environment variables that do the same where the tool has no flag: (name, value),
                              #: `{empty}` an empty folder of the pipeline's own
    plugins: bool = False     #: it loads the method skills from its plugins, so its skill folder holds the pipeline's


                              #: alone; a tool without plugins finds only its folder, which then holds them all


TOOLS = (
    # stream-json: one event per line as it happens, so a stage can be followed while it runs (`factory.sh
    # follow`); the last line, `"type":"result"`, carries the usage.
    Tool("claude", ("claude", "-p", "--permission-mode", "acceptEdits", "--output-format", "stream-json",
                    "--verbose"),
         help=("claude", "--help"),
         isolation=(("--setting-sources", "project"), ("--strict-mcp-config",), ("--tools", "{stage_tools}"),
                    ("--exclude-dynamic-system-prompt-sections",)),
         usage="claude-json", skills=".claude/skills", model_flag="--model", args_env="FACTORY_CLAUDE_ARGS",
         add_dirs="all", deny=True, allow_list=True, plugins=True),
    # The user's config.toml (MCP servers, profiles, a model) stays out; the login does not. stdin is closed by the
    # runner: `codex exec` also reads a prompt from stdin, and an unattended run has none.
    Tool("codex", ("codex", "exec", "--json", "-s", "workspace-write", "-c",
                   "sandbox_workspace_write.network_access=true"),
         help=("codex", "exec", "--help"), isolation=(("--ignore-user-config",),),
         usage="codex-jsonl", skills=".codex/skills", model_flag="-m", args_env="FACTORY_CODEX_ARGS",
         add_dirs="writable"),
    # `opencode run` otherwise attaches to a background service started with another configuration: the permission
    # block, the isolation and the model would be that process's. A config folder of its own keeps the person's
    # opencode.json, plugins and MCP servers out; the login lives in the data folder and stays (probed 2.0.20).
    Tool("opencode", ("opencode", "run", "--standalone", "--format", "json"),
         help=("opencode", "run", "--help"), isolation=(), isolation_env=(("OPENCODE_CONFIG_DIR", "{empty}"),),
         usage="opencode-json", skills=".opencode/skills", model_flag="-m", args_env="FACTORY_OPENCODE_ARGS",
         add_dirs="permission", permission_env="OPENCODE_CONFIG_CONTENT"),
)


TOOL = {tool.name: tool for tool in TOOLS}


#: The built-in tools a stage process gets: the same list for every stage, so the prompt prefix is shared.
STAGE_TOOLS = "Read,Write,Edit,Glob,Grep,Bash,Skill"


def tool_help(tool):
    """The tool's help text, probed once per binary and kept beside the temp files keyed by the binary's path, size
    and time — every stage of a run gets the same flags, and a tool that is updated is probed again. "" when the
    binary is not there. FACTORY_TOOL_HELP_<TOOL> stands in for the probe."""
    stand_in = os.environ.get(f"FACTORY_TOOL_HELP_{tool.name.upper()}")
    if stand_in is not None:
        return stand_in
    binary = shutil.which(tool.help[0])
    if not binary:
        return ""
    stat = os.stat(binary)
    key = f"{os.path.realpath(binary)}|{stat.st_size}|{int(stat.st_mtime)}|{' '.join(tool.help[1:])}"
    cache = os.path.join(tempfile.gettempdir(), f"dca-factory-probes-{os.getuid() if hasattr(os, 'getuid') else 0}.json")
    try:
        with open(cache, encoding="utf-8") as handle:
            known = json.load(handle)
    except (OSError, ValueError):
        known = {}
    if key in known:
        return known[key]
    try:
        done = subprocess.run([binary, *tool.help[1:]], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""                                  # not kept: the next stage probes again
    text = done.stdout + done.stderr
    if done.returncode == 0 and text.strip():
        known[key] = text
        with contextlib.suppress(OSError):
            temporary = f"{cache}.{os.getpid()}"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(known, handle)
            os.replace(temporary, cache)
    return text


def empty_folder():
    """A folder of the pipeline's own that holds nothing: what a tool reads as its configuration folder when the
    person's must stay out."""
    folder = os.path.join(tempfile.gettempdir(), f"dca-factory-empty-{os.getuid() if hasattr(os, 'getuid') else 0}")
    with contextlib.suppress(OSError):
        os.makedirs(folder, exist_ok=True)
    if os.path.isdir(folder) and not os.listdir(folder):
        return folder
    return tempfile.mkdtemp(prefix="dca-factory-empty-")


def has_flag(help_text, flag):
    return re.search(r"(^|[\s,])" + re.escape(flag) + r"([\s,=<\[]|$)", help_text, re.M) is not None


def isolation_args(tool):
    """The isolation flags this binary knows: an older one refuses a flag it does not know and the stage would not
    start, so each is passed only where the help names it — or every one where there is no binary to ask."""
    if os.environ.get("FACTORY_ISOLATION", "on") == "off":
        return []
    help_text = tool_help(tool)
    words = []
    for group in tool.isolation:
        if not help_text or has_flag(help_text, group[0]):
            words += [word.replace("{stage_tools}", STAGE_TOOLS) for word in group]
    return words


def unprobed_flags(tool):
    """What the binary's help does not name, as (required, isolation): a fixed, model, add-dir or allow-list flag the
    record passes — a stage started with it fails — and an isolation flag the runner then leaves out, so the stage runs
    with the tool's own setup. None when the binary is not there."""
    help_text = tool_help(tool)
    if not help_text:
        return None
    flags = [w for w in tool.command[len(tool.help) - 1:] if w.startswith("-")] + [tool.model_flag]
    flags += ["--add-dir"] if tool.add_dirs in ("all", "writable") else []
    flags += ["--allowed-tools", "--disallowedTools"] if tool.allow_list else []
    missing = lambda names: sorted({flag for flag in names if not has_flag(help_text, flag)})
    return missing(flags), missing(group[0] for group in tool.isolation)


def permission_block(allowed, protected, linked, cwd=None, home=None):
    """OpenCode's permission block: the same shell as Claude's allow-list; every edit allowed but under the protected
    folders, which its edit rules match relative to the project (an absolute pattern matches nothing there — probed
    2.0.20); the linked folders as external ones it may use, and the protected ones among them refused there."""
    cwd, home = os.path.abspath(cwd or os.getcwd()), os.path.abspath(home or os.environ.get("FACTORY_HOME") or cwd or ".")
    bash = {"*": "deny"}
    for entry in allowed.split(","):
        if entry.startswith("Bash(") and entry.endswith(":*)"):
            bash[entry[5:-3] + "*"] = "allow"
    edit, external = {"*": "allow"}, {folder.rstrip("/") + "/**": "allow" for folder in linked}
    for folder in (f for f in protected if f):
        absolute = os.path.abspath(folder)
        inside = os.path.relpath(absolute, home)
        if not inside.startswith(".."):
            edit[inside.replace(os.sep, "/") + "/**"] = "deny"          # the project's, and a worktree's link of it
        if os.path.relpath(absolute, cwd).startswith(".."):
            external[absolute.rstrip("/") + "/**"] = "deny"             # the main checkout's, named by its path
    return json.dumps({"permission": {"bash": bash, "edit": edit, "external_directory": external}})


def tool_command(tool, model="", writable=(), readable=(), protected=(), allowed=""):
    """What starts one stage with this tool: the variables it is started with and its arguments, the prompt not
    among them — the caller appends it."""
    # a variable the person set is theirs and wins — a config folder that carries their local providers, say
    env = {name: value.replace("{empty}", empty_folder()) for name, value in tool.isolation_env
           if os.environ.get("FACTORY_ISOLATION", "on") != "off" and not os.environ.get(name)}
    if tool.permission_env:
        block = os.environ.get(tool.permission_env, "")
        if not block and os.environ.get("FACTORY_OPENCODE_PERMISSIONS", "on") != "off":
            block = permission_block(allowed, protected, [*writable, *readable])
        env[tool.permission_env] = block
    argv = list(tool.command)
    if tool.allow_list:
        argv += ["--allowed-tools", f"Read,Write,Edit,Glob,Grep,Skill,{allowed}"]
    if tool.add_dirs in ("all", "writable"):
        for folder in [*writable, *(readable if tool.add_dirs == "all" else ())]:
            argv += ["--add-dir", folder]
    if tool.deny and protected:
        argv += ["--disallowedTools", ",".join(f"Edit(//{d.lstrip('/')}/**)" for d in protected)]
    argv += isolation_args(tool)
    if model:
        argv += [tool.model_flag, model]
    argv += shlex.split(os.environ.get(tool.args_env, ""))
    return env, argv


def tool_invocation(tool, model="", writable=(), readable=(), protected=(), allowed=""):
    """The same command line as shell words for a caller to `eval`, with the prompt left as `"$prompt"` — the
    caller's variable, never text quoted here."""
    env, argv = tool_command(tool, model, writable, readable, protected, allowed)
    words = [f"{name}={shlex.quote(value)}" for name, value in env.items()] + [shlex.quote(w) for w in argv]
    return " ".join(words + ['"$prompt"'])


def tools_shell():
    """The tool table as the runner reads it at its start: the names, each tool's skill folder, usage format,
    extra-flags variable and model flag, as `<tool>:<value>` words — every one checked to be a plain word."""
    bad = [w for t in TOOLS for w in (t.name, t.skills, t.usage, t.args_env, t.model_flag) if not TOOL_WORD.fullmatch(w)]
    if bad:
        print(f"factory-cli: the tool table holds a value the runner cannot take as a word: {', '.join(bad)}",
              file=sys.stderr)
        return None
    pairs = lambda field: "' " + " ".join(f"{t.name}:{getattr(t, field)}" for t in TOOLS) + " '"
    return [f"TOOL_NAMES=({' '.join(t.name for t in TOOLS)})", f"TOOL_SKILLS={pairs('skills')}",
            f"TOOL_USAGE={pairs('usage')}", f"TOOL_ARGS_ENV={pairs('args_env')}",
            f"TOOL_MODEL_FLAG={pairs('model_flag')}", f"TOOL_SKILL_DIRS=({' '.join(t.skills for t in TOOLS)})",
            f"TOOL_PLUGIN_DIRS=({' '.join(t.skills for t in TOOLS if t.plugins)})"]


TOOL_WORD = re.compile(r"[A-Za-z0-9_.-][A-Za-z0-9_./-]*")
