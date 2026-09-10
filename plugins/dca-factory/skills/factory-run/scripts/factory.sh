#!/usr/bin/env bash
# The factory outside the session: one process per stage, so every stage starts with a fresh
# context and reads only its story and its predecessor's file. Same stages, same gate, same
# files as running the skills inside a session — this only changes who holds the context.
#
#   factory.sh install [--tool claude|codex|opencode|all] [--from <skill folder>] [--copy]
#   factory.sh run --story <id> [--tool <tool>] [--from <stage>] [--dry-run]
#
# The tool adapters below are the only tool-specific lines in the whole pipeline. Adding a tool
# is one entry, not a change to any stage.

set -uo pipefail

STAGES=(plan test build judge document)
# Which gate runs when. `plan` is the only gate that can run *before* its stage: it reads the
# backlog alone. Every other gate judges the file its stage writes — `tests.md`, the implementation,
# `document.md` — so it runs after it. Gating `test` up front would refuse every story for the
# missing file its own stage is about to write.
PRE_GATED=(plan)
POST_GATED=(test build document)
GATE=".agents/factory/story-gate.py"
TASKS="tasks"

# A stage is finished when its hand-over file exists. The names are the file contract's, not the
# stage names — the test stage writes `tests.md`, because the table in it maps several tests.
stage_file() {
  case "$1" in
    test) echo "tests.md" ;;
    *)    echo "$1.md" ;;
  esac
}

usage() { sed -n '2,12p' "$0" >&2; exit 2; }

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
  local list="Bash(python3 $GATE:*)"
  if [ -f "$profile" ]; then
    local head
    for key in compile test e2eTest architecture format; do
      head=$(sed -n "s/^$key:[[:space:]]*//p" "$profile" | head -1 | tr -d '"'"'"'"' | awk '{print $1}')
      [ -n "$head" ] && case "$list" in *"Bash($head:*)"*) ;; *) list="$list,Bash($head:*)" ;; esac
    done
  fi
  echo "$list"
}

invoke() {                                  # invoke <tool> <prompt>
  local tool=$1 prompt=$2
  case "$tool" in
    claude)   claude -p "$prompt" --permission-mode acceptEdits \
                --allowed-tools "Read,Write,Edit,Glob,Grep,Skill,$(allowed_commands)" ;;
    codex)    codex exec -s workspace-write \
                -c sandbox_workspace_write.network_access=true "$prompt" ;;
    opencode) opencode run "$prompt" ;;
    *)        echo "factory: unknown tool '$tool'" >&2; return 2 ;;
  esac
}

# --- install -----------------------------------------------------------------

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
    *)        usage ;;
  esac
  for target in "${targets[@]}"; do
    mkdir -p "$target"
    # A copy of a skill folder is a second truth: an edit at the source does not reach the project,
    # and the project keeps running yesterday's process while its author believes otherwise (that
    # is how a whole set of runs can use a stale stage). So a local source is *linked* by default;
    # --copy is for a real distribution, where there is no source directory to point at.
    for skill in "$from"/*; do
      [ -d "$skill" ] || continue
      local name; name=$(basename "$skill")
      rm -rf "$target/$name"
      if [ -n "$copy_mode" ]; then
        cp -R "$skill" "$target/$name"
      else
        ln -s "$(cd "$skill" && pwd)" "$target/$name"
      fi
    done
    echo "factory: skills → $target ($([ -n "$copy_mode" ] && echo copied || echo "linked to $from"))"
  done
  check_dca_setup
  mkdir -p .agents/factory .githooks
  cp "$from/factory-run/scripts/story-gate.py" "$GATE"
  cp "$from/factory-run/templates/githooks/pre-commit" .githooks/pre-commit
  chmod +x .githooks/pre-commit "$GATE"
  git config core.hooksPath .githooks 2>/dev/null && echo "factory: git hooks → .githooks"
  [ -f .agents/factory/factory.profile.yaml ] || write_profile "$from"
  case "$tool" in
    claude|all) write_claude_permissions ;;
  esac
  echo "factory: the copies under .claude/.codex/.opencode belong in .gitignore"
}

check_dca_setup() {
  # The factory delivers stories; it does not install an architecture. That is the bootstrap
  # skill's job, and it runs once. Say so instead of quietly starting without one.
  if ls **/ArchitectureTest.* */ArchitectureTest.* 2>/dev/null | head -1 | grep -q . \
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
  cp "$from/factory-run/templates/factory.profile.yaml.tmpl" .agents/factory/factory.profile.yaml
  local compile="" test="" architecture="" filter_flag="" filter_format=""
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
    compile="dotnet build"; test="dotnet test"; architecture="dotnet test --filter FullyQualifiedName~Architecture"
    filter_flag="--filter"; filter_format='"FullyQualifiedName~{class}.{method}"'
  fi
  if [ -n "$conventions" ]; then
    local stated
    stated=$(grep -oE '`[^`]*(gradlew|mvnw|dotnet)[^`]*`' "$conventions" | tr -d '`' | grep -iE "arch" | head -1)
    [ -n "$stated" ] && architecture="$stated"
    echo "factory: read build facts from $conventions"
  fi
  python3 - "$compile" "$test" "$architecture" "$filter_flag" "$filter_format" <<'PYEOF'
import sys
compile_, test, architecture, filter_flag, filter_format = sys.argv[1:6]
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
open(path, "w").write("\n".join(out) + "\n")
PYEOF
  echo "factory: wrote .agents/factory/factory.profile.yaml — check the commands, then add"
  echo "factory:   knowledge:, carrier.<stage>: and review.<perspective>: where the project has them"
}

write_claude_permissions() {
  # Claude Code asks before running a command. In a non-interactive run there is nobody to ask,
  # so the gate cannot run and no stage can be verified — the tool then stops, correctly. These
  # two entries are the smallest allowlist that lets the pipeline verify itself; every other
  # command still asks.
  python3 - <<'PYEOF'
import json, os
path = ".claude/settings.json"
os.makedirs(".claude", exist_ok=True)
settings = {}
if os.path.isfile(path):
    with open(path) as handle:
        settings = json.load(handle)
allow = settings.setdefault("permissions", {}).setdefault("allow", [])
wanted = ["Bash(python3 .agents/factory/story-gate.py:*)"]
profile = ".agents/factory/factory.profile.yaml"
if os.path.isfile(profile):
    for line in open(profile):
        if line.startswith(("compile:", "test:", "e2eTest:", "architecture:", "format:")):
            command = line.split(":", 1)[1].strip().strip("\"'")
            head = command.split()[0] if command else ""
            if head and not head.startswith("{{"):
                wanted.append(f"Bash({head}:*)")
added = [entry for entry in dict.fromkeys(wanted) if entry not in allow]
allow.extend(added)
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
  printf '%s' "Apply the stage-$stage skill for backlog story $story. \
Read only the story and the files the skill names as its input, and write its output file under \
$TASKS/$story/. Do the stage yourself in this session; do not delegate it. Do not run other stages.$repeat"
}

gate() {                                    # gate <stage> <story>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh install'" >&2; return 2; }
  local report="$TASKS/$2/.gate-$1.txt"
  mkdir -p "$TASKS/$2"
  python3 "$GATE" --story "$2" --stage "$1" 2>&1 | tee "$report"
  local code=${PIPESTATUS[0]}
  [ "$code" = 0 ] && rm -f "$report"      # only a refusal is worth handing on
  return "$code"
}

run_story() {
  local story=$1 tool=$2 from=${3:-plan} dry=${4:-}
  local started=0
  for stage in "${STAGES[@]}"; do
    [ "$stage" = "$from" ] && started=1
    [ "$started" = 1 ] || continue

    if [[ " ${PRE_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      gate "$stage" "$story" || { echo "factory: gate '$stage' refused the story. Fix it before the stage runs." >&2; return 1; }
    fi

    echo "── stage $stage  (tool: $tool, fresh context)"
    if [ -n "$dry" ]; then
      echo "   would run: $(prompt_for "$stage" "$story")"
    else
      invoke "$tool" "$(prompt_for "$stage" "$story")" || {
        echo "factory: the tool exited non-zero during stage '$stage'." >&2; return 1; }
      local artefact="$TASKS/$story/$(stage_file "$stage")"
      [ -f "$artefact" ] || {
        echo "factory: stage '$stage' produced no $artefact — a stage is finished when its file exists." >&2
        return 1; }
    fi

    if [[ " ${POST_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      [ -n "$dry" ] || gate "$stage" "$story" || {
        echo "factory: gate '$stage' failed after the stage. Re-run this stage with the gate output." >&2
        return 1; }
    fi

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
  echo "factory: story $story ran through $(IFS=,; echo "${STAGES[*]}")."
}

# --- main --------------------------------------------------------------------

[ $# -ge 1 ] || usage
command=$1; shift
story=""; tool=""; from="plan"; dry=""; source_dir=""; copy_mode=""

while [ $# -gt 0 ]; do
  case "$1" in
    --story) story=$2; shift 2 ;;
    --tool) tool=$2; shift 2 ;;
    --from) if [ "$command" = "install" ]; then source_dir=$2; else from=$2; fi; shift 2 ;;
    --copy) copy_mode=1; shift ;;
    --dry-run) dry=1; shift ;;
    *) usage ;;
  esac
done

case "$command" in
  install) install_skills "${tool:-all}" "$source_dir" "$copy_mode" ;;
  run)
    [ -n "$story" ] || usage
    [ -n "$tool" ] || tool=$(detect_tool)
    [ -n "$tool" ] || { echo "factory: no agent tool found on PATH." >&2; exit 2; }
    run_story "$story" "$tool" "$from" "$dry"
    ;;
  *) usage ;;
esac
