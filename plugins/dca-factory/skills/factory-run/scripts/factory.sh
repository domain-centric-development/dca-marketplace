#!/usr/bin/env bash
# The factory outside the session: one process per stage, so every stage starts with a fresh
# context and reads only its story and its predecessor's file. Same stages, same gate, same
# files as running the skills inside a session — this only changes who holds the context.
#
#   factory.sh install [--tool claude|codex|opencode|all] [--from <skill folder>] [--copy]
#   factory.sh update [--from <skill folder>]   the newest pipeline found, same tools, links or copies
#   factory.sh run --story <id> [--tool <tool>] [--from <stage>] [--story-budget <tokens>] [--dry-run]
#   factory.sh backlog [--tool <tool>] [--watch] [--interval <s>] [--max-stages <n>]
#                      [--story-budget <tokens>] [--dry-run]
#   factory.sh status [--brief]           what runs, what waits for a human, every story, its cost
#   factory.sh status <story>             the same, with that story's cost per stage
#   factory.sh usage [--story <id>]       tokens per story and stage
#   factory.sh decisions [--story <id>]   the decision inbox
#   factory.sh schedule                   every story's state and the next one
#   factory.sh change [--staged] [--checks "<c> …"]   the profile's checks outside a story
#   factory.sh parity <config>            every implementation proves the scenario contract
#
# `run` exits 0 when the story ran through, 3 when it stopped for a decision, 4 at --max-stages,
# 5 when another worker holds the checkout, 6 when started inside an agent session with a real
# tool (FACTORY_ALLOW_NESTED=1 overrides), anything else on a failure. `backlog` runs story after story in the order `story-gate.py
# --schedule` names, past stories that wait for a decision; --watch keeps it waiting for answers.
#
# FACTORY_TOOL_CMD replaces the tool invocation entirely ($FACTORY_STAGE and $FACTORY_PROMPT are
# exported to it) — for a tool none of the adapters covers, and so the loop itself is testable.
#
# Per-tool flags come from the environment, because a model and an effort level are the
# tool's configuration and not the process': FACTORY_CLAUDE_ARGS, FACTORY_CODEX_ARGS,
# FACTORY_OPENCODE_ARGS.
#
# The tool adapters below are the only tool-specific lines in the whole pipeline. Adding a tool
# is one entry, not a change to any stage.

set -uo pipefail

STAGES=(plan test build tidy judge document)
# Which gate runs when. `plan` is the only gate that can run *before* its stage: it reads the
# backlog alone. Every other gate judges the file its stage writes — `tests.md`, the implementation,
# `document.md` — so it runs after it. Gating `test` up front would refuse every story for the
# missing file its own stage is about to write.
PRE_GATED=(plan)
POST_GATED=(test build tidy document)
GATE=".agents/factory/story-gate.py"
TASKS="tasks"
DECISIONS=".agents/factory/decisions"
STOP_FILE=".agents/factory/stop"             # exists → a backlog run stops before its next story
INVOCATIONS=0                                # agent invocations in this process
MAX_STAGES=""                                # --max-stages: the cap on them, empty for none
STORY_BUDGET=""                              # --story-budget: tokens one story may use in total
WORKER="runner:$(hostname 2>/dev/null || echo host):$$"   # this runner's name on the checkout claim

# Inside an agent session the stages run in that session (`/factory-run`); a runner started from
# there would start a tool process per stage on top of it. So `run` and `backlog` refuse to start a
# real tool when this shell belongs to a Claude Code or Codex session. FACTORY_ALLOW_NESTED=1 is the
# deliberate way past it; a stand-in (FACTORY_TOOL_CMD) and a dry run start no tool and pass.
refuse_nested() {
  [ -n "${FACTORY_TOOL_CMD:-}" ] && return 0
  [ "${FACTORY_ALLOW_NESTED:-}" = 1 ] && return 0
  if [ -n "${CLAUDECODE:-}${CLAUDE_CODE_SESSION_ID:-}${CODEX_SESSION_ID:-}${CODEX_THREAD_ID:-}" ]; then
    echo "factory: this shell belongs to an agent session — the runner would start a tool process per" >&2
    echo "factory:   stage on top of it. In the session, run the stages with /factory-run; start the" >&2
    echo "factory:   runner from a terminal of its own. FACTORY_ALLOW_NESTED=1 starts it here anyway." >&2
    return 6
  fi
}

# One worker per checkout: the gate's claim, taken before the first stage, renewed before each one,
# given back when the runner ends — however it ends.
take_checkout() {
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — the checkout is not claimed; install the pipeline" >&2; return 0; }
  "$PY" "$GATE" --claim "$WORKER" || {
    echo "factory: another worker holds this checkout — see 'factory.sh status'. Nothing was started." >&2
    return 5; }
  trap '"$PY" "$GATE" --release "$WORKER" >/dev/null 2>&1' EXIT
}

# Which Python runs the gate. `python3` is the POSIX spelling; on Windows the interpreter is
# `python` and `python3` is often a Store stub that opens a shop window. FACTORY_PYTHON overrides,
# for a project that pins one. Resolved once, and the *name* is what reaches the profile and the
# permission list, so both stay portable between machines.
PY="${FACTORY_PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3
  elif command -v python >/dev/null 2>&1; then PY=python
  else PY=python3; fi                          # named in the error the first call then produces
fi

# Whether `ln -s` in this shell makes a symlink. On Windows (Git Bash, MSYS2) it needs developer
# mode or an administrator *and* `MSYS=winsymlinks:nativestrict`; without those it silently makes
# a *copy* — a copy that then looks like a link to the rest of this script and is stale from the
# first edit. Probed, not inferred from the platform, so a Windows that can link gets links; where
# it cannot, the install copies openly and says so.
can_symlink() {
  local probe; probe=$(mktemp -d 2>/dev/null) || return 1
  : > "$probe/a"
  ln -s "$probe/a" "$probe/b" 2>/dev/null && [ -L "$probe/b" ]
  local result=$?
  rm -rf "$probe"
  return $result
}

# A stage is finished when its hand-over file exists. The names are the file contract's, not the
# stage names — the test stage writes `tests.md`, because the table in it maps several tests.
stage_file() {
  case "$1" in
    test) echo "tests.md" ;;
    *)    echo "$1.md" ;;
  esac
}

usage() { sed -n '2,25p' "$0" >&2; exit 2; }

# An install step that had to work and did not. `set -e` is deliberately *not* used: the run loop
# expects non-zero exits in several places — a gate that refuses, a tool that stops, a verdict that
# sends the story back — and a shell that aborts on the first one would turn a normal refusal into a
# crash. So the steps that must not fail silently say so one by one. An install that could not write
# the gate has installed nothing, and reporting success there is the one failure mode that leaves a
# project believing it is governed.
must() {                                    # must <what> <command...>
  local what=$1; shift
  "$@" || { echo "factory: could not $what — install aborted, the project is unchanged from here on." >&2; exit 1; }
}

# A gate script states two things about itself: VERSION (where this copy came from) and CONTRACT
# (the version of the files it reads and writes). Read them out of the file, because the copy in a
# project is the only thing that knows which release governs that project.
gate_field() {                              # gate_field <file> <VERSION|CONTRACT>
  [ -f "$1" ] || return 1
  sed -n "s/^$2 = *//p" "$1" | head -1 | tr -d '"' | tr -d "'"
}

#: What the project records about the pipeline it installed. Three facts, no paths and no
#: timestamps, so the file belongs in the repository: a reviewer and a CI run can see which version
#: of the pipeline governs this project, and every checkout reads the same thing. Where the plugin
#: sits is a property of a machine, not of the project, so it is resolved when it is needed instead
#: of being frozen here — an absolute path written on one machine is wrong on every other one.
STAMP=".agents/factory/gate.installed"

# The pipeline's own copy of the gate, for comparison against the project's copy. In order: an
# explicit override, the checkout this script is running from (the usual case — the runner is
# started out of the plugin), and the skill links an install may have left. When none of them
# resolves there is simply nothing to compare, which is a silence, not a finding.
plugin_gate() {
  local skills; skills=$(plugin_skills) || return 1
  echo "$skills/factory-run/scripts/story-gate.py"
}

# The pipeline's skill folder this project can update from, the newest one found: an explicit
# FACTORY_PLUGIN_DIR, the checkout this script runs from, the skill folders the install linked or
# copied, and Claude Code's plugin cache. A copy of the skills in the project is a candidate too, so
# "newest" decides, not the order — the project's own copy is never the answer when a newer one exists.
plugin_skills() {
  local candidate dir best="" best_version="" version own
  own=$(cd "$(dirname "$GATE")" 2>/dev/null && pwd)
  for candidate in \
      "${FACTORY_PLUGIN_DIR:-}" \
      "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)" \
      .claude/skills .codex/skills .opencode/skills \
      "$HOME"/.claude/plugins/cache/*/dca-factory/*/skills; do
    [ -n "$candidate" ] && [ -f "$candidate/factory-run/scripts/story-gate.py" ] || continue
    dir=$(cd "$candidate" && pwd -P)
    [ "$dir/factory-run/scripts" = "$own" ] && continue                # the project's own copy of the gate
    version=$(gate_field "$dir/factory-run/scripts/story-gate.py" VERSION)
    if [ -z "$best" ] || [ "$(printf '%s\n%s\n' "$best_version" "$version" | sort -V | tail -1)" != "$best_version" ]; then
      best=$dir; best_version=$version
    fi
  done
  [ -n "$best" ] && echo "$best"
}

# How the project holds the skills for one tool: `link` (into a checkout or cache — live), `copy`
# (its own folders — pinned, committed with the project), or nothing for a tool it does not use.
skills_mode() {                             # skills_mode <target dir>
  local target=$1
  [ -L "$target" ] && { echo link; return; }
  [ -d "$target/factory-run" ] || { echo ""; return; }
  [ -L "$target/factory-run" ] && echo link || echo copy
}

# Bring the project up to the newest pipeline found, for exactly the tools it already has, keeping
# links as links and copies as copies. The profile is the project's and is never rewritten; a file
# contract that moved is said out loud, with the profile line to raise.
update_project() {                          # update_project <explicit skill folder or "">
  local src=${1:-} before before_contract after after_contract tool target mode declared updated=0
  [ -n "$src" ] || src=$(plugin_skills) || {
    echo "factory: no pipeline found to update from — pass --from <the plugin's skills folder>" >&2; return 2; }
  [ -f "$src/factory-run/scripts/story-gate.py" ] || {
    echo "factory: $src is not the pipeline's skills folder (no factory-run/scripts/story-gate.py)" >&2; return 2; }
  before=$(sed -n 's/^version:[[:space:]]*//p' "$STAMP" 2>/dev/null | head -1)
  before_contract=$(sed -n 's/^contract:[[:space:]]*//p' "$STAMP" 2>/dev/null | head -1)
  # The install is the *new* pipeline's, not this copy's: a release that adds a file the project
  # needs must be able to put it there, even when the project's runner predates it.
  local installer="$src/factory-run/scripts/factory.sh"
  for tool in claude codex opencode; do
    target=".$tool/skills"
    mode=$(skills_mode "$target")
    [ -n "$mode" ] || continue
    if [ "$mode" = copy ]; then
      bash "$installer" install --tool "$tool" --from "$src" --copy || return $?
    else
      bash "$installer" install --tool "$tool" --from "$src" || return $?
    fi
    updated=1
  done
  [ "$updated" = 1 ] || bash "$installer" install --tool none --from "$src" || return $?
  after=$(gate_field "$GATE" VERSION); after_contract=$(gate_field "$GATE" CONTRACT)
  echo "factory: updated ${before:-an unstamped install} → $after (file contract ${before_contract:-?} → $after_contract) from $src"
  declared=$(sed -n 's/^contract:[[:space:]]*//p' .agents/factory/factory.profile.yaml 2>/dev/null | head -1)
  if [ -n "$declared" ] && [ "$declared" != "$after_contract" ]; then
    echo "factory: the stack profile declares contract $declared — raise it to 'contract: $after_contract' once" >&2
    echo "factory:   the profile uses what that contract describes; the gate reads it as older until then." >&2
  fi
  echo "factory: review and commit the changed files — the update commits nothing."
}

# Whether the gate in this project is still the one the pipeline ships. The gate itself cannot tell:
# a copied script has nothing to compare against. A difference in VERSION is an update to run, never
# a reason to refuse a story; an incompatible *contract* is refused by the gate, against the
# profile, which is where it shows.
check_gate_freshness() {
  [ -f "$STAMP" ] || return 0
  local source installed_version source_version installed_contract source_contract
  source=$(plugin_gate) || return 0
  installed_version=$(sed -n 's/^version:[[:space:]]*//p' "$STAMP" | head -1)
  installed_contract=$(sed -n 's/^contract:[[:space:]]*//p' "$STAMP" | head -1)
  source_version=$(gate_field "$source" VERSION) || return 0
  source_contract=$(gate_field "$source" CONTRACT)
  if [ "$installed_contract" != "$source_contract" ]; then
    echo "factory: this project was installed against file contract $installed_contract and the" >&2
    echo "factory:   pipeline here implements $source_contract — run 'factory.sh install' and check" >&2
    echo "factory:   the stack profile's 'contract:' line before trusting a run." >&2
  elif [ "$installed_version" != "$source_version" ]; then
    echo "factory: this project was installed from pipeline $installed_version, the one here is" >&2
    echo "factory:   $source_version — same file contract, so the run is valid; 'factory.sh install'" >&2
    echo "factory:   brings the project up to date." >&2
  fi
}

# --- tool adapters -----------------------------------------------------------

detect_tool() {
  for candidate in claude codex opencode; do
    command -v "$candidate" >/dev/null 2>&1 && { echo "$candidate"; return; }
  done
  echo ""
}

# The commands a stage must be allowed to run: the gate and whatever the stack profile declares.
# A tool that asks for permission has nobody to ask in a headless run, and a project settings file
# is ignored while the workspace is untrusted — so the allowlist is passed on the command line.
allowed_commands() {
  local profile="${FACTORY_PROFILE:-.agents/factory/factory.profile.yaml}"
  local list="Bash($PY $GATE:*)"
  if [ -f "$profile" ]; then
    local head
    for key in compile test e2eTest architecture format; do
      head=$(sed -n "s/^$key:[[:space:]]*//p" "$profile" | head -1 | tr -d '"'"'"'"' | awk '{print $1}')
      [ -n "$head" ] && case "$list" in *"Bash($head:*)"*) ;; *) list="$list,Bash($head:*)" ;; esac
    done
  fi
  echo "$list"
}

# A stage process sees the project and nothing else: not the person's own skills, plugins or MCP
# servers, and not a second copy of this pipeline from an installed plugin — which one a stage would
# pick is chance, and a colleague with other plugins would get another pipeline. It also starts
# smaller: the built-in tools no stage uses cost context on every turn. The tool list is the same
# for every stage, and nothing in the system prompt changes between stages, so from the second
# stage on the tool's prompt cache serves the prefix instead of writing it again.
# FACTORY_ISOLATION=off runs a stage with the tool's full setup, for a run that needs something the
# project does not carry; the run says so.
STAGE_TOOLS="Read,Write,Edit,Glob,Grep,Bash,Skill"
isolated() { [ "${FACTORY_ISOLATION:-on}" != off ]; }
isolation_flags() {                         # isolation_flags <tool>
  isolated || return 0
  case "$1" in
    claude)
      local help="" flag want
      # An older CLI refuses a flag it does not know and the stage would not start; ask it once.
      command -v claude >/dev/null 2>&1 && help=${CLAUDE_HELP:-$(claude --help 2>/dev/null)}
      for want in "--setting-sources project" "--strict-mcp-config" "--tools $STAGE_TOOLS" \
                  "--exclude-dynamic-system-prompt-sections"; do
        flag=${want%% *}
        if [ -z "$help" ] || printf '%s' "$help" | grep -q -- "$flag"; then printf '%s ' "$want"; fi
      done ;;
    codex)
      # The user's config.toml (MCP servers, profiles, a model) stays out; the login does not.
      local help=""
      command -v codex >/dev/null 2>&1 && help=$(codex exec --help 2>/dev/null)
      if [ -z "$help" ] || printf '%s' "$help" | grep -q -- "--ignore-user-config"; then
        printf '%s ' "--ignore-user-config"
      fi ;;
    opencode) printf '%s ' "--pure" ;;
  esac
}

# The craft a profile names — carrier.<stage>, review.<perspective>, knowledge — has to be in the
# project's own skill directory, because an isolated stage sees nothing else. Checked before the
# first invocation, so a missing carrier stops the run instead of every stage quietly falling back.
skill_dir_of() { case "$1" in claude) echo .claude/skills ;; codex) echo .codex/skills ;; opencode) echo .opencode/skills ;; esac; }
named_carriers() {
  local profile="${FACTORY_PROFILE:-.agents/factory/factory.profile.yaml}"
  [ -f "$profile" ] || profile=factory.profile.yaml      # the gate's second place for it
  [ -f "$profile" ] || return 0
  sed -n -E 's/^(carrier\.[a-z]+|review\.[a-z-]+|knowledge):[[:space:]]*//p' "$profile" \
    | tr -d '"'"'"'"' | awk '{print $1}' | sed 's/.*://' | sort -u
}
check_carriers() {                          # check_carriers <tool>
  [ -n "${FACTORY_TOOL_CMD:-}" ] && return 0
  isolated || return 0
  local dir missing="" name; dir=$(skill_dir_of "$1")
  [ -n "$dir" ] || return 0
  for name in $(named_carriers); do
    [ -f "$dir/$name/SKILL.md" ] || missing="$missing $name"
  done
  [ -z "$missing" ] && return 0
  echo "factory: the profile names carrier(s) the project does not hold in $dir:$missing" >&2
  echo "factory:   a stage process sees only the project — run 'factory.sh install --tool $1' (or update)" >&2
  echo "factory:   so they are linked there, or FACTORY_ISOLATION=off to use the tool's own setup." >&2
  return 2
}

# A local model loaded with a context window smaller than a stage grows to truncates or aborts in
# silence. LM Studio says how large the loaded window is; below this, the run warns before it starts.
LOCAL_CONTEXT_MIN=${FACTORY_LOCAL_CONTEXT_MIN:-65536}
check_local_context() {                     # check_local_context <tool>
  [ "$1" = opencode ] || return 0
  local model; model=$(model_flag opencode)
  case "$model" in lmstudio*/*) ;; *) return 0 ;; esac
  command -v curl >/dev/null 2>&1 || return 0
  local id=${model#*/} loaded
  loaded=$(curl -s -m 2 "${FACTORY_LMSTUDIO_URL:-http://localhost:1234}/api/v0/models" 2>/dev/null \
    | "$PY" -c "import json,sys
try: data=json.load(sys.stdin)
except Exception: sys.exit(0)
for m in data.get('data',[]):
    if m.get('id')==sys.argv[1]: print(m.get('loaded_context_length') or 0)" "$id" 2>/dev/null)
  if [ -z "$loaded" ]; then
    echo "factory: note — the context window of $model could not be read; a stage needs ${LOCAL_CONTEXT_MIN}+ tokens" >&2
  elif [ "$loaded" -lt "$LOCAL_CONTEXT_MIN" ]; then
    echo "factory: $model is loaded with a ${loaded}-token context window; a stage grows past ${LOCAL_CONTEXT_MIN}." >&2
    echo "factory:   reload it with a larger context length in LM Studio, or set FACTORY_LOCAL_CONTEXT_MIN." >&2
  fi
  return 0
}

invoke() {                                  # invoke <tool> <prompt>
  local tool=$1 prompt=$2
  # Which model, which effort, which sandbox a tool runs with is the tool's configuration and not
  # the pipeline's — but a default that does not work stops the run, so each adapter takes extra
  # flags from the environment: FACTORY_CLAUDE_ARGS, FACTORY_CODEX_ARGS, FACTORY_OPENCODE_ARGS.
  # Example: FACTORY_OPENCODE_ARGS="--model <provider>/<model>" where the default provider is not
  # authenticated. The pipeline never chooses a model; it only stops standing in the way of one.
  # One seam, for two honest purposes: a project whose tool is none of the three can plug it in,
  # and the runner's own loop can be exercised without a model — which is the only way a defect in
  # the loop is found by a test rather than by a wasted run.
  INVOCATIONS=$((INVOCATIONS + 1))
  # The tool's own output is kept per invocation (`$raw`), because it is also where the tool says
  # what the stage cost. Claude and Codex are asked for their machine-readable form; the runner
  # prints the stage's final message from it, so the log still reads as text.
  local raw="${invocation_raw:-/dev/null}"
  if [ -n "${FACTORY_TOOL_CMD:-}" ]; then
    FACTORY_STAGE="${stage_in_flight:-}" FACTORY_STORY="${story_in_flight:-}" FACTORY_PROMPT="$prompt" \
      sh -c "$FACTORY_TOOL_CMD" > "$raw"
    local code=$?
    [ "$raw" = /dev/null ] || { [ -n "${FACTORY_USAGE_FORMAT:-}" ] || cat "$raw"; }
    return $code
  fi
  case "$tool" in
    claude)   claude -p "$prompt" --permission-mode acceptEdits --output-format json \
                --allowed-tools "Read,Write,Edit,Glob,Grep,Skill,$(allowed_commands)" \
                $(isolation_flags claude) ${FACTORY_CLAUDE_ARGS:+$FACTORY_CLAUDE_ARGS} > "$raw" ;;
    # stdin closed: `codex exec` also reads a prompt from stdin, and an unattended run has none.
    codex)    codex exec --json -s workspace-write $(isolation_flags codex) \
                -c sandbox_workspace_write.network_access=true \
                ${FACTORY_CODEX_ARGS:+$FACTORY_CODEX_ARGS} "$prompt" < /dev/null > "$raw" ;;
    opencode) opencode run --format json $(isolation_flags opencode) \
                ${FACTORY_OPENCODE_ARGS:+$FACTORY_OPENCODE_ARGS} "$prompt" < /dev/null > "$raw" ;;
    *)        echo "factory: unknown tool '$tool'" >&2; return 2 ;;
  esac
}

# Which format a tool's raw output is in, for the usage reading.
usage_format() {                            # usage_format <tool>
  if [ -n "${FACTORY_TOOL_CMD:-}" ]; then echo "${FACTORY_USAGE_FORMAT:-none}"; return; fi
  case "$1" in
    claude) echo claude-json ;;
    codex)  echo codex-jsonl ;;
    opencode) echo opencode-json ;;
    *)      echo none ;;
  esac
}

# The model a tool ran with, where its output does not say: the -m/--model in its extra flags.
model_flag() {                              # model_flag <tool>
  local args=""
  case "$1" in codex) args="${FACTORY_CODEX_ARGS:-}" ;; opencode) args="${FACTORY_OPENCODE_ARGS:-}" ;; esac
  # -E: BSD sed (macOS) has no `\|` in a basic expression, so the alternation is written extended
  printf '%s\n' "$args" | sed -n -E 's/.*(-m|--model)[ =]([^ ]*).*/\2/p' | head -1
}

# One `usage` line in the story's journal per invocation, and the stage's final message on screen.
record_usage() {                            # record_usage <story> <stage> <tool> <raw> [seconds]
  local out fields
  out=$("$PY" "$GATE" --usage-from "$(usage_format "$3")" "$4" --usage-model "$(model_flag "$3")" 2>/dev/null) \
    || out="unknown"
  fields=$(printf '%s\n' "$out" | head -1)
  [ -n "${5:-}" ] && fields="$fields	seconds=$5"
  [ "$(usage_format "$3")" = none ] || printf '%s\n' "$out" | sed '1d'
  printf '%s\tusage\t%s\ttool=%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$2" "$3" "$fields" \
    >> "$TASKS/$1/.verify/journal.tsv"
}

# --- install -----------------------------------------------------------------


# Whether a directory holds nothing but links into the given source — then it is ours to replace
# with one link, and no project-owned skill is lost.

# The craft skills a stack profile may name as a carrier, where they sit next to this pipeline in
# the same checkout. Claude Code finds them through its plugins; a tool without that mechanism
# finds only what the project's own skill directory holds.

# Whether a link points into one of the directories we install from — the only links this install
# may replace or prune. Anything else in that directory is the project's and is left alone.
ours() {                                    # ours <target> <source> <method dirs>
  local target=$1 dir
  for dir in $2 $3; do
    case "$target" in "$dir"/*) return 0 ;; esac
  done
  return 1
}

method_skill_dirs() {
  local source_abs=$1 plugins dir found=""
  plugins=$(cd "$source_abs/../.." 2>/dev/null && pwd) || return 0
  for dir in "$plugins"/*/skills; do
    [ -d "$dir" ] || continue
    [ "$(cd "$dir" && pwd)" = "$source_abs" ] && continue
    found="$found $(cd "$dir" && pwd)"
  done
  echo "$found"
}

only_links_into() {
  local dir=$1 source_abs=$2 entry
  [ -d "$dir" ] || return 1
  for entry in "$dir"/* "$dir"/.[!.]*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    [ -L "$entry" ] || return 1
    case "$(readlink "$entry")" in "$source_abs"/*) ;; *) return 1 ;; esac
  done
  return 0
}

# The carriers the profile names, into a skill directory that does not already get every craft
# skill: Claude Code's (whose stage processes see only the project) and any directory a copy install
# wrote. Only what the profile names, so an isolated stage's prefix does not grow by skills it never
# uses; linked where the install links, copied where it copies (and then listed as the pipeline's).
install_named_carriers() {                  # install_named_carriers <target> <source_abs> <copy_mode>
  local target=$1 source_abs=$2 copy_mode=$3 name dir found method_dirs
  method_dirs=$(method_skill_dirs "$source_abs")
  for name in $(named_carriers); do
    [ -f "$target/$name/SKILL.md" ] && ! { [ -L "$target/$name" ] && ! [ -e "$target/$name" ]; } && continue
    found=""
    for dir in $method_dirs; do [ -d "$dir/$name" ] && { found="$dir/$name"; break; }; done
    if [ -z "$found" ]; then
      echo "factory: the profile names carrier '$name', which no plugin beside the pipeline provides — add it to $target" >&2
      continue
    fi
    if [ -n "$copy_mode" ]; then
      rm -rf "${target:?}/$name" && cp -R "$found" "$target/$name" && echo "$name" >> "$target/.dca-factory-skills"
    else
      ln -sfn "$found" "$target/$name"
    fi
    echo "factory: carrier $name → $target"
  done
}

install_skills() {
  local tool=${1:-all} from=${2:-} copy_mode=${3:-}
  if [ -z "$from" ]; then
    from="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # the skill folder
  fi
  local targets=()
  case "$tool" in
    claude)   targets=(.claude/skills) ;;
    codex)    targets=(.codex/skills) ;;
    opencode) targets=(.opencode/skills) ;;
    all)      targets=(.claude/skills .codex/skills .opencode/skills) ;;
    none)     targets=() ;;                  # only the project's files: gate, runner, hook, stamp
    *)        usage ;;
  esac
  local source_abs; source_abs=$(cd "$from" && pwd)
  local copy_reason=""
  if [ -z "$copy_mode" ] && ! can_symlink; then
    copy_mode=1; copy_reason=" — this shell cannot make symlinks (Windows without developer mode or MSYS=winsymlinks:nativestrict), so the install copies"
  fi
  for target in "${targets[@]}"; do
    # A copy of a skill folder is a second truth: an edit at the source does not reach the project,
    # and the project keeps running yesterday's process while its author believes otherwise (that
    # is how a whole set of runs can use a stale stage). So a local source is *linked* by default;
    # --copy is for a real distribution, where there is no source directory to point at.
    #
    # The *whole directory* is linked where it can be, not one link per skill: per-skill links
    # freeze the set at install time, so a skill added later never appears and the project runs an
    # incomplete pipeline without a word. Where the project keeps skills of its own in that
    # directory, each skill is linked individually instead and the freeze is named.
    if [ -n "$copy_mode" ]; then
      # A copy looks like a skill of the project's own, so the install keeps a list of what it copied
      # (`.dca-factory-skills`): only those are its to replace, and one the pipeline no longer has is
      # removed. A folder of the project's own with a pipeline skill's name is left alone and named.
      must "create $target" mkdir -p "$target"
      local manifest="$target/.dca-factory-skills" previous="" skill name copied=0 kept=0 removed=0
      if [ -f "$manifest" ]; then
        previous=$(cat "$manifest")
      elif [ -d "$target/factory-run" ] && [ ! -L "$target/factory-run" ]; then
        # a copy from before the list: the folders named like the pipeline's skills are the pipeline's
        previous=$(for skill in "$source_abs"/*; do [ -d "$skill" ] && basename "$skill"; done)
      fi
      : > "$manifest.new"
      for skill in "$source_abs"/*; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        if { [ -e "$target/$name" ] || [ -L "$target/$name" ]; } && ! printf '%s\n' "$previous" | grep -qx "$name"; then
          echo "factory: kept the project's own $target/$name — the pipeline's $name was not copied" >&2
          kept=$((kept + 1))
          continue
        fi
        rm -rf "${target:?}/$name"
        must "copy $name into $target" cp -R "$skill" "$target/$name"
        echo "$name" >> "$manifest.new"
        copied=$((copied + 1))
      done
      for name in $previous; do
        [ -d "$source_abs/$name" ] && continue
        rm -rf "${target:?}/$name"
        removed=$((removed + 1))
        echo "factory: removed $target/$name — the pipeline no longer has it" >&2
      done
      mv -f "$manifest.new" "$manifest"
      echo "factory: skills → $target ($copied copied${copy_reason}; $kept of the project's own kept, $removed removed)"
      continue
    fi
    local method_dirs; method_dirs=$(method_skill_dirs "$source_abs")
    if [ -n "$method_dirs" ] && [ "$target" != ".claude/skills" ]; then
      # A tool without a plugin mechanism finds *only* what is in this directory, so the craft the
      # profile names as a carrier (`carrier.build:`, `review.<perspective>:`) has to be here too —
      # otherwise the pipeline ports and the craft does not, and every stage falls back with a note.
      # Several sources cannot be one directory link, so these are per skill: an edited skill is
      # still live, but a *newly added* one needs another install, and that is said out loud.
      mkdir -p "$target"
      # Never wipe the directory: a project may keep skills of its own in it, and an install that
      # deletes them while reporting success is the worst kind of helpfulness. Only links that
      # point into a source we install from are ours to replace, and a stale one — its skill gone
      # from the source — is pruned and named.
      local linked=0 kept=0 pruned=0 dir skill entry name
      for entry in "$target"/*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        if [ -L "$entry" ] && ours "$(readlink "$entry")" "$source_abs" "$method_dirs"; then
          [ -e "$entry" ] || { rm -f "$entry"; pruned=$((pruned + 1)); }   # its skill is gone
          continue
        fi
        kept=$((kept + 1))
      done
      for dir in "$source_abs" $method_dirs; do
        for skill in "$dir"/*; do
          [ -d "$skill" ] || continue
          name=$(basename "$skill")
          # Ours to replace only if it is a link into a source we install from. A directory the
          # project keeps here is obvious; a *link* the project made is just as much its own, and
          # overwriting it silently swaps a skill under someone's feet.
          if [ -e "$target/$name" ] || [ -L "$target/$name" ]; then
            if ! { [ -L "$target/$name" ] && ours "$(readlink "$target/$name")" "$source_abs" "$method_dirs"; }; then
              echo "factory: kept the project's own $target/$name — the pipeline's $name was not installed" >&2
              kept=$((kept + 1))
              continue
            fi
          fi
          ln -sfn "$skill" "$target/$name"
          linked=$((linked + 1))
        done
      done
      [ "$kept" -gt 0 ] && echo "factory: left $kept entry/entries in $target that are the project's own" >&2
      [ "$pruned" -gt 0 ] && echo "factory: pruned $pruned link(s) whose skill is gone from the source" >&2
      echo "factory: skills → $target ($linked linked: the pipeline plus the craft it names as carriers)"
      echo "factory:   per skill, because they come from several sources — re-run install after a skill is added" >&2
    elif [ "$target" = ".claude/skills" ] && [ -n "$(named_carriers)" ] \
         && { [ -L "$target" ] || [ ! -e "$target" ] || only_links_into "$target" "$source_abs"; }; then
      # The profile names carriers, and an isolated Claude stage sees only this directory — so it
      # holds the pipeline's skills one link each, with the named carriers beside them. Per skill
      # freezes the set: a skill added to the pipeline later needs another install (or update).
      [ -L "$target" ] && must "replace the $target link" rm -f "$target"
      must "create $target" mkdir -p "$target"
      local skill linked=0
      for skill in "$source_abs"/*; do
        [ -d "$skill" ] || continue
        ln -sfn "$skill" "$target/$(basename "$skill")"
        linked=$((linked + 1))
      done
      echo "factory: skills → $target ($linked linked one by one, beside the carriers the profile names)"
      echo "factory:   re-run install after a skill is added to the pipeline" >&2
    elif [ -L "$target" ] || [ ! -e "$target" ] || only_links_into "$target" "$source_abs"; then
      must "replace $target" rm -rf "$target"
      must "create $(dirname "$target")" mkdir -p "$(dirname "$target")"
      must "link $target to the pipeline" ln -s "$source_abs" "$target"
      echo "factory: skills → $target (linked to $from — a skill added there appears at once)"
    else
      mkdir -p "$target"
      for skill in "$source_abs"/*; do
        [ -d "$skill" ] || continue
        rm -rf "$target/$(basename "$skill")"
        ln -s "$skill" "$target/$(basename "$skill")"
      done
      echo "factory: skills → $target (per skill: the directory holds skills of its own)" >&2
      echo "factory:   re-run install after a skill is added to the source" >&2
    fi
  done
  for target in "${targets[@]}"; do
    # The whole-directory link to the pipeline cannot take a carrier beside it: the carrier would be
    # written into the plugin's own folder. Then the tool finds the carrier through its plugins, and
    # an isolated stage does not — the runner's carrier check says so before a run.
    [ -L "$target" ] && continue
    if [ "$target" = ".claude/skills" ] || [ -n "$copy_mode" ]; then
      install_named_carriers "$target" "$source_abs" "$copy_mode"
    fi
  done
  check_dca_setup
  must "create .agents/factory and .githooks" mkdir -p .agents/factory .githooks
  must "copy the gate to $GATE" cp "$from/factory-run/scripts/story-gate.py" "$GATE"
  # The runner goes beside the gate, so the project has one entry point for everything it does with
  # the pipeline: `bash .agents/factory/factory.sh run|backlog|status|usage|…`. Installing again is
  # done from the plugin's copy, which knows where the skills are.
  # Replaced, never written over: `update` runs from this very file, and bash reads a script as it
  # goes — a copy onto the same inode would change the lines it has not read yet.
  must "copy the runner to .agents/factory/factory.sh" cp "$from/factory-run/scripts/factory.sh" .agents/factory/.factory.sh.new
  must "make the runner executable" chmod +x .agents/factory/.factory.sh.new
  must "put the runner in place" mv -f .agents/factory/.factory.sh.new .agents/factory/factory.sh
  must "copy the commit hook to .githooks/pre-commit" \
    cp "$from/factory-run/templates/githooks/pre-commit" .githooks/pre-commit
  must "make the gate and the commit hook executable" chmod +x .githooks/pre-commit "$GATE"
  # Which pipeline this project is governed by — committed with the project, so it is the same
  # answer for everyone who checks it out. Deliberately no path and no timestamp: both describe the
  # machine that happened to run the install, and neither survives a second developer.
  {
    echo "plugin: dca-factory"
    echo "version: $(gate_field "$GATE" VERSION)"
    echo "contract: $(gate_field "$GATE" CONTRACT)"
  } > "$STAMP"
  echo "factory: gate → $GATE (version $(gate_field "$GATE" VERSION), file contract $(gate_field "$GATE" CONTRACT))"
  # Not a `must`: the project need not be a git repository for the gate to work, and a checkout
  # without git is a legitimate place to run the pipeline. The hook is then absent, and said to be.
  if git config core.hooksPath .githooks 2>/dev/null; then
    echo "factory: git hooks → .githooks"
  else
    echo "factory: no git repository here — .githooks/pre-commit is installed but nothing runs it." >&2
  fi
  [ -f .agents/factory/factory.profile.yaml ] || write_profile "$from"
  case "$tool" in
    claude|all) write_claude_permissions ;;
  esac
  # The journal is append-only, one line per event: two branches that ran the same story both add
  # lines at its end, which git reports as a conflict although keeping both is always right.
  if ! grep -qs "journal.tsv merge=union" .gitattributes; then
    printf '%s\n' "tasks/**/.verify/journal.tsv merge=union" >> .gitattributes
    echo "factory: .gitattributes merges the story journals by keeping both sides (merge=union)"
  fi
  write_agents_block
  if [ -n "$copy_mode" ]; then
    echo "factory: the skills are copies — commit .claude/.codex/.opencode skills with the project, and"
    echo "factory:   every clone delivers stories with this pipeline, without the marketplace."
  elif [ "${#targets[@]}" -gt 0 ]; then
    echo "factory: the skill links point into $source_abs — they belong in .gitignore; a clone"
    echo "factory:   installs them again, or use --copy to commit the skills with the project."
  fi
}

check_dca_setup() {
  # The factory delivers stories; it does not install an architecture. That is the bootstrap
  # skill's job, and it runs once. Say so instead of quietly starting without one.
  # `find`, not a glob: `**` without `shopt -s globstar` is one `*`, so an architecture test one
  # directory further down — which is where every real source layout puts it — went unseen and the
  # install told the project it had no governance.
  if find . -name "ArchitectureTest*" -not -path "*/build/*" -not -path "*/bin/*" \
        -not -path "*/obj/*" -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null \
        | head -1 | grep -q . \
     || grep -rqs "dca-archunit\|DomainCentric.ArchRules" --include="*.gradle" --include="*.kts" \
        --include="pom.xml" --include="*.csproj" --include="*.props" . 2>/dev/null; then
    echo "factory: architecture governance found — the pipeline has something to gate on."
  else
    echo "factory: no architecture governance found in this project." >&2
    echo "factory: run the DCA bootstrap skill (/dca-bootstrap) first — it adds the building" >&2
    echo "factory:   blocks and the rule catalog, and it is what the build gate checks against." >&2
    echo "factory: installing the pipeline anyway; its architecture check will be skipped and named." >&2
  fi
}

conventions_file() {
  for candidate in .agents/dca/conventions.md .claude/dca/conventions.md; do
    [ -f "$candidate" ] && { echo "$candidate"; return; }
  done
  echo ""
}

write_profile() {
  # Prefill from what the project already states, so the profile is not a second truth.
  local from=$1 conventions
  conventions=$(conventions_file)
  must "copy the stack-profile template" \
    cp "$from/factory-run/templates/factory.profile.yaml.tmpl" .agents/factory/factory.profile.yaml
  local compile="" test="" architecture="" filter_flag="" filter_format="" covers=""
  # The selector syntax belongs to the runner, not to the language: writing a Gradle selector into
  # a .NET profile makes every single-test invocation of the gate select nothing, and a test that
  # runs nothing looks exactly like a red one.
  if [ -f gradlew ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; then
    compile="./gradlew testClasses"; test="./gradlew test"; architecture="./gradlew test-architecture"
    filter_flag="--tests"; filter_format='"{class}.{method}"'
  elif [ -f pom.xml ]; then
    compile="./mvnw test-compile"; test="./mvnw test"; architecture="./mvnw -Dtest=*ArchitectureTest test"
    filter_flag="-Dtest"; filter_format='"{class}#{method}"'
  elif compgen -G "./*.sln" >/dev/null || compgen -G "./*.slnx" >/dev/null || compgen -G "./*.csproj" >/dev/null; then
    # `dotnet test` takes one project per invocation; several paths in one call is an MSBuild error.
    # `--logger trx`: the gate reads what actually ran from the runner's report, and the .NET test
    # platform writes one only when asked. Without it every verdict would rest on an exit code.
    compile="dotnet build"; test="dotnet test --logger trx"
    architecture="dotnet test --filter FullyQualifiedName~Architecture"
    filter_flag="--filter"; filter_format='"FullyQualifiedName~{class}.{method}"'
    # Without a project argument `dotnet test` runs every test project of the solution, so this
    # command's scope is the whole project. A Gradle or Maven task is *not* that — `./gradlew test`
    # runs one source set — which is why this is declared here rather than guessed by the gate.
    covers="**"
  elif [ -f pytest.ini ] || [ -f conftest.py ] || grep -qs "^\[tool\.pytest" pyproject.toml || grep -qs "^\[pytest\]" setup.cfg tox.ini; then
    # pytest selects by path — `tests/test_x.py::test_y` — so the filter names the file the gate
    # located, not a dotted class. `--junitxml` puts the report where the gate looks by convention.
    # No `compile:`: Python has none worth the name, and a skipped check is named, not faked.
    test="$PY -m pytest -q --junitxml=test-results/pytest.xml"
    filter_format='"{file}::{method}"'
    covers="**"
  fi
  if [ -n "$conventions" ]; then
    local stated
    stated=$(grep -oE '`[^`]*(gradlew|mvnw|dotnet)[^`]*`' "$conventions" | tr -d '`' | grep -iE "arch" | head -1)
    [ -n "$stated" ] && architecture="$stated"
    echo "factory: read build facts from $conventions"
  fi
  "$PY" - "$compile" "$test" "$architecture" "$filter_flag" "$filter_format" "$covers" <<'PYEOF'
import sys
compile_, test, architecture, filter_flag, filter_format, covers = sys.argv[1:7]
path = ".agents/factory/factory.profile.yaml"
lines = open(path).read().splitlines()
values = {
    "compile": compile_,
    "test": test,
    "e2eTest": test,
    "architecture": architecture,
    "filterFlag": filter_flag,
    "filterFormat": filter_format,
}
out = []
for line in lines:
    key = line.split(":", 1)[0].strip()
    if key in values and values[key] and "{{" in line:
        out.append(f"{key}: {values[key]}")
    elif "{{" in line:
        # An undetected command is left out, not left as a placeholder: the gate skips and names
        # what the profile does not declare, but it would try to run a placeholder.
        continue
    else:
        out.append(line)
if covers:
    out.append(f"covers.test: {covers}")
open(path, "w").write("\n".join(out) + "\n")
PYEOF
  echo "factory: wrote .agents/factory/factory.profile.yaml — check the commands, then add"
  echo "factory:   knowledge:, carrier.<stage>: and review.<perspective>: where the project has them"
}

# The instruction every tool reads: a block in AGENTS.md between two markers. Only the block is the
# pipeline's — it is replaced on every install and update; the rest of the file is the project's.
write_agents_block() {
  "$PY" - <<'AGENTSEOF'
import os
path, start, end = "AGENTS.md", "<!-- dca-factory: start -->", "<!-- dca-factory: end -->"
block = start + """
## Delivery pipeline

This project delivers stories through the dca-factory pipeline. At the start of a session, unless the
person names a task right away, run `python3 .agents/factory/story-gate.py --status --brief`, show
its lines, and ask what they want to do: write or release a story (`/factory-backlog`), answer a
waiting question (`/factory-decisions`), work the backlog (`/factory-run`, or `/loop /factory-run` to
keep listening), or look closer (`/factory-status`). A session never runs `factory.sh run` or
`backlog` — they start a tool process per stage. One worker per checkout: a managing session writes
backlog and decision files only.
""" + end
text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
if start in text and end in text:
    head, rest = text.split(start, 1)
    text = head + block + rest.split(end, 1)[1]
else:
    text = (text.rstrip() + "\n\n" if text.strip() else "") + block + "\n"
with open(path, "w", encoding="utf-8") as handle:
    handle.write(text)
print("factory: AGENTS.md carries the pipeline's section (between its dca-factory markers)")
AGENTSEOF
  if [ -f CLAUDE.md ] && ! grep -q "AGENTS.md" CLAUDE.md; then
    echo "factory: CLAUDE.md does not import AGENTS.md — Claude Code gets the section through the" >&2
    echo "factory:   SessionStart hook; add '@AGENTS.md' to CLAUDE.md if it should read the rest too." >&2
  fi
}

write_claude_permissions() {
  # Claude Code asks before running a command. In a non-interactive run there is nobody to ask,
  # so the gate cannot run and no stage can be verified — the tool then stops, correctly. These
  # two entries are the smallest allowlist that lets the pipeline verify itself; every other
  # command still asks.
  "$PY" - "$PY" <<'PYEOF'
import json, os, sys
python = sys.argv[1]
path = ".claude/settings.json"
os.makedirs(".claude", exist_ok=True)
settings = {}
if os.path.isfile(path):
    with open(path) as handle:
        settings = json.load(handle)
allow = settings.setdefault("permissions", {}).setdefault("allow", [])
wanted = [f"Bash({python} .agents/factory/story-gate.py:*)"]
profile = ".agents/factory/factory.profile.yaml"
if os.path.isfile(profile):
    for line in open(profile):
        if line.startswith(("compile:", "test:", "e2eTest:", "architecture:", "format:")):
            command = line.split(":", 1)[1].strip().strip("\"'")
            head = command.split()[0] if command else ""
            if head and not head.startswith("{{"):
                wanted.append(f"Bash({head}:*)")
# the reading commands, so a session looks without being asked; `run` and `backlog` are not in it —
# they start a tool process per stage, and the runner refuses them inside a session anyway
for verb in ("status", "usage", "decisions", "schedule"):
    wanted.append(f"Bash(bash .agents/factory/factory.sh {verb}:*)")
added = [entry for entry in dict.fromkeys(wanted) if entry not in allow]
allow.extend(added)
# The session starts knowing where the pipeline stands: the hook's output lands in its context. It
# calls the gate, which only reads — `factory.sh` is the person's, and no hook or skill runs it.
hook_command = f"{python} .agents/factory/story-gate.py --status --brief --session-start"
starts = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
for entry in starts:                         # an earlier install's hook through factory.sh is replaced
    entry["hooks"] = [h for h in entry.get("hooks", []) if "factory.sh status --brief" not in h.get("command", "")]
starts[:] = [entry for entry in starts if entry.get("hooks")]
if not any(h.get("command") == hook_command for entry in starts for h in entry.get("hooks", [])):
    starts.append({"hooks": [{"type": "command", "command": hook_command}]})
    added.append("a SessionStart hook with the pipeline's status")
with open(path, "w") as handle:
    json.dump(settings, handle, indent=2)
    handle.write("\n")
print("factory: .claude/settings.json allows " + ", ".join(added) if added else
      "factory: .claude/settings.json already allowed the gate")
PYEOF
}

# --- run ---------------------------------------------------------------------

# The judge's verdict decides what comes next, and the script must read it from the file rather
# than assume the run continues: `changes-requested` goes back to the build stage (one round),
# `story-conflict` stops the run — the story or the plan is wrong, and no build round fixes that.
verdict_of() {                              # verdict_of <story>
  local file="$TASKS/$1/judge.md"
  [ -f "$file" ] || { echo ""; return; }
  sed -n 's/^verdict:[[:space:]]*//p' "$file" | head -1 | tr -d '`" '"'"''
}

# Whether a stage file stops the run: a `## needs-human` section with something in it. A bare
# heading — empty, or `(none)` copied from the file template — asks nobody anything.
asks_human() {                              # asks_human <file>
  sed -n '/^## needs-human/,/^## /p' "$1" | sed '1d; /^## /d' \
    | grep -v -i -E '^[[:space:]]*(\(?(none|n/a|nothing)\)?|—|–|-)?[[:space:]]*$' | grep -q .
}

bump_rounds() {                             # bump_rounds <story> -> current count
  local file="$TASKS/$1/.rounds" count=0
  [ -f "$file" ] && count=$(tr -dc '0-9' < "$file")
  count=$(( ${count:-0} + 1 ))
  printf '%s\n' "$count" > "$file"
  echo "$count"
}

prompt_for() {                              # prompt_for <stage> <story>
  local stage=$1 story=$2 repeat=""
  # A repeat round that cannot see why the gate refused works blind, and every stage skill says to
  # work only on what the gate confirmed. So the refusal is named as an input, not remembered.
  [ -f "$TASKS/$story/.gate-$stage.txt" ] && repeat=" The gate refused this stage before; its \
report is $TASKS/$story/.gate-$stage.txt — read it and fix exactly what it names, nothing else."
  [ "$stage" = judge ] && [ -f "$TASKS/$story/.judge-previous.md" ] && repeat=" This is a repeat round: \
the previous verdict is $TASKS/$story/.judge-previous.md. Account for each defect it confirmed under \
'## Previous round' — fixed (with the evidence) or withdrawn (with the reason) — before judging anew."
  printf '%s' "Apply the stage-$stage skill for backlog story $story. \
Read only the story and the files the skill names as its input, and write its output file under \
$TASKS/$story/. Do the stage yourself in this session; do not delegate it. Do not run other stages.$repeat"
}

gate() {                                    # gate <stage> <story>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh install'" >&2; return 2; }
  local report="$TASKS/$2/.gate-$1.txt" journal="$TASKS/$2/.verify"
  mkdir -p "$TASKS/$2" "$journal"
  "$PY" "$GATE" --story "$2" --stage "$1" 2>&1 | tee "$report"
  local code=${PIPESTATUS[0]}
  # Every gate run is kept for the observer, with its verdict; only a *refusal* is kept where the
  # next stage reads it. A run that has to be reconstructed afterwards from what a stage claimed is
  # exactly the evidence the gate exists to replace.
  cp "$report" "$journal/gate-$1.$(date -u +%H%M%S).txt"
  printf '%s\tgate\t%s\texit=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$code" >> "$journal/journal.tsv"
  [ "$code" = 0 ] && rm -f "$report"
  return "$code"
}

# Which SHA-256 command this machine has, resolved once. `shasum` is the BSD and macOS spelling and
# arrives with perl; `sha256sum` is the coreutils one and all a slim Linux image has; `openssl` is
# the fallback where neither is installed. FACTORY_SHA256 overrides the choice — `none` forces the
# names-only path, which is how that path is exercised by a test rather than by a wrong machine.
HASHER=""
hasher() {
  [ -n "$HASHER" ] && { printf '%s' "$HASHER"; return; }
  if [ -n "${FACTORY_SHA256:-}" ]; then HASHER="$FACTORY_SHA256"
  elif command -v shasum >/dev/null 2>&1; then HASHER="shasum -a 256"
  elif command -v sha256sum >/dev/null 2>&1; then HASHER="sha256sum"
  elif command -v openssl >/dev/null 2>&1; then HASHER="openssl dgst -sha256 -r"
  else HASHER="none"; fi
  printf '%s' "$HASHER"
}

#: The first line of a snapshot written without a hash command. The observer reads it and treats
#: the snapshot as absent — see below for why that is the only honest reading.
NO_HASHES="# no-sha256-command: names only, no content hashes"

# What the working tree looks like right now, so a later stage's claim about what it changed can be
# checked rather than believed. Cheap: one porcelain listing plus a hash per file git reports.
snapshot() {                                # snapshot <story> <label>
  local journal="$TASKS/$1/.verify" file hash
  mkdir -p "$journal"
  hash=$(hasher)
  if [ "$hash" = none ]; then
    # Named, and named loudly. A snapshot of empty digests compares equal to every other one, so
    # the observer would read "this stage changed nothing" off a missing tool — the strongest claim
    # in its report, from the least evidence. So the snapshot says it carries no content, and the
    # run says which command it looked for.
    echo "factory: no sha256 command found (shasum, sha256sum, openssl) — the tree snapshots" >&2
    echo "factory:   record file names without content, and factory-verify reports every check" >&2
    echo "factory:   that needs a digest as not observed. Install one of the three for full evidence." >&2
  fi
  {
    [ "$hash" = none ] && echo "$NO_HASHES"
    # -uall: without it a newly added directory is listed as one entry and every file in it is
    # missing from the snapshot — so a test added by this run, and edited afterwards, would look
    # untouched. `--porcelain` also quotes unusual names, hence the -z form and the NUL split.
    git -c core.fileMode=false status --porcelain -z -uall 2>/dev/null \
      | tr '\0' '\n' | sed 's/^...//' | while read -r file; do
      { [ -n "$file" ] && [ -f "$file" ]; } || continue
      if [ "$hash" = none ]; then
        printf '%s  %s\n' "-" "$file"
      else
        printf '%s  %s\n' "$($hash "$file" 2>/dev/null | cut -d" " -f1)" "$file"
      fi
    done
  } > "$journal/tree-$2.txt" 2>/dev/null || true
}

# A record under $DECISIONS that names this story and carries no '## Answer' yet. The gate does the
# fine reading (a draft without a name is still open); this is the cheap check that keeps a run from
# starting a stage while the story waits for a human.
open_decisions() {                          # open_decisions <story>
  local file
  [ -d "$DECISIONS" ] || return 0
  for file in "$DECISIONS"/*.md; do
    [ -f "$file" ] || continue
    grep -q "^story:[[:space:]]*$1[[:space:]]*$" "$file" || continue
    grep -q '^## Answer' "$file" || echo "$file"
  done
}

run_story() {
  local story=$1 tool=$2 from=${3:-plan} dry=${4:-}
  local started=0 ran="" waiting
  waiting=$(open_decisions "$story")
  if [ -n "$waiting" ]; then
    echo "factory: story $story waits for a decision — no stage runs until it is answered:" >&2
    printf 'factory:   %s\n' $waiting >&2
    echo "factory:   answer under '## Answer' with answer:, by: and at:, then run the stage that asked (--from <stage>)." >&2
    return 3
  fi
  for stage in "${STAGES[@]}"; do
    [ "$stage" = "$from" ] && started=1
    [ "$started" = 1 ] || continue

    if [[ " ${PRE_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      gate "$stage" "$story" || { echo "factory: gate '$stage' refused the story. Fix it before the stage runs." >&2; return 1; }
    fi

    # A resumed story whose document file exists and was never refused: its gate decides first, and a
    # file that already holds costs no invocation.
    if [ "$stage" = document ] && [ -z "$dry" ] && [ -f "$TASKS/$story/document.md" ] \
       && [ ! -f "$TASKS/$story/.gate-document.txt" ] && [ ! -f "$TASKS/$story/.delivered" ]; then
      echo "── gate document  (the file exists — checked before the stage is invoked)"
      if gate document "$story" >/dev/null 2>&1; then
        echo "factory: $TASKS/$story/document.md already holds — the document stage is not invoked again."
        ran="${ran:+$ran,}document"
        break
      fi
    fi
    echo "── stage $stage  (tool: $tool, fresh context)"
    if [ -n "$dry" ]; then
      echo "   would run: $(prompt_for "$stage" "$story")"
      echo "   tool flags: $(isolation_flags "$tool")${FACTORY_ISOLATION:+(FACTORY_ISOLATION=$FACTORY_ISOLATION)}"
    elif [ -f "$GATE" ] && ! "$PY" "$GATE" --claim "$WORKER" >/dev/null; then
      echo "factory: the checkout was taken over by another worker before stage '$stage' — stopping." >&2
      return 5
    elif [ -n "$STORY_BUDGET" ] && [ "$("$PY" "$GATE" --usage --story "$story" --total 2>/dev/null || echo 0)" -ge "$STORY_BUDGET" ]; then
      # Checked before the invocation, from the journal: a restart, a second session or a new run
      # continues the same count. The last stage may overshoot — usage is known only after it ran.
      echo "factory: story $story has used $("$PY" "$GATE" --usage --story "$story" --total) tokens of its" >&2
      echo "factory:   --story-budget $STORY_BUDGET — stage '$stage' is not dispatched; the work so far stays." >&2
      return 4
    elif [ -n "$MAX_STAGES" ] && [ "$INVOCATIONS" -ge "$MAX_STAGES" ]; then
      # Checked before the invocation, never after: the cap is what may still be spent. Nothing is
      # undone — the stages so far keep their files, and the schedule resumes the story from them.
      echo "factory: --max-stages $MAX_STAGES reached before stage '$stage' of $story — nothing more is" >&2
      echo "factory:   dispatched; the work so far stays as it is and the next run continues from it." >&2
      return 4
    else
      # Never `started` — that name is the loop's "have we reached --from yet" flag, and
      # overwriting it skips every later stage while the run still reports success.
      local stage_started; stage_started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      # The previous verdict is an input to the next one, not something to overwrite: a defect a judge
      # confirmed may not vanish in the next round without a word.
      [ "$stage" = judge ] && [ -f "$TASKS/$story/judge.md" ] && mv "$TASKS/$story/judge.md" "$TASKS/$story/.judge-previous.md"
      snapshot "$story" "before-$stage"
      printf '%s\tstage-start\t%s\ttool=%s\n' "$stage_started" "$stage" "$tool" >> "$TASKS/$story/.verify/journal.tsv"
      local raw_out; raw_out="$TASKS/$story/.verify/$stage.$(date -u +%H%M%S).out"
      local invoked=0
      local began; began=$(date +%s)
      invocation_raw="$raw_out" stage_in_flight="$stage" story_in_flight="$story" \
        invoke "$tool" "$(prompt_for "$stage" "$story")" || invoked=$?
      record_usage "$story" "$stage" "$tool" "$raw_out" "$(( $(date +%s) - began ))"
      [ "$invoked" = 0 ] || {
        printf '%s\tstage-end\t%s\texit=nonzero\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" \
          >> "$TASKS/$story/.verify/journal.tsv"
        echo "factory: the tool exited non-zero during stage '$stage'." >&2; return 1; }
      printf '%s\tstage-end\t%s\texit=0\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$stage" \
        >> "$TASKS/$story/.verify/journal.tsv"
      snapshot "$story" "after-$stage"
      local artefact="$TASKS/$story/$(stage_file "$stage")"
      [ -f "$artefact" ] || {
        echo "factory: stage '$stage' produced no $artefact — a stage is finished when its file exists." >&2
        return 1; }
      # A stage that ends with a needs-human section has stopped, whatever its file otherwise says.
      # Reading only "does the file exist" turns an escalation into a hand-over, and the next stage
      # then builds on a decision nobody took.
      if asks_human "$artefact"; then
        echo "factory: stage '$stage' ends with a needs-human section — the run stops here." >&2
        # The question is a record of its own, so the answer has a place to land and a second
        # session finds it without this transcript. Name the file, and the command that resumes.
        local ids id
        ids=$(sed -n '/^## needs-human/,/^## /p' "$artefact" | sed -n 's/^[[:space:]-]*decision:[[:space:]]*//p')
        if [ -z "$ids" ]; then
          echo "factory:   the section names no 'decision: <id>' — the stage has to write the question as" >&2
          echo "factory:   $DECISIONS/<story>-<nn>.md; the next gate refuses a question nobody was asked." >&2
        fi
        for id in $ids; do
          if [ -f "$DECISIONS/$id.md" ]; then
            # The record names the stage that applies the answer — for a judge's story conflict that is
            # not the judge. That is where the story resumes.
            local applies; applies=$(sed -n 's/^stage:[[:space:]]*//p' "$DECISIONS/$id.md" | head -1)
            echo "factory:   decision $id → $DECISIONS/$id.md — answer it there under '## Answer'" >&2
            echo "factory:   with answer:, by: and at:, then: factory.sh run --story $story --from ${applies:-$stage}" >&2
          else
            echo "factory:   decision $id is named but $DECISIONS/$id.md does not exist." >&2
          fi
        done
        echo "factory:   read $artefact and decide; the stages after it were not run." >&2
        # 3 only when the question is a record: that is what a backlog run can wait on. A section
        # without one is a stop a human has to look at, like any other failure.
        [ -n "$ids" ] && return 3
        return 1
      fi
    fi

    if [[ " ${POST_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      if [ -z "$dry" ] && ! gate "$stage" "$story"; then
        # The same way back a judge's `changes-requested` takes: the stage runs again with the gate's
        # report as its input, one round counted, and three rounds stop the story.
        local refused_rounds; refused_rounds=$(bump_rounds "$story")
        if [ "$refused_rounds" -ge 3 ]; then
          echo "factory: gate '$stage' refused in round $refused_rounds — three rounds did not converge. needs-human." >&2
          return 1
        fi
        echo "factory: gate '$stage' refused — round $refused_rounds runs stage '$stage' again with the gate's report." >&2
        run_story "$story" "$tool" "$stage" "$dry"
        return $?
      fi
    fi

    ran="${ran:+$ran,}$stage"

    if [ "$stage" = "judge" ] && [ -z "$dry" ]; then
      local verdict rounds
      verdict=$(verdict_of "$story")
      case "$verdict" in
        pass) echo "factory: judge verdict 'pass'." ;;
        changes-requested)
          rounds=$(bump_rounds "$story")
          if [ "$rounds" -ge 3 ]; then
            echo "factory: judge verdict 'changes-requested' in round $rounds — three rounds did not converge. needs-human." >&2
            return 1
          fi
          echo "factory: judge verdict 'changes-requested' — round $rounds goes back to the build stage." >&2
          run_story "$story" "$tool" build "$dry"
          return $?
          ;;
        story-conflict)
          echo "factory: judge verdict 'story-conflict' — the story or the plan is wrong. This never goes back to the build stage. needs-human: read $TASKS/$story/judge.md." >&2
          return 1
          ;;
        "")
          echo "factory: $TASKS/$story/judge.md carries no 'verdict:' line — the judge stage is not finished." >&2
          return 1
          ;;
        *)
          echo "factory: judge verdict '$verdict' is not one of pass|changes-requested|story-conflict." >&2
          return 1
          ;;
      esac
    fi
  done
  # What ran, not what the script knows how to run: a message that names six stages after one of
  # them is exactly the self-report the gates exist to replace.
  echo "factory: story $story ran through ${ran:-nothing}."
}

# Story after story, in the order the schedule names. The schedule is read off the files every
# time, so nothing here remembers what ran: a story that stopped for a decision is simply not named
# again until its record is answered, and then it is named with the stage that asked. A failure
# ends the loop — retrying a broken stage spends a run on the same refusal.
run_backlog() {                             # run_backlog <tool> <watch> <interval> <dry>
  local tool=$1 watch=$2 interval=$3 dry=$4
  local out previous="" next story from last="" code
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh install'" >&2; return 2; }
  while :; do
    # waiting is working too: the claim is renewed on every look, so a watch that waits for an answer
    # for hours is not mistaken for a crashed one
    [ -n "$dry" ] || "$PY" "$GATE" --claim "$WORKER" >/dev/null || {
      echo "factory: another worker took over this checkout — the backlog run ends here." >&2; return 5; }
    if [ -f "$STOP_FILE" ]; then
      echo "factory: $STOP_FILE exists — the backlog run stops here. Remove it to run again."
      return 0
    fi
    out=$("$PY" "$GATE" --schedule 2>&1) || {
      printf '%s\n' "$out" >&2; echo "factory: the schedule could not be read." >&2; return 1; }
    next=$(printf '%s\n' "$out" | sed -n 's/^next: //p')
    case "$next" in
      none*|"") ;;
      *)
        story=${next%% *}; from=${next#* }
        if [ "$next" = "$last" ]; then
          printf '%s\n' "$out"
          echo "factory: $story ran from $from and the schedule names it there again — no progress, stopping." >&2
          return 1
        fi
        echo "══ story $story from $from"
        if [ -n "$dry" ]; then
          printf '%s\n' "$out"
          echo "   would run: factory.sh run --story $story --from $from"
          return 0
        fi
        run_story "$story" "$tool" "$from" ""
        code=$?
        case "$code" in
          0) last=$next; continue ;;
          3) last=""; continue ;;              # waits for a decision; the schedule skips it now
          *) echo "factory: story $story stopped (exit $code) — the backlog run ends here." >&2
             return "$code" ;;
        esac
        ;;
    esac
    if [ -z "$watch" ] || ! printf '%s\n' "$out" | grep -q '^wait: yes'; then
      printf '%s\n' "$out"
      echo "factory: nothing more can run$([ -n "$watch" ] && echo ", and nothing waits on an answer that would change that")."
      return 0
    fi
    # Waiting is reading files, never asking an agent: an unchanged schedule costs one gate call.
    if [ "$out" != "$previous" ]; then
      printf '%s\n' "$out"
      echo "factory: waiting for an answer — the schedule is read again every ${interval}s; $STOP_FILE ends the watch."
      previous=$out
    fi
    last=""
    sleep "$interval"
  done
}

# --- main --------------------------------------------------------------------

[ $# -ge 1 ] || usage
command=$1; shift
story=""; tool=""; from="plan"; dry=""; source_dir=""; copy_mode=""; watch=""; interval=60

# The reading commands are the gate's; the runner passes them on, so a project calls one script.
read_command() {                            # read_command <gate flags…>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh install' from the plugin" >&2; exit 2; }
  exec "$PY" "$GATE" "$@"
}
case "$command" in
  status)    case "${1:-}" in
               --brief) shift; [ -f "$GATE" ] || exit 0; read_command --status --brief "$@" ;;
               "") check_gate_freshness; read_command --status ;;
               --story) [ $# -eq 2 ] || usage; check_gate_freshness; read_command --status --story "$2" ;;
               -*) usage ;;
               *) [ $# -eq 1 ] || usage; check_gate_freshness; read_command --status --story "$1" ;;
             esac ;;
  schedule)  [ $# -eq 0 ] || usage; read_command --schedule ;;
  usage)     read_command --usage "$@" ;;
  decisions) read_command --list-decisions "$@" ;;
  change)    read_command --change "$@" ;;
  parity)    [ $# -eq 1 ] || usage; read_command --parity "$1" ;;
esac

while [ $# -gt 0 ]; do
  case "$1" in
    --story) story=$2; shift 2 ;;
    --tool) tool=$2; shift 2 ;;
    --from) case "$command" in install|update) source_dir=$2 ;; *) from=$2 ;; esac; shift 2 ;;
    --copy) copy_mode=1; shift ;;
    --dry-run) dry=1; shift ;;
    --watch) watch=1; shift ;;
    --interval) interval=$2; shift 2 ;;
    --max-stages) MAX_STAGES=$2; shift 2 ;;
    --story-budget) STORY_BUDGET=$2; shift 2 ;;
    *) usage ;;
  esac
done

case "$command" in
  install) install_skills "${tool:-all}" "$source_dir" "$copy_mode" ;;
  update)  update_project "$source_dir" ;;
  run)
    [ -n "$story" ] || usage
    [ -n "$tool" ] || tool=$(detect_tool)
    [ -n "$tool" ] || { echo "factory: no agent tool found on PATH." >&2; exit 2; }
    check_gate_freshness                    # once per invocation; run_story recurses on a verdict
    [ -n "$dry" ] || refuse_nested || exit $?
    check_carriers "$tool" || exit $?
    check_local_context "$tool"
    isolated || echo "factory: FACTORY_ISOLATION=off — stages run with the tool's full setup, user plugins included" >&2
    [ -n "$dry" ] || take_checkout || exit $?
    run_story "$story" "$tool" "$from" "$dry"
    ;;
  backlog)
    [ -n "$tool" ] || tool=$(detect_tool)
    [ -n "$tool" ] || [ -n "${FACTORY_TOOL_CMD:-}" ] || { echo "factory: no agent tool found on PATH." >&2; exit 2; }
    case "$interval" in ''|*[!0-9]*) echo "factory: --interval takes whole seconds" >&2; exit 2 ;; esac
    case "$MAX_STAGES" in *[!0-9]*) echo "factory: --max-stages takes a number" >&2; exit 2 ;; esac
    case "$STORY_BUDGET" in *[!0-9]*) echo "factory: --story-budget takes a number of tokens" >&2; exit 2 ;; esac
    # Bounded both ways: below a second the watch is a busy loop, above an hour an answer waits
    # longer than anyone expects to.
    [ "$interval" -lt 1 ] && interval=1
    [ "$interval" -gt 3600 ] && interval=3600
    check_gate_freshness
    [ -n "$dry" ] || refuse_nested || exit $?
    check_carriers "${tool:-}" || exit $?
    check_local_context "${tool:-}"
    isolated || echo "factory: FACTORY_ISOLATION=off — stages run with the tool's full setup, user plugins included" >&2
    [ -n "$dry" ] || take_checkout || exit $?
    run_backlog "${tool:-stand-in}" "$watch" "$interval" "$dry"
    ;;
  *) usage ;;
esac
