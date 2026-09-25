#!/usr/bin/env bash
# The factory outside the session: one process per stage, so every stage starts with a fresh
# context and reads only its story and its predecessor's file. Same stages, same gate, same
# files as running the skills inside a session — this only changes who holds the context.
#
#   factory.sh setup [--tool claude|codex|opencode|all|none] [--copy] [--from <skill folder>]
#                    installs the pipeline where it is not; on an installed project it reports only
#   factory.sh setup --check                 what detection finds against the profile (read-only)
#   factory.sh setup --write [--replace <key>]   adds the detected keys the profile lacks
#   factory.sh backlog [--check]             every story's state and the next one; --check the backlog
#   factory.sh run [--story <id>] [--tool <tool>] [--from <stage>] [--watch] [--interval <s>]
#                  [--max-stages <n>] [--story-budget <tokens>] [--shared-builder] [--dry-run]
#                    one story, or without --story the whole backlog in the schedule's order
#   factory.sh status [--story <id>] [--usage] [--brief]   what runs, what waits, every story, the cost
#   factory.sh decisions [--story <id>]      the decision inbox
#   factory.sh help [--format text|md|json]  the factory explained: the flow and where this project stands,
#                                            every command in its agent and its shell form, the marks, the files
#   factory.sh update [--from <skill folder>]   the newest pipeline found, same tools, links or copies
#   factory.sh verify --story <id> | --fixtures   observe a delivered story | check the machinery
#   factory.sh check [--staged] [--checks "<c> …"] | --parity <config>   for the commit hook and CI
#
# `run` exits 0 when the story ran through, 3 when it stopped for a decision, 4 at --max-stages,
# 5 when another worker holds the checkout, 6 when started inside an agent session with a real
# tool (FACTORY_ALLOW_NESTED=1 overrides), anything else on a failure. Without --story it runs story
# after story in the order `backlog` names, past stories that wait for a decision; --watch keeps it
# waiting for answers.
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
SHARED_BUILDER="${FACTORY_SHARED_BUILDER:-}"  # --shared-builder: plan to tidy in one process (off by default)
case "$(printf '%s' "$SHARED_BUILDER" | tr '[:upper:]' '[:lower:]')" in 0|off|no|false) SHARED_BUILDER="" ;; esac
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
  # Without these, a TERM or HUP ends the runner at once — its EXIT trap gives the claim back while
  # the stage's tool process runs on, and a second worker starts beside it. With a trap set, bash
  # runs it once the foreground stage has ended, so the claim is released only after that.
  trap 'echo "factory: stopped by a signal — after the running stage, nothing more starts" >&2; exit 143' TERM
  trap 'echo "factory: stopped by a hang-up — after the running stage, nothing more starts" >&2; exit 129' HUP
}

# Which Python runs the gate. `python3` is the POSIX spelling; on Windows the interpreter is
# `python` or `py`, and `python3` is often the WindowsApps alias that opens a shop window instead of
# running — found on PATH all the same. So each name is asked to run, not only looked up.
# FACTORY_PYTHON overrides, for a project that pins one. Resolved once, and the *name* is what
# reaches the profile and the permission list, so both stay portable between machines.
PY="${FACTORY_PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in python3 python py; do
    "$candidate" -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1 && { PY=$candidate; break; }
  done
  PY=${PY:-python3}                            # named in the error the first call then produces
fi
# Every Python this runner starts writes UTF-8 — the gate's and the setup's lines carry `—` and `→`,
# and a Windows console's code page (cp1252) cannot encode them: the print raises and the step dies.
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

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

usage() { sed -n '2,/^# FACTORY_TOOL_CMD/p' "$0" | sed '$d' >&2; exit 2; }

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
  local candidate dir best="" best_version="" version
  for candidate in \
      "${FACTORY_PLUGIN_DIR:-}" \
      "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)" \
      .claude/skills .codex/skills .opencode/skills \
      "$HOME"/.claude/plugins/cache/*/dca-factory/*/skills; do
    [ -n "$candidate" ] && [ -f "$candidate/factory-run/scripts/story-gate.py" ] || continue
    dir=$(cd "$candidate" && pwd -P)
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
  if [ ! -d "$target/factory-run" ]; then
    # Links are machine-local and kept out of git, so a fresh clone has none — the ignore rule is what
    # says the project used them, and `update` is how a clone gets them back.
    git check-ignore -q "$target/factory-run" 2>/dev/null && echo link || echo ""
    return
  fi
  [ -L "$target/factory-run" ] && echo link || echo copy
}

# Bring the project up to the newest pipeline found, for exactly the tools it already has, keeping
# links as links and copies as copies. The profile is the project's and is never rewritten; a file
# contract that moved is said out loud, with the profile line to raise. The replacing is the *newest*
# runner's, not this copy's: a release that adds a file the project needs must be able to put it
# there, even when the project's runner predates it — so a project's copy hands over to it (`exec`).
update_project() {                          # update_project <explicit skill folder or "">
  local src=${1:-} before before_contract after after_contract tool target mode declared updated=0
  [ -n "$src" ] || src=$(plugin_skills) || {
    echo "factory: no pipeline found to update from — pass --from <the plugin's skills folder>" >&2; return 2; }
  [ -f "$src/factory-run/scripts/story-gate.py" ] || {
    echo "factory: $src is not the pipeline's skills folder (no factory-run/scripts/story-gate.py)" >&2; return 2; }
  src=$(cd "$src" && pwd -P)
  local newest="$src/factory-run/scripts/factory.sh" self
  self=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/$(basename "${BASH_SOURCE[0]}")
  if [ -z "${FACTORY_UPDATE_HANDED:-}" ] && [ -f "$newest" ] && [ "$self" != "$newest" ]; then
    FACTORY_UPDATE_HANDED=1 exec bash "$newest" update --from "$src"
  fi
  before=$(sed -n 's/^version:[[:space:]]*//p' "$STAMP" 2>/dev/null | head -1)
  before_contract=$(sed -n 's/^contract:[[:space:]]*//p' "$STAMP" 2>/dev/null | head -1)
  for tool in claude codex opencode; do
    target=".$tool/skills"
    mode=$(skills_mode "$target")
    [ -n "$mode" ] || continue
    if [ "$mode" = copy ]; then
      install_project "$tool" "$src" 1
    else
      install_project "$tool" "$src" ""
    fi
    updated=1
  done
  [ "$updated" = 1 ] || install_project none "$src" ""
  prune_renamed_copies "$src"
  local renames; renames=$(profile_renames)
  if [ -n "$renames" ]; then
    echo "factory: the profile names skills by their old names — the update writes nothing into it; change:" >&2
    printf 'factory:   %s\n' "$renames" >&2
  fi
  after=$(gate_field "$GATE" VERSION); after_contract=$(gate_field "$GATE" CONTRACT)
  echo "factory: updated ${before:-an unstamped install} → $after (file contract ${before_contract:-?} → $after_contract) from $src"
  declared=$(sed -n 's/^contract:[[:space:]]*//p' "$PROFILE" 2>/dev/null | head -1)
  if [ -n "$declared" ] && [ "$declared" != "$after_contract" ]; then
    echo "factory: the stack profile declares contract $declared — raise it to 'contract: $after_contract' once" >&2
    echo "factory:   the profile uses what that contract describes; the gate reads it as older until then." >&2
  fi
  # the layout before `project/` is not read by the new gate; the move is said here as well
  "$PY" "$GATE" --schedule 2>/dev/null | sed -n 's/^layout: /factory: /p' >&2
  echo "factory: review and commit the changed files — the update commits nothing. 'factory.sh setup --check'"
  echo "factory:   names what the project gained since, as profile lines to confirm; the update writes none."
}

# A copied skill under a name the method plugins renamed: removed when it is byte for byte the newest
# version of its old plugin still on this machine (the plugin cache, or a checkout beside the pipeline)
# — nobody edited it — and kept and named otherwise, because then the project made it its own.
prune_renamed_copies() {                    # prune_renamed_copies <pipeline skill folder>
  local src=$1 target old new plugin copy candidate reference version best_version
  for target in .claude/skills .codex/skills .opencode/skills; do
    [ -d "$target" ] && [ ! -L "$target" ] || continue
    while read -r old new plugin; do
      copy="$target/$old"
      [ -d "$copy" ] && [ ! -L "$copy" ] || continue
      reference=""; best_version=""
      for candidate in "$HOME"/.claude/plugins/cache/*/"$plugin"/*/skills/"$old" "$src/../../$plugin/skills/$old"; do
        [ -d "$candidate" ] || continue
        version=$(basename "$(dirname "$(dirname "$candidate")")")
        if [ -z "$reference" ] || [ "$(printf '%s\n%s\n' "$best_version" "$version" | sort -V | tail -1)" = "$version" ]; then
          reference=$candidate; best_version=$version
        fi
      done
      if [ -z "$reference" ]; then
        echo "factory: kept $copy — renamed to $new, and no $plugin copy of it is left to compare with" >&2
      elif diff -rq -x .dca-factory-skills "$copy" "$reference" >/dev/null 2>&1; then
        rm -rf "${copy:?}"
        [ -f "$target/.dca-factory-skills" ] && { grep -vx "$old" "$target/.dca-factory-skills" > "$target/.dca-factory-skills.new"; mv -f "$target/.dca-factory-skills.new" "$target/.dca-factory-skills"; }
        echo "factory: removed $copy — renamed to $new, and the copy was $plugin's own, unedited"
      else
        echo "factory: kept $copy — renamed to $new, but the copy differs from $plugin's: the project edited it" >&2
      fi
    done <<< "$RENAMED_SKILLS"
  done
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
    echo "factory:   pipeline here implements $source_contract — run 'factory.sh update' and check" >&2
    echo "factory:   the stack profile's 'contract:' line before trusting a run." >&2
  elif [ "$installed_version" != "$source_version" ]; then
    echo "factory: this project was installed from pipeline $installed_version, the one here is" >&2
    echo "factory:   $source_version — same file contract, so the run is valid; 'factory.sh update'" >&2
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
    for key in compile test e2eTest architecture format formatFix; do
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
# Skills the method plugins renamed: <old> <new> <the plugin that shipped the old one>. A profile that
# still names an old one would run yesterday's copy without a word, so the run stops on it, and
# `update` removes a copy under the old name that nobody edited.
RENAMED_SKILLS="review-domain review-ddd dca-core
review-boundaries review-hexagonal dca-core
review-craft review-clean-code software-craftsmanship
ddd-modelling dca-modelling dca-core
dca-bootstrap dca-init dca-core
dca-scaffold dca-new dca-core"
RENAMED_KEYS="review.domain review.ddd
review.boundaries review.hexagonal
review.craft review.clean-code"
RETIRED_PLUGINS="software-craftsmanship"     # left in a plugin cache after a rename; never a source

renamed_skill() { printf '%s\n' "$RENAMED_SKILLS" | awk -v n="$1" '$1 == n {print $2}'; }

# The profile lines that name a renamed skill or key, as "<old line> → <new line>".
profile_renames() {
  local profile="${FACTORY_PROFILE:-.agents/factory/factory.profile.yaml}" key value new_key new_value
  [ -f "$profile" ] || profile=factory.profile.yaml
  [ -f "$profile" ] || return 0
  sed -n -E 's/^(carrier\.[a-z]+|review\.[a-z-]+|knowledge):[[:space:]]*/\1 /p' "$profile" | tr -d '"'"'"'"' \
    | while read -r key value _; do
      new_key=$(printf '%s\n' "$RENAMED_KEYS" | awk -v k="$key" '$1 == k {print $2}'); new_key=${new_key:-$key}
      new_value=$(renamed_skill "$value"); new_value=${new_value:-$value}
      [ "$key: $value" = "$new_key: $new_value" ] || echo "$key: $value → $new_key: $new_value"
    done
}

check_carriers() {                          # check_carriers <tool>
  local renames; renames=$(profile_renames)
  if [ -n "$renames" ]; then
    echo "factory: the profile names skills by names they no longer have — nothing was started:" >&2
    printf 'factory:   %s\n' "$renames" >&2
    echo "factory:   change those lines; a copy under the old name would run yesterday's skill. 'factory.sh" >&2
    echo "factory:   update' removes such a copy where the project did not edit it." >&2
    return 2
  fi
  [ -n "${FACTORY_TOOL_CMD:-}" ] && return 0
  isolated || return 0
  local dir missing="" name; dir=$(skill_dir_of "$1")
  [ -n "$dir" ] || return 0
  for name in $(named_carriers); do
    [ -f "$dir/$name/SKILL.md" ] || missing="$missing $name"
  done
  [ -z "$missing" ] && return 0
  echo "factory: the profile names carrier(s) the project does not hold in $dir:$missing" >&2
  echo "factory:   a stage process sees only the project — 'factory.sh update' links them there (a tool the" >&2
  echo "factory:   project has no skills for yet: 'factory.sh setup --tool $1'), or FACTORY_ISOLATION=off" >&2
  echo "factory:   uses the tool's own setup." >&2
  return 2
}

# The profile's contract and model keys, before any stage is paid for: a run started --from a later
# stage has no plan gate in front of it, and a stage run on the wrong model is spent money.
check_contract_first() {
  [ -f "$GATE" ] || return 0
  local out code=0
  out=$("$PY" "$GATE" --check-contract 2>&1) || code=$?
  [ "$code" = 0 ] && return 0
  if [ "$code" = 1 ]; then
    printf '%s\n' "$out" >&2
    echo "factory: the stack profile does not hold for this gate — nothing was started." >&2
    return 2
  fi
  return 0                                  # an older gate without the check: its stage gates still run
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

# The model a stage runs on is the project's choice, stated in the profile per tool and stage
# (`model.<tool>.<stage>`, falling back to `model.<tool>`); the pipeline itself names no model. A
# `--model`/`-m` the person puts in FACTORY_<TOOL>_ARGS wins — it is their local override, for
# example for a provider that does not work here — and the run says so. Exactly one model flag is
# ever passed: which of two a tool would honour is its behaviour, not something to rely on.
model_key() {                               # model_key <tool> <stage> — the profile's choice, or nothing
  local profile="${FACTORY_PROFILE:-.agents/factory/factory.profile.yaml}" value
  [ -f "$profile" ] || profile=factory.profile.yaml
  [ -f "$profile" ] || return 0
  value=$(sed -n "s/^model\.$1\.$2:[[:space:]]*//p" "$profile" | head -1 | tr -d '"'"'"'"' | awk '{print $1}')
  [ -n "$value" ] || value=$(sed -n "s/^model\.$1:[[:space:]]*//p" "$profile" | head -1 | tr -d '"'"'"'"' | awk '{print $1}')
  printf '%s' "$value"
}
tool_args() { case "$1" in claude) printf '%s' "${FACTORY_CLAUDE_ARGS:-}" ;; codex) printf '%s' "${FACTORY_CODEX_ARGS:-}" ;; opencode) printf '%s' "${FACTORY_OPENCODE_ARGS:-}" ;; esac; }
env_model() { tool_args "$1" | sed -n -E 's/.*(^| )(-m|--model)[ =]([^ ]*).*/\3/p' | head -1; }
# The model flag for one stage, and why a request does not become one: "<flag args>|<note>".
model_choice() {                            # model_choice <tool> <stage>
  local requested; requested=$(model_key "$1" "$2")
  [ -n "$requested" ] || { printf '|'; return; }
  if [ -n "${FACTORY_TOOL_CMD:-}" ]; then printf '|passed as FACTORY_MODEL to the custom command'; return; fi
  if [ -n "$(env_model "$1")" ]; then printf '|overridden by FACTORY_%s_ARGS (%s)' "$(printf '%s' "$1" | tr a-z A-Z)" "$(env_model "$1")"; return; fi
  case "$1" in
    claude) printf -- '--model %s|' "$requested" ;;
    codex|opencode) printf -- '-m %s|' "$requested" ;;
    *) printf '|no model flag for tool %s' "$1" ;;
  esac
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
  local choice model_args; choice=$(model_choice "$tool" "${stage_in_flight:-}"); model_args=${choice%%|*}
  if [ -n "${FACTORY_TOOL_CMD:-}" ]; then
    FACTORY_STAGE="${stage_in_flight:-}" FACTORY_STORY="${story_in_flight:-}" FACTORY_PROMPT="$prompt" \
      FACTORY_MODEL="$(model_key "$tool" "${stage_in_flight:-}")" sh -c "$FACTORY_TOOL_CMD" > "$raw"
    local code=$?
    [ "$raw" = /dev/null ] || { [ -n "${FACTORY_USAGE_FORMAT:-}" ] || cat "$raw"; }
    return $code
  fi
  case "$tool" in
    claude)   claude -p "$prompt" --permission-mode acceptEdits --output-format json \
                --allowed-tools "Read,Write,Edit,Glob,Grep,Skill,$(allowed_commands)" \
                $(isolation_flags claude) $model_args ${FACTORY_CLAUDE_ARGS:+$FACTORY_CLAUDE_ARGS} > "$raw" ;;
    # stdin closed: `codex exec` also reads a prompt from stdin, and an unattended run has none.
    codex)    codex exec --json -s workspace-write $(isolation_flags codex) $model_args \
                -c sandbox_workspace_write.network_access=true \
                ${FACTORY_CODEX_ARGS:+$FACTORY_CODEX_ARGS} "$prompt" < /dev/null > "$raw" ;;
    opencode) opencode run --format json $(isolation_flags opencode) $model_args \
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
model_flag() {                              # model_flag <tool> [stage]
  [ -n "${2:-}" ] && [ -n "$(model_key "$1" "$2")" ] && [ -z "$(env_model "$1")" ] && { model_key "$1" "$2"; return; }
  local args=""
  case "$1" in codex) args="${FACTORY_CODEX_ARGS:-}" ;; opencode) args="${FACTORY_OPENCODE_ARGS:-}" ;; esac
  # -E: BSD sed (macOS) has no `\|` in a basic expression, so the alternation is written extended
  printf '%s\n' "$args" | sed -n -E 's/.*(-m|--model)[ =]([^ ]*).*/\2/p' | head -1
}

# One `usage` line in the story's journal per invocation, and the stage's final message on screen.
record_usage() {                            # record_usage <story> <stage> <tool> <raw> [seconds]
  local out fields
  out=$("$PY" "$GATE" --usage-from "$(usage_format "$3")" "$4" --usage-model "$(model_flag "$3" "$2")" 2>/dev/null) \
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

# The skill folders of the plugins beside this one. In a checkout they are `plugins/<plugin>/skills`;
# in a plugin cache every plugin has a folder per version — `<plugin>/<version>/skills` — and there
# `../../*/skills` would be the *other versions of this pipeline*, so each neighbour's newest is taken.
method_skill_dirs() {
  local source_abs=$1 plugin plugins dir found="" newest
  plugin=$(cd "$source_abs/.." 2>/dev/null && pwd) || return 0
  if [ -f "$plugin/.claude-plugin/plugin.json" ] && [ "$(basename "$plugin")" != dca-factory ] \
     && [ "$(basename "$(dirname "$plugin")")" = dca-factory ]; then
    plugins=$(cd "$plugin/../.." && pwd)                            # the cache: <plugin>/<version>/
    for dir in "$plugins"/*; do
      [ -d "$dir" ] && [ "$(basename "$dir")" != dca-factory ] || continue
      case " $RETIRED_PLUGINS " in *" $(basename "$dir") "*) continue ;; esac
      newest=$(for version in "$dir"/*/skills; do [ -d "$version" ] && basename "$(dirname "$version")"; done \
        | sort -V | tail -1)
      [ -n "$newest" ] && found="$found $(cd "$dir/$newest/skills" && pwd)"
    done
    echo "$found"
    return 0
  fi
  plugins=$(cd "$source_abs/../.." 2>/dev/null && pwd) || return 0
  for dir in "$plugins"/*/skills; do
    [ -d "$dir" ] || continue
    [ "$(cd "$dir" && pwd)" = "$source_abs" ] && continue
    case " $RETIRED_PLUGINS " in *" $(basename "$(dirname "$dir")") "*) continue ;; esac
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
  local manifest="$target/.dca-factory-skills" ours_copy
  for name in $(named_carriers); do
    # A copy this install made (in its list) is refreshed; any other skill of that name is the project's.
    ours_copy=""
    [ -n "$copy_mode" ] && grep -qsx "$name" "$manifest" && ours_copy=1
    if [ -f "$target/$name/SKILL.md" ] && ! { [ -L "$target/$name" ] && ! [ -e "$target/$name" ]; } \
       && [ -z "$ours_copy" ]; then
      continue
    fi
    found=""
    for dir in $method_dirs; do [ -d "$dir/$name" ] && { found="$dir/$name"; break; }; done
    if [ -z "$found" ]; then
      if [ -n "$ours_copy" ] && [ -f "$target/$name/SKILL.md" ]; then
        echo "factory: kept the copied carrier $target/$name — no plugin beside the pipeline has a newer one" >&2
      else
        echo "factory: the profile names carrier '$name', which no plugin beside the pipeline provides — add it to $target" >&2
      fi
      continue
    fi
    if [ -n "$copy_mode" ]; then
      rm -rf "${target:?}/$name" && cp -R "$found" "$target/$name" \
        && { grep -qsx "$name" "$manifest" || echo "$name" >> "$manifest"; }
    else
      ln -sfn "$found" "$target/$name"
    fi
    echo "factory: carrier $name → $target"
  done
}

# The pipeline's files in the project, for the tools named: what a first `setup` installs and what
# `update` replaces. Internal — the verbs are `setup` and `update`.
install_project() {                         # install_project <tool> <skill folder> <copy_mode>
  local tool=${1:-all} from=${2:-} copy_mode=${3:-}
  if [ -z "$from" ]; then
    from="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # the skill folder, run from the plugin
    [ -f "$from/factory-run/scripts/story-gate.py" ] || from=$(plugin_skills) || {
      echo "factory: no pipeline found to install from — pass --from <the plugin's skills folder>" >&2; exit 2; }
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
  # The profile first: the carriers it names are linked by this same run, so the first `run` does not
  # stop in the carrier check, and the per-skill branch for Claude's directory below sees them.
  must "create .agents/factory and .githooks" mkdir -p .agents/factory .githooks
  [ -f "$PROFILE" ] || write_profile "$from"
  if [ -z "$copy_mode" ] && ! can_symlink; then
    copy_mode=1; copy_reason=" — this shell cannot make symlinks (Windows without developer mode or MSYS=winsymlinks:nativestrict), so the install copies"
  fi
  # `${targets[@]+…}`: an empty array under `set -u` is an unbound variable to bash 3.2 (macOS /bin/bash).
  for target in ${targets[@]+"${targets[@]}"}; do
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
      # The same set a link install gives this tool: for a tool without a plugin mechanism the craft
      # of the method plugins beside the pipeline, not only the carriers the profile already names.
      local copy_dirs="$source_abs"
      [ "$target" != ".claude/skills" ] && copy_dirs=$(printf '%s\n%s' "$source_abs" "$(method_skill_dirs "$source_abs" | tr ' ' '\n')")
      while IFS= read -r skill; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        grep -qx "$name" "$manifest.new" && continue         # the pipeline's own wins a name clash
        if { [ -e "$target/$name" ] || [ -L "$target/$name" ]; } && ! printf '%s\n' "$previous" | grep -qx "$name"; then
          echo "factory: kept the project's own $target/$name — the pipeline's $name was not copied" >&2
          kept=$((kept + 1))
          continue
        fi
        rm -rf "${target:?}/$name"
        must "copy $name into $target" cp -R "$skill" "$target/$name"
        echo "$name" >> "$manifest.new"
        copied=$((copied + 1))
      done < <(printf '%s\n' "$copy_dirs" | while IFS= read -r dir; do [ -n "$dir" ] && printf '%s\n' "$dir"/*; done)
      for name in $previous; do
        grep -qx "$name" "$manifest.new" && continue            # copied again just now
        # A carrier the profile names is not the pipeline's skill but one it copied beside it: it
        # stays, on the list, for install_named_carriers to refresh — never removed as outdated.
        if printf '%s\n' $(named_carriers) | grep -qx "$name" && [ -d "$target/$name" ]; then
          echo "$name" >> "$manifest.new"
          continue
        fi
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
        # A link that points nowhere is nobody's skill — typically one into a plugin folder that was
        # renamed. It is pruned and named, so the skill of that name can be linked afresh.
        if [ -L "$entry" ] && [ ! -e "$entry" ]; then
          echo "factory: pruned $entry — it pointed to $(readlink "$entry"), which no longer exists" >&2
          rm -f "$entry"; pruned=$((pruned + 1))
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
      echo "factory:   per skill, because they come from several sources — 'factory.sh update' after a skill is added" >&2
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
      echo "factory:   'factory.sh update' after a skill is added to the pipeline" >&2
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
      echo "factory:   'factory.sh update' after a skill is added to the source" >&2
    fi
  done
  for target in ${targets[@]+"${targets[@]}"}; do
    # The whole-directory link to the pipeline cannot take a carrier beside it: the carrier would be
    # written into the plugin's own folder. Then the tool finds the carrier through its plugins, and
    # an isolated stage does not — the runner's carrier check says so before a run.
    [ -L "$target" ] && continue
    if [ "$target" = ".claude/skills" ] || [ -n "$copy_mode" ]; then
      install_named_carriers "$target" "$source_abs" "$copy_mode"
    fi
  done
  check_dca_setup "$from"
  must "copy the gate to $GATE" cp "$from/factory-run/scripts/story-gate.py" "$GATE"
  # The observer beside it, for `factory.sh verify --story`: a delivered story is checked in the project.
  must "copy the observer to .agents/factory/observe.py" \
    cp "$from/factory-verify/scripts/observe.py" .agents/factory/observe.py
  # The runner goes beside the gate, so the project has one entry point for everything it does with
  # the pipeline: `bash .agents/factory/factory.sh setup|backlog|run|status|…`. An update is handed to
  # the newest pipeline's runner, which knows where the skills are.
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
  local hooks_path; hooks_path=$(git config --get core.hooksPath 2>/dev/null || true)
  if [ -n "$hooks_path" ] && [ "$hooks_path" != .githooks ]; then
    # Another hook manager (husky, lefthook, …) owns the hooks: overwriting its path would switch its
    # hooks off without a word. It calls ours instead.
    echo "factory: core.hooksPath is $hooks_path, not .githooks — left as it is. Call .githooks/pre-commit" >&2
    echo "factory:   from $hooks_path/pre-commit, or nothing checks a commit." >&2
  elif git config core.hooksPath .githooks 2>/dev/null; then
    echo "factory: git hooks → .githooks"
  else
    echo "factory: no git repository here — .githooks/pre-commit is installed but nothing runs it." >&2
  fi
  case "$tool" in
    claude|all) write_claude_permissions ;;
  esac
  # The journal is append-only, one line per event: two branches that ran the same story both add
  # lines at its end, which git reports as a conflict although keeping both is always right.
  if ! grep -qs "journal.tsv merge=union" .gitattributes; then
    [ -s .gitattributes ] && [ -n "$(tail -c 1 .gitattributes)" ] && printf '\n' >> .gitattributes
    printf '%s\n' "tasks/**/.verify/journal.tsv merge=union" >> .gitattributes
    echo "factory: .gitattributes merges the story journals by keeping both sides (merge=union)"
  fi
  write_agents_block
  if [ -n "$copy_mode" ]; then
    echo "factory: the skills are copies — commit .claude/.codex/.opencode skills with the project, and"
    echo "factory:   every clone delivers stories with this pipeline, without the marketplace."
  elif [ -n "${targets[*]+x}" ] && [ "${#targets[@]}" -gt 0 ]; then
    echo "factory: the skill links point into $source_abs — they belong in .gitignore; a clone"
    echo "factory:   gets them with 'factory.sh update', or use --copy to commit the skills with the project."
  fi
}

check_dca_setup() {                        # check_dca_setup <skill folder>
  # The factory delivers stories; it does not install an architecture. That is the method's
  # setup skill's job, and it runs once. Say so instead of quietly starting without one. What counts as
  # governance is the `governance` presets' — a rule package or an architecture test.
  local dir; dir=$(presets_dir "${1:-}") || dir=""
  if presets "$dir" detect | grep -q '^#governance'; then
    echo "factory: architecture governance found — the pipeline has something to gate on."
  else
    echo "factory: no architecture governance found in this project." >&2
    echo "factory: run the method's setup skill first (in a DCA project /dca-init) — it adds the building" >&2
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

# --- detection: the presets ----------------------------------------------------
# What a build tool looks like, and which commands it gets, is data: one flat `key: value` file per
# detection case in templates/presets/, applied at setup and compared by `setup --check`. This script
# knows no build tool. A preset is never read at run time — the profile is the only contract there.
PROFILE=".agents/factory/factory.profile.yaml"

presets_dir() {                             # presets_dir [<skill folder>] — where the presets are
  if [ -n "${FACTORY_STACKS_DIR:-}" ]; then echo "$FACTORY_STACKS_DIR"; return 0; fi
  local skills=${1:-} own
  own="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)"
  # the pipeline this script belongs to when it runs from the plugin; the newest one found otherwise
  [ -n "$skills" ] || { [ -d "$own/factory-run/templates/presets" ] && skills=$own; }
  [ -n "$skills" ] || skills=$(plugin_skills) || return 1
  [ -d "$skills/factory-run/templates/presets" ] && echo "$skills/factory-run/templates/presets"
}

# One program for every use of the presets, so detection, the first profile, the check and the write
# cannot disagree about what was found:
#   detect                         the detected keys, one `key<TAB>value` per line; `#governance` when found
#   new <template> <profile>       write a first profile from the template and what was detected
#   check <profile> [brief]        what detection proposes against the profile; exit 1 on a missing key
#   write <profile> [<key>]        add the missing keys; with <key>, take the detected value for that one
# The roles a method skill fills, and whether the role needs the architecture governance a preset
# detects. A line is written only where the skill is installed beside the pipeline — a named carrier
# that is missing stops a run — and stays commented out otherwise, so resolution by description applies.
CARRIERS="carrier.build dca-modelling governance
carrier.guard dca-discipline governance
review.dca dca-review governance
carrier.glossary ubiquitous-language -
carrier.domain context-map -
carrier.test e2e-testing -"

# The skill names of the method plugins beside the pipeline whose presets are in <dir>.
method_skill_names() {                      # method_skill_names <presets dir>
  local skills="" dir entry
  if [ -f "$1/../../scripts/story-gate.py" ]; then
    skills=$(cd "$1/../../.." && pwd)                 # the pipeline the presets belong to
  else
    skills=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)
    [ -f "$skills/factory-run/scripts/story-gate.py" ] || skills=$(plugin_skills) || return 0
  fi
  for dir in $(method_skill_dirs "$skills"); do
    for entry in "$dir"/*/SKILL.md; do [ -f "$entry" ] && basename "$(dirname "$entry")"; done
  done | sort -u | tr '\n' ' '
}

presets() {                                 # presets <dir> <mode> [args…]
  local dir=$1; shift
  FACTORY_SKILLS="$(method_skill_names "$dir")" FACTORY_CARRIERS="$CARRIERS" \
  "$PY" - "$dir" "$PY" "$(conventions_file)" "$@" <<'PRESETEOF'
import os, re, sys

directory, python, conventions, mode, rest = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
KINDS = ("stack", "browser", "format", "governance", "stub")
#: Folders no detection looks into: build output, dependencies, tool state. Bounded in depth as well,
#: so a detection never walks a whole disk from a mistaken directory.
PRUNED = {".git", ".gradle", ".idea", ".vs", "build", "bin", "obj", "target", "dist", "out",
          "node_modules", ".venv", "venv", "__pycache__", ".agents", ".claude", ".codex", ".opencode", "tasks"}
DEPTH = 4
#: The project description's default places — the gate's defaults, so no key is needed for them.
LOCATIONS = {"product": "project/product.md", "tech": "project/tech.md", "domain": "project/domain.md"}
#: Which check or stage a profile key switches on — what `--check` says beside a proposed line.
SWITCHES = {
    "compile": "the test, build and tidy gates compile the tests",
    "test": "single tests and the required suites run with it",
    "e2eTest": "the criteria's end-user tests run with it",
    "filterFlag": "single tests are selected by it",
    "filterFormat": "single tests are selected by it",
    "architecture": "the build, tidy and document gates run it",
    "format": "the build and tidy gates run it",
    "formatFix": "the test, build and tidy stages correct formatting with it",
    "browser": "the plan takes browser tests for a page",
}


def files():
    found = []
    for root, dirs, names in os.walk("."):
        depth = 0 if root == "." else root.count(os.sep)
        dirs[:] = sorted(d for d in dirs if d not in PRUNED and depth < DEPTH)
        rel = "" if root == "." else root[2:].replace(os.sep, "/") + "/"
        found += [rel + name for name in sorted(names)]
    return found


def glob_re(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def read_preset(path):
    entries = []
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            entries.append((key.strip(), value.strip()))
    return entries


TREE = None


def matches(globs):
    global TREE
    TREE = files() if TREE is None else TREE
    patterns = [glob_re(g) for g in globs.split()]
    return [f for f in TREE if any(p.match(f) for p in patterns)]


def holds(key, value):
    """The files one detection line matched — empty when it does not hold."""
    if key == "detect.exists":
        return matches(value)
    if key == "detect.contains":
        globs, _, pattern = value.partition(" :: ")
        wanted = re.compile(pattern, re.M)
        hits = []
        for path in matches(globs):
            try:
                if os.path.getsize(path) < 2_000_000 and wanted.search(open(path, encoding="utf-8", errors="ignore").read()):
                    hits.append(path)
            except OSError:
                pass
        return hits
    raise SystemExit(f"factory: unknown detection `{key}` — a preset has detect.exists and detect.contains only")


def detect():
    presets = []
    for name in sorted(os.listdir(directory)) if os.path.isdir(directory) else []:
        if name.endswith(".preset"):
            entries = read_preset(os.path.join(directory, name))
            fields = dict(entries)
            if fields.get("kind") not in KINDS:
                raise SystemExit(f"factory: {name} has no `kind:` of {', '.join(KINDS)}")
            presets.append((KINDS.index(fields["kind"]), int(fields.get("order", 50)), name[:-7], entries))
    presets.sort()
    values, applied, governance, stack, derived = {}, [], False, None, {}
    for kind, _order, name, entries in presets:
        if kind == 0 and stack is not None:
            continue                                   # the first stack that holds wins
        match = None
        for key, value in entries:
            if key.startswith("detect."):
                hit = holds(key, value)
                if not hit:
                    break
                match = hit[0]
        else:
            applied.append(name)
            if kind == 0:
                stack = name
            if kind == 3:
                governance = True
            for key, value in entries:
                if key in ("kind", "order") or key.startswith("detect."):
                    continue
                if key.startswith("conventions."):
                    derived[key[len("conventions."):]] = value
                    continue
                values[key] = value.replace("{match}", match or "").replace("{python}", python)
    # A command the project's conventions file states wins over the preset's, so the profile is not a
    # second truth: the first backticked command there that the preset's pattern matches.
    if conventions and os.path.isfile(conventions) and derived:
        stated = re.findall(r"`([^`\n]+)`", open(conventions, encoding="utf-8").read())
        for key, pattern in derived.items():
            hit = next((s for s in stated if re.search(pattern, s, re.I)), None)
            if hit:
                values[key] = hit
    # What depends on the installed method skills: a carrier line only for a skill that is there.
    installed = set(os.environ.get("FACTORY_SKILLS", "").split())
    for row in os.environ.get("FACTORY_CARRIERS", "").splitlines():
        key, skill, needs = row.split()
        if skill in installed and (needs == "-" or governance):
            values[key] = skill
            if key.startswith("review."):
                values["reviews"] = ", ".join(filter(None, [values.get("reviews", ""), key[len("review."):]]))
    # Where the project description is, from the method's line in AGENTS.md — the line is the source,
    # the profile the factory's view of it. A default location needs no key.
    if os.path.isfile("AGENTS.md"):
        text = open("AGENTS.md", encoding="utf-8").read()
        start, end = "<!-- dca-describe: start -->", "<!-- dca-describe: end -->"
        if start in text and end in text:
            block = text.split(start, 1)[1].split(end, 1)[0]
            for key, path in re.findall(r"^\s*-\s*(product|tech|domain):\s*`([^`]+)`", block, re.M):
                if path != LOCATIONS[key]:
                    values[key] = path
    return values, applied, governance


def norm(value):
    return value.strip().strip('"').strip("'").strip()


def active(path):
    keys = {}
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            keys.setdefault(key.strip(), value.strip())
    return keys


def proposals(values, profile):
    """(missing, differing): what detection finds that the profile lacks, and where it says otherwise.
    A key that qualifies another (`covers.test` for `test`) is proposed only while the qualified key
    holds the detected value — it describes that command, not the person's."""
    missing, differing = [], []
    for key, value in values.items():
        if key.startswith("covers."):
            base = key[len("covers."):]
            if base in profile and norm(profile[base]) != norm(values.get(base, "")):
                continue
        if key not in profile:
            missing.append((key, value))
        elif norm(profile[key]) != norm(value):
            differing.append((key, profile[key], value))
    return missing, differing


def switch(key):
    if key.startswith("test."):
        key = "test"
    if key.startswith("covers."):
        return f"says which tests `{key[len('covers.'):]}:` runs"
    if key.startswith("carrier."):
        return f"the {key[len('carrier.'):]} role is carried by that skill"
    if key.startswith("review."):
        return f"the judge's {key[len('review.'):]} perspective is carried by that skill"
    if key == "reviews":
        return "the judge covers these perspectives as well"
    if key in LOCATIONS:
        return "the stages read it there"
    return SWITCHES.get(key, "")


values, applied, governance = detect()
if mode == "detect":
    for key, value in values.items():
        print(f"{key}\t{value}")
    print("#applied\t" + " ".join(applied))
    if governance:
        print("#governance\tfound")
elif mode == "new":
    template, target = rest
    out = []
    for line in open(template, encoding="utf-8").read().splitlines():
        key = line.split(":", 1)[0].strip()
        if "{{" in line:
            # An undetected command is left out, not left as a placeholder: the gate skips and names
            # what the profile does not declare, but it would try to run a placeholder.
            if values.get(key):
                out.append(f"{key}: {values[key]}")
            continue
        out.append(line)
    written = {l.split(":", 1)[0].strip() for l in out if l and not l.startswith("#") and ":" in l}
    for key, value in values.items():
        if key in written:
            continue
        # a commented line of the template is the key's place; otherwise it goes at the end
        slot = next((i for i, line in enumerate(out) if re.match(rf"#\s*{re.escape(key)}\s*:", line)), None)
        if slot is None:
            out.append(f"{key}: {value}")
        else:
            out[slot] = f"{key}: {value}"
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    print(f"factory: wrote {target} from {', '.join(applied) or 'no preset (nothing detected)'} — check the")
    print("factory:   commands, then add knowledge:, carrier.<role>: and review.<perspective>: where the project has them")
elif mode == "check":
    profile = active(rest[0])
    missing, differing = proposals(values, profile)
    if rest[1:] == ["brief"]:
        if missing:
            print(f"factory: profile — detection finds {', '.join(k for k, _ in missing)} the profile does not declare "
                  "(factory.sh setup --check)")
        raise SystemExit(0)
    # The same view as the status: a table, marks, and what to do in an agent and in a shell.
    import os, shutil, textwrap
    colour = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    paint = lambda text, code: f"\x1b[{code}m{text}\x1b[0m" if colour else text
    width = shutil.get_terminal_size((120, 24)).columns if sys.stdout.isatty() else 120
    title = f"Profile — {os.path.basename(os.getcwd())}"
    print("\n" + paint(title, "1") + "\n" + "═" * len(title) + "\n")
    print(f"  detected   {', '.join(applied) or 'nothing a preset knows'}\n")
    label = lambda text: paint(text.ljust(12), "2")
    for key, value in missing:
        print("    " + paint(f"? {key}", "33") + "   missing" + (f" — {switch(key)}" if switch(key) else ""))
        print(f"        {label('detected')}   {norm(value)}\n")
    for key, have, value in differing:
        print("    " + paint(f"· {key}", "2") + "   differs — kept: the profile's value is a person's decision")
        print(f"        {label('the profile')}   {norm(have)}")
        print(f"        {label('detected')}   {norm(value)}")
        print(f"        {label('to take it')}   bash .agents/factory/factory.sh setup --write --replace {key}\n")
    if not missing and not differing:
        print("    The profile declares everything detection finds.\n")
    print("─" * 72)
    if missing:
        print(f"  {paint('Next', '1')}   add the {len(missing)} missing key(s).")
        print(f"         {paint('agent'.ljust(10), '2')}   {paint('/factory-setup', '36')}")
        print(f"         {paint('shell'.ljust(10), '2')}   bash .agents/factory/factory.sh setup --write")
        print()
        raise SystemExit(1)
    print(f"  {paint('Next', '1')}   Nothing to add." + (" The notes are yours to keep." if differing else ""))
    print()
elif mode == "write":
    path, replace = rest[0], (rest[1] if len(rest) > 1 else "")
    if replace and replace not in values:
        raise SystemExit(f"factory: detection finds no `{replace}:` — nothing to replace")
    profile = active(path)
    missing, _ = proposals(values, profile)
    lines = open(path, encoding="utf-8").read().splitlines()
    changed = []
    if replace and replace in profile:
        for i, line in enumerate(lines):
            if not line.lstrip().startswith("#") and line.split(":", 1)[0].strip() == replace:
                lines[i] = f"{replace}: {values[replace]}"
                changed.append(f"{replace} (replaced)")
                break
    for key, value in missing:
        slot = next((i for i, line in enumerate(lines)
                     if re.match(rf"#\s*{re.escape(key)}\s*:", line)), None)
        if slot is None:
            lines.append(f"{key}: {value}")
        else:
            lines[slot] = f"{key}: {value}"
        changed.append(key)
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        print(f"factory: {path} — wrote {', '.join(changed)}; every other line is as it was")
    else:
        print(f"factory: {path} already declares everything detection finds — nothing written")
else:
    raise SystemExit(f"factory: unknown presets mode {mode}")
PRESETEOF
}

write_profile() {                           # write_profile <skill folder>
  # Prefill from what the project already states, so the profile is not a second truth.
  local from=$1 dir
  dir=$(presets_dir "$from") || dir=""
  must "write the stack profile" presets "$dir" new "$from/factory-run/templates/factory.profile.yaml.tmpl" "$PROFILE"
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
waiting question (`/factory-decisions`), work the backlog (`/factory-run`; to keep listening, a tool
that repeats a prompt runs it again — in Claude Code `/loop /factory-run`), look closer (`/factory-status`), or
learn how the factory works (`/factory-help`).

An instruction that changes what an actor can see or do is a user story. Before any code, ask once, in
these words: "As a story through the factory — to an existing epic, a new epic — or directly by hand?"
For the factory, run `/factory-run` with the person's words: it writes the story through
`/factory-backlog` and runs it once it is released. A fix, a refactoring, documentation, tooling or a
question is done directly.

A session never runs `factory.sh run` — it starts a tool process per stage. One worker per checkout: a
managing session writes backlog and decision files only. Every change — by a stage or by hand in a
session — passes `bash .agents/factory/factory.sh check` before it is committed; the commit hook runs it
on what is staged.
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
        if line.startswith(("compile:", "test:", "test.", "e2eTest:", "architecture:", "format:", "formatFix:")):
            command = line.split(":", 1)[1].strip().strip("\"'")
            head = command.split()[0] if command else ""
            if head and not head.startswith("{{"):
                wanted.append(f"Bash({head}:*)")
# the reading commands, so a session looks without being asked; `run` is not in it — it starts a
# tool process per stage, and the runner refuses it inside a session anyway
for verb in ("status", "decisions", "backlog", "setup --check", "verify"):
    wanted.append(f"Bash(bash .agents/factory/factory.sh {verb}:*)")
# what an earlier install allowed under verbs that are gone
retired = {f"Bash(bash .agents/factory/factory.sh {verb}:*)" for verb in ("usage", "schedule")}
removed = [entry for entry in allow if entry in retired]
allow[:] = [entry for entry in allow if entry not in retired]
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
if removed:
    print("factory: .claude/settings.json no longer allows " + ", ".join(removed) + " — verbs the runner does not have")
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
    | grep -v -i -E '^[[:space:]]*([-*][[:space:]]*)?[(_*]*(none|n/a|nothing|—|–)?[.]?[)_*]*[.]?[[:space:]]*$' | grep -q .
}

# A stage that ends with a needs-human section has stopped. The question is a record of its own, so
# the answer has a place to land and a second session finds it without this transcript: name the
# file, and the command that resumes. 3 only when the question is a record — that is what a backlog
# run can wait on; a section without one is a stop a human has to look at, like any other failure.
stopped_for_human() {                       # stopped_for_human <artefact> <stage> <story>
  local artefact=$1 stage=$2 story=$3 ids id applies
  echo "factory: stage '$stage' ends with a needs-human section — the run stops here." >&2
  ids=$(sed -n '/^## needs-human/,/^## /p' "$artefact" | sed -n 's/^[[:space:]-]*decision:[[:space:]]*//p')
  if [ -z "$ids" ]; then
    echo "factory:   the section names no 'decision: <id>' — the stage has to write the question as" >&2
    echo "factory:   $DECISIONS/<story>-<nn>.md; the next gate refuses a question nobody was asked." >&2
  fi
  for id in $ids; do
    if [ -f "$DECISIONS/$id.md" ]; then
      # The record names the stage that applies the answer — for a judge's story conflict that is
      # not the judge. That is where the story resumes.
      applies=$(sed -n 's/^stage:[[:space:]]*//p' "$DECISIONS/$id.md" | head -1)
      echo "factory:   decision $id → $DECISIONS/$id.md — answer it there under '## Answer'" >&2
      echo "factory:   with answer:, by: and at:, then: factory.sh run --story $story --from ${applies:-$stage}" >&2
    else
      echo "factory:   decision $id is named but $DECISIONS/$id.md does not exist." >&2
    fi
  done
  echo "factory:   read $artefact and decide; the stages after it were not run." >&2
  [ -n "$ids" ] && return 3
  return 1
}

# --shared-builder: plan, test, build and tidy in ONE tool process, so each stage builds on what the
# one before read instead of reading it again (measured: −31 % on a story, the same tokens but far
# fewer cache writes). Off unless asked for, per run. The process runs each stage's gate itself; the
# runner then checks, not believes: the red proof must exist (the test gate ran and saw the tests
# fail) and the build and tidy gates run again here. The judge and the document stage stay separate
# processes with a fresh context — the judge's independence is the point of it. Only `model.<tool>`
# applies to the shared process; per-stage model keys need a process per stage.
BUILDER_STAGES=(plan test build tidy)
run_shared_builder() {                      # run_shared_builder <story> <tool> <from> <dry>
  local story=$1 tool=$2 from=$3 dry=$4 range=() on=0 st
  for st in "${BUILDER_STAGES[@]}"; do [ "$st" = "$from" ] && on=1; [ "$on" = 1 ] && range+=("$st"); done
  local list; list=$(IFS=+; echo "${range[*]}")
  local prompt="Carry out these stages of the delivery pipeline for backlog story $story, one after another, \
in this one session: $(printf 'stage-%s, ' "${range[@]}" | sed 's/, $//') — apply each stage's skill in turn, \
reading only the story and the files that stage's skill names as its input, and writing its output file under \
$TASKS/$story/. After the test, build and tidy stages run that stage's gate, \
\`$PY $GATE --story $story --stage <stage>\`, and fix exactly what it names before the next stage, at most \
three attempts per stage. Stop at once when a stage ends in a needs-human section. Do not run the judge or the \
document stage."
  local guard; guard=$(sed -n 's/^carrier\.guard:[[:space:]]*//p' "${FACTORY_PROFILE:-.agents/factory/factory.profile.yaml}" 2>/dev/null | head -1 | tr -d '"'"'"'"')
  [ -n "$guard" ] && prompt="$prompt In the build and tidy stages apply the $guard skill (the profile's carrier.guard) to every file you write."
  echo "── stage $list  (tool: $tool, one shared context)"
  if [ -n "$dry" ]; then
    echo "   would run: $prompt"
    echo "   tool flags: $(isolation_flags "$tool")${FACTORY_ISOLATION:+(FACTORY_ISOLATION=$FACTORY_ISOLATION)}"
    local dry_choice; dry_choice=$(model_choice "$tool" builder)
    echo "   model: ${dry_choice%%|*}${dry_choice#*|}"
    return 0
  fi
  if [ -f "$GATE" ] && ! "$PY" "$GATE" --claim "$WORKER" >/dev/null; then
    echo "factory: the checkout was taken over by another worker before the shared stages — stopping." >&2; return 5
  fi
  if [ -n "$STORY_BUDGET" ] && [ "$("$PY" "$GATE" --usage --story "$story" --total 2>/dev/null || echo 0)" -ge "$STORY_BUDGET" ]; then
    echo "factory: story $story has reached its --story-budget $STORY_BUDGET — the shared stages are not dispatched." >&2; return 4
  fi
  if [ -n "$MAX_STAGES" ] && [ "$INVOCATIONS" -ge "$MAX_STAGES" ]; then
    echo "factory: --max-stages $MAX_STAGES reached before the shared stages of $story." >&2; return 4
  fi
  local journal="$TASKS/$story/.verify/journal.tsv" began raw_out invoked=0
  [ -f "$GATE" ] && "$PY" "$GATE" --record-base --story "$story" >/dev/null 2>&1
  snapshot "$story" "before-builder"
  printf '%s\tstage-start\tbuilder\ttool=%s\tstages=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tool" "$(IFS=,; echo "${range[*]}")" >> "$journal"
  raw_out="$TASKS/$story/.verify/builder.$(date -u +%H%M%S).out"
  began=$(date +%s)
  invocation_raw="$raw_out" stage_in_flight=builder story_in_flight="$story" invoke "$tool" "$prompt" || invoked=$?
  record_usage "$story" builder "$tool" "$raw_out" "$(( $(date +%s) - began ))"
  printf '%s\tstage-end\tbuilder\texit=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$([ "$invoked" = 0 ] && echo 0 || echo nonzero)" >> "$journal"
  [ "$invoked" = 0 ] || { echo "factory: the tool exited non-zero during the shared stages." >&2; return 1; }
  snapshot "$story" "after-builder"
  [ -f "$GATE" ] && "$PY" "$GATE" --record-changes builder --story "$story" >/dev/null 2>&1
  for st in "${range[@]}"; do
    local artefact="$TASKS/$story/$(stage_file "$st")"
    [ -f "$artefact" ] || { echo "factory: the shared stages produced no $artefact — stage '$st' is not finished." >&2; return 1; }
    if asks_human "$artefact"; then stopped_for_human "$artefact" "$st" "$story"; return $?; fi
  done
  # Checked, not believed: the process says it ran the gates; the runner looks.
  if [[ " ${range[*]} " == *" test "* ]] && [ ! -s "$TASKS/$story/.tests-red" ]; then
    echo "factory: the shared stages left no red proof ($TASKS/$story/.tests-red) — the test gate never saw the tests fail." >&2
    return 1
  fi
  for st in build tidy; do
    [[ " ${range[*]} " == *" $st "* ]] || continue
    echo "── gate $st  (re-checked by the runner)"
    gate "$st" "$story" || { echo "factory: the runner's re-check of gate '$st' refused the shared stages' work." >&2; return 1; }
  done
  return 0
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
  # The guard the profile names holds the invariants while code is edited: said in the prompt of the two
  # stages that write production code, so no build or tidy stage starts without it in view.
  local guard="" profile="${FACTORY_PROFILE:-.agents/factory/factory.profile.yaml}"
  case "$stage" in build|tidy)
    guard=$(sed -n 's/^carrier\.guard:[[:space:]]*//p' "$profile" 2>/dev/null | head -1 | tr -d '"'"'"'"')
    [ -n "$guard" ] && guard=" Apply the $guard skill (the profile's carrier.guard) to every file you write." ;;
  esac
  printf '%s' "Apply the stage-$stage skill for backlog story $story. \
Read only the story and the files the skill names as its input, and write its output file under \
$TASKS/$story/. Do the stage yourself in this session; do not delegate it. Do not run other stages.$guard$repeat"
}

gate() {                                    # gate <stage> <story>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh setup'" >&2; return 2; }
  local report="$TASKS/$2/.gate-$1.txt" journal="$TASKS/$2/.verify"
  mkdir -p "$TASKS/$2" "$journal"
  "$PY" "$GATE" --story "$2" --stage "$1" 2>&1 | tee "$report"
  local code=${PIPESTATUS[0]}
  # Every gate run is kept for the observer, with its verdict; only a *refusal* is kept where the
  # next stage reads it. A run that has to be reconstructed afterwards from what a stage claimed is
  # exactly the evidence the gate exists to replace.
  cp "$report" "$journal/gate-$1.$(date -u +%H%M%S).txt"
  printf '%s\tgate\t%s\texit=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$code" >> "$journal/journal.tsv"
  # 3 is not a refusal: every check passed and a human is asked (acceptance) — nothing to run again.
  { [ "$code" = 0 ] || [ "$code" = 3 ]; } && rm -f "$report"
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
  local journal="$TASKS/$1/.verify" file hash prefix entry code origin
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
    # untouched. `--porcelain` also quotes unusual names, hence the -z form and the NUL split. Its
    # paths are the repository's; `-- .` and the prefix make them the project's, which may be a
    # directory inside it. A tracked file that is gone is recorded as `deleted` — left out, its
    # removal would be in no stage's record.
    prefix=$(git rev-parse --show-prefix 2>/dev/null)
    git -c core.fileMode=false status --porcelain -z -uall -- . 2>/dev/null \
      | tr '\0' '\n' | { origin=""; while IFS= read -r entry; do
      [ -n "$entry" ] || continue
      if [ -n "$origin" ]; then           # -z writes a rename's source as the next entry
        [ "$origin" = R ] && printf '%s  %s\n' deleted "${entry#"$prefix"}"
        origin=""
        continue
      fi
      code=${entry:0:2} file=${entry:3}
      file=${file#"$prefix"}
      case $code in R*|C*) origin=${code:0:1} ;; esac
      case $code in *D*) printf '%s  %s\n' deleted "$file"; continue ;; esac
      [ -f "$file" ] || continue
      if [ "$hash" = none ]; then
        printf '%s  %s\n' "-" "$file"
      else
        printf '%s  %s\n' "$($hash "$file" 2>/dev/null | cut -d" " -f1)" "$file"
      fi
    done; }
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

# The adopt gate: every scenario on a green test, the judge's pass, a break for every test the adoption
# wrote. Passed, it delivers the story; refused, the test stage runs again, one round counted.
adopt_gate() {                              # adopt_gate <story> <tool> <dry>
  echo "── gate adopt"
  [ -n "$3" ] && return 0
  if gate adopt "$1"; then
    echo "factory: story $1 is adopted."
    return 0
  fi
  local rounds; rounds=$(bump_rounds "$1")
  if [ "$rounds" -ge 3 ]; then
    echo "factory: gate 'adopt' refused in round $rounds — three rounds did not converge. needs-human." >&2
    return 1
  fi
  echo "factory: gate 'adopt' refused — round $rounds runs the test stage again with the gate's report." >&2
  run_story "$1" "$2" test "$3"
}

run_story() {
  local story=$1 tool=$2 from=${3:-plan} dry=${4:-}
  local started=0 ran="" waiting built=""
  waiting=$(open_decisions "$story")
  if [ -n "$waiting" ]; then
    echo "factory: story $story waits for a decision — no stage runs until it is answered:" >&2
    printf 'factory:   %s\n' $waiting >&2
    echo "factory:   answer under '## Answer' with answer:, by: and at:, then run the stage that asked (--from <stage>)." >&2
    return 3
  fi
  local kind; kind=$("$PY" "$GATE" --story "$story" --kind 2>/dev/null || echo story)
  # An adopted story whose judge passed: only the adopt gate is left, and it delivers the story.
  if [ "$from" = adopt ]; then
    adopt_gate "$story" "$tool" "$dry"
    return $?
  fi
  for stage in "${STAGES[@]}"; do
    [ "$stage" = "$from" ] && started=1
    [ "$started" = 1 ] || continue
    # A journey walks what is delivered: nothing to build, nothing to tidy.
    if [ "$kind" = journey ] && { [ "$stage" = build ] || [ "$stage" = tidy ]; }; then
      echo "── stage $stage  (skipped: a journey builds nothing)"
      continue
    fi
    # An adoption builds nothing and documents nothing: plan, test, judge, then the adopt gate.
    if [ "$kind" = adopt ] && { [ "$stage" = build ] || [ "$stage" = tidy ] || [ "$stage" = document ]; }; then
      echo "── stage $stage  (skipped: an adopted story is not built)"
      continue
    fi

    if [[ " ${PRE_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      gate "$stage" "$story" || { echo "factory: gate '$stage' refused the story. Fix it before the stage runs." >&2; return 1; }
    fi

    if [ -n "$SHARED_BUILDER" ] && [[ " ${BUILDER_STAGES[*]} " == *" $stage "* ]]; then
      if [ -z "$built" ]; then
        run_shared_builder "$story" "$tool" "$stage" "$dry" || return $?
        built=1
      fi
      ran="${ran:+$ran,}$stage"
      continue
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
      local dry_choice; dry_choice=$(model_choice "$tool" "$stage")
      echo "   model: ${dry_choice%%|*}${dry_choice#*|}"
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
      [ -f "$GATE" ] && "$PY" "$GATE" --record-base --story "$story" >/dev/null 2>&1
      snapshot "$story" "before-$stage"
      local choice requested note model_fields=""
      choice=$(model_choice "$tool" "$stage"); note=${choice#*|}; requested=$(model_key "$tool" "$stage")
      [ -n "$requested" ] && model_fields="	model_requested=$requested"
      [ -n "$note" ] && model_fields="$model_fields	model_applied=no ($note)"
      [ -n "$note" ] && echo "factory: model.$tool.$stage: $requested — $note"
      printf '%s\tstage-start\t%s\ttool=%s%s\n' "$stage_started" "$stage" "$tool" "$model_fields" >> "$TASKS/$story/.verify/journal.tsv"
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
      # What the stage changed and the story's diff so far, for the next stage to read first.
      [ -f "$GATE" ] && "$PY" "$GATE" --record-changes "$stage" --story "$story" >/dev/null 2>&1
      local artefact="$TASKS/$story/$(stage_file "$stage")"
      [ -f "$artefact" ] || {
        echo "factory: stage '$stage' produced no $artefact — a stage is finished when its file exists." >&2
        return 1; }
      # A stage that ends with a needs-human section has stopped, whatever its file otherwise says.
      # Reading only "does the file exist" turns an escalation into a hand-over, and the next stage
      # then builds on a decision nobody took.
      if asks_human "$artefact"; then
        stopped_for_human "$artefact" "$stage" "$story"
        return $?
      fi
    fi

    if [[ " ${POST_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      local gate_code=0
      [ -z "$dry" ] && { gate "$stage" "$story" || gate_code=$?; }
      if [ "$gate_code" = 3 ]; then
        echo "factory: story $story waits for a human's acceptance — answer it with /factory-decisions;" >&2
        echo "factory:   the story holds the checkout until then." >&2
        return 3
      fi
      if [ "$gate_code" != 0 ]; then
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
        pass)
          echo "factory: judge verdict 'pass'."
          if [ "$kind" = adopt ]; then
            adopt_gate "$story" "$tool" "$dry"
            return $?
          fi
          ;;
        changes-requested)
          rounds=$(bump_rounds "$story")
          if [ "$rounds" -ge 3 ]; then
            echo "factory: judge verdict 'changes-requested' in round $rounds — three rounds did not converge. needs-human." >&2
            return 1
          fi
          local back=build; { [ "$kind" = journey ] || [ "$kind" = adopt ]; } && back=test
          echo "factory: judge verdict 'changes-requested' — round $rounds goes back to the $back stage." >&2
          run_story "$story" "$tool" "$back" "$dry"
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
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh setup'" >&2; return 2; }
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

# --- setup -------------------------------------------------------------------

# The commit hook and the worker lock live in .git, so the pipeline needs a repository. Asked with
# `rev-parse`, not "has a commit": a repository without one is a fine place to start.
require_git() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 && return 0
  echo "factory: not a git repository — 'git init' first; the commit hook and the worker lock live in .git." >&2
  return 1
}

installed() { [ -f "$GATE" ] && [ -f .agents/factory/factory.sh ]; }

# What detection finds against the profile — read-only in every state. Exit 1 when the runner is
# missing or a detected key is absent; a value that differs from detection is a person's decision
# and only a note, because a check that goes red on a decision gets switched off.
setup_check() {                             # setup_check [brief]
  local brief=${1:-} dir
  if ! installed; then
    [ -n "$brief" ] && return 0
    echo "factory: no runner — factory.sh setup"
    return 1
  fi
  dir=$(presets_dir) || dir=""
  if [ -z "$dir" ]; then
    [ -n "$brief" ] && return 0
    echo "factory: no presets found — no pipeline beside this project to detect with (FACTORY_PLUGIN_DIR names one)"
    return 0
  fi
  if [ ! -f "$PROFILE" ]; then
    [ -n "$brief" ] && return 0
    echo "factory: no stack profile at $PROFILE — 'factory.sh update' writes one from detection"
    return 1
  fi
  presets "$dir" check "$PROFILE" ${brief:+brief}
}

# Adds what detection finds and the profile lacks; never overwrites a value a person wrote, except the
# one key --replace names. The Claude allow list is derived from the profile's commands, so it follows.
setup_write() {                             # setup_write [<key>]
  local dir
  installed || { echo "factory: no runner — factory.sh setup"; return 1; }
  [ -f "$PROFILE" ] || { echo "factory: no stack profile at $PROFILE — 'factory.sh update' writes one"; return 1; }
  dir=$(presets_dir) || dir=""
  [ -n "$dir" ] || { echo "factory: no presets found — nothing to write from (FACTORY_PLUGIN_DIR names a pipeline)" >&2; return 2; }
  presets "$dir" write "$PROFILE" ${1:+"$1"} || return $?
  [ -d .claude ] && write_claude_permissions
  return 0
}

# --- main --------------------------------------------------------------------

[ $# -ge 1 ] || usage
command=$1; shift
story=""; tool=""; from="plan"; dry=""; source_dir=""; copy_mode=""; watch=""; interval=60
setup_mode=""; replace_key=""; want_usage=""; want_brief=""; session_start=""; live=""; view=()

# The reading commands are the gate's; the runner passes them on, so a project calls one script.
read_command() {                            # read_command <gate flags…>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh setup' from the plugin" >&2; exit 2; }
  exec "$PY" "$GATE" "$@"
}
case "$command" in
  status)
    while [ $# -gt 0 ]; do
      case "$1" in
        --story) [ $# -ge 2 ] || usage; story=$2; shift 2 ;;
        --usage) want_usage=1; shift ;;
        --brief) want_brief=1; shift ;;
        --session-start) session_start=1; shift ;;
        --format|--color) [ $# -ge 2 ] || usage; view+=("$1" "$2"); shift 2 ;;
        --live) live=1; view+=("--live"); shift ;;
        *) usage ;;
      esac
    done
    if [ -n "$want_brief" ]; then
      [ -f "$GATE" ] || exit 0
      setup_check brief
      read_command --status --brief ${session_start:+--session-start}
    fi
    [ -n "$want_usage" ] && read_command --usage ${story:+--story "$story"}
    # Which pipeline this machine has is not the project's state: said with --live only, so the same
    # files give the same view everywhere.
    [ -n "${live:-}" ] && check_gate_freshness
    read_command --status ${story:+--story "$story"} ${view[@]+"${view[@]}"} ;;
  backlog)
    # The person's view of the backlog; the runner reads the schedule's lines from the gate itself.
    case "${1:-}" in
      --check) read_command --check-backlog ;;
      *) read_command --status --part backlog "$@" ;;
    esac ;;
  decisions) read_command --list-decisions "$@" ;;
  help)
    # The help works before the pipeline is installed too: then the plugin's gate explains it.
    helper=$GATE
    [ -f "$helper" ] || helper=$(plugin_gate) || { echo "factory: no gate found to explain the factory — FACTORY_PLUGIN_DIR names one" >&2; exit 2; }
    exec "$PY" "$helper" --help-view "$@" ;;
  check)
    case "${1:-}" in
      --parity) [ $# -eq 2 ] || usage; read_command --parity "$2" ;;
      *) read_command --change "$@" ;;
    esac ;;
  verify)
    case "${1:-}" in
      --story)
        [ $# -eq 2 ] || usage
        [ -f .agents/factory/observe.py ] || {
          echo "factory: no observer at .agents/factory/observe.py — 'factory.sh update' copies it there" >&2; exit 2; }
        exec "$PY" .agents/factory/observe.py --story "$2" ;;
      --fixtures)
        [ $# -eq 1 ] || usage
        skills=$(plugin_skills) && [ -f "$skills/factory-verify/scripts/verify.py" ] || {
          echo "factory: no pipeline found whose fixtures could run — FACTORY_PLUGIN_DIR names one" >&2; exit 2; }
        echo "factory: the machinery of $skills"
        exec "$PY" "$skills/factory-verify/scripts/verify.py" ;;
      *) usage ;;
    esac ;;
esac

while [ $# -gt 0 ]; do
  case "$1" in
    --story) story=$2; shift 2 ;;
    --tool) tool=$2; shift 2 ;;
    --from) case "$command" in setup|update) source_dir=$2 ;; *) from=$2 ;; esac; shift 2 ;;
    --copy) copy_mode=1; shift ;;
    --check) [ "$command" = setup ] || usage; setup_mode=check; shift ;;
    --write) [ "$command" = setup ] || usage; setup_mode=write; shift ;;
    --replace) [ "$command" = setup ] && [ $# -ge 2 ] || usage; replace_key=$2; shift 2 ;;
    --dry-run) dry=1; shift ;;
    --watch) watch=1; shift ;;
    --interval) interval=$2; shift 2 ;;
    --max-stages) MAX_STAGES=$2; shift 2 ;;
    --story-budget) STORY_BUDGET=$2; shift 2 ;;
    --shared-builder) SHARED_BUILDER=1; shift ;;
    *) usage ;;
  esac
done

case "$command" in
  setup)
    [ -z "$replace_key" ] || [ "$setup_mode" = write ] || usage
    require_git || exit 1
    case "$setup_mode" in
      check) setup_check; exit $? ;;
      write) setup_write "$replace_key"; exit $? ;;
    esac
    if installed; then
      # Idempotent: an installed pipeline is `update`'s to replace. Only a tool named explicitly that
      # has no skills here yet is missing, and that is what setup adds.
      if [ -n "$tool" ] && [ -n "$(skill_dir_of "$tool")" ] && [ -z "$(skills_mode "$(skill_dir_of "$tool")")" ]; then
        install_project "$tool" "$source_dir" "$copy_mode"
        exit $?
      fi
      echo "factory: the pipeline is installed here — setup installs nothing ('factory.sh update' replaces its files)"
      setup_check
      exit 0
    fi
    install_project "${tool:-all}" "$source_dir" "$copy_mode" ;;
  update)  update_project "$source_dir" ;;
  run)
    [ -n "$tool" ] || tool=$(detect_tool)
    [ -n "$tool" ] || [ -n "${FACTORY_TOOL_CMD:-}" ] || { echo "factory: no agent tool found on PATH." >&2; exit 2; }
    case "$MAX_STAGES" in *[!0-9]*) echo "factory: --max-stages takes a number" >&2; exit 2 ;; esac
    case "$STORY_BUDGET" in *[!0-9]*) echo "factory: --story-budget takes a number of tokens" >&2; exit 2 ;; esac
    if [ -n "$story" ]; then
      [ -z "$watch" ] || { echo "factory: --watch works the backlog off — it takes no --story" >&2; exit 2; }
      tool=${tool:-stand-in}
      check_gate_freshness                  # once per invocation; run_story recurses on a verdict
      [ -n "$dry" ] || refuse_nested || exit $?
      check_carriers "$tool" || exit $?
      check_contract_first || exit $?
      check_local_context "$tool"
      isolated || echo "factory: FACTORY_ISOLATION=off — stages run with the tool's full setup, user plugins included" >&2
      [ -n "$dry" ] || take_checkout || exit $?
      run_story "$story" "$tool" "$from" "$dry"
      exit $?
    fi
    # Without --story: the backlog, story after story in the order the schedule names.
    case "$interval" in ''|*[!0-9]*) echo "factory: --interval takes whole seconds" >&2; exit 2 ;; esac
    # Bounded both ways: below a second the watch is a busy loop, above an hour an answer waits
    # longer than anyone expects to.
    [ "$interval" -lt 1 ] && interval=1
    [ "$interval" -gt 3600 ] && interval=3600
    check_gate_freshness
    [ -n "$dry" ] || refuse_nested || exit $?
    check_carriers "${tool:-}" || exit $?
    check_contract_first || exit $?
    check_local_context "${tool:-}"
    isolated || echo "factory: FACTORY_ISOLATION=off — stages run with the tool's full setup, user plugins included" >&2
    [ -n "$dry" ] || take_checkout || exit $?
    run_backlog "${tool:-stand-in}" "$watch" "$interval" "$dry"
    ;;
  *) usage ;;
esac
