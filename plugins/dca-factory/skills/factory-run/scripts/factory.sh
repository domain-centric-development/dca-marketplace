#!/usr/bin/env bash
# The factory outside the session: one process per stage, so every stage starts with a fresh
# context and reads only its story and its predecessor's file. Same stages, same gate, same
# files as running the skills inside a session — this only changes who holds the context.
#
#   factory.sh install [--tool claude|codex|opencode|all] [--from <skill folder>]
#   factory.sh run --story <id> [--tool <tool>] [--from <stage>] [--dry-run]
#
# The tool adapters below are the only tool-specific lines in the whole pipeline. Adding a tool
# is one entry, not a change to any stage.

set -uo pipefail

STAGES=(plan test build judge document)
GATED=(plan test build document)          # stages whose gate runs before them; build gates after
GATE=".agents/factory/story-gate.py"
TASKS="tasks"

usage() { sed -n '2,12p' "$0" >&2; exit 2; }

# --- tool adapters -----------------------------------------------------------

detect_tool() {
  for candidate in claude codex opencode; do
    command -v "$candidate" >/dev/null 2>&1 && { echo "$candidate"; return; }
  done
  echo ""
}

invoke() {                                  # invoke <tool> <prompt>
  local tool=$1 prompt=$2
  case "$tool" in
    claude)   claude -p "$prompt" --permission-mode acceptEdits ;;
    codex)    codex exec -s workspace-write \
                -c sandbox_workspace_write.network_access=true "$prompt" ;;
    opencode) opencode run "$prompt" ;;
    *)        echo "factory: unknown tool '$tool'" >&2; return 2 ;;
  esac
}

# --- install -----------------------------------------------------------------

install_skills() {
  local tool=${1:-all} from=${2:-}
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
    cp -R "$from"/* "$target"/
    echo "factory: skills → $target"
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
  local compile="" test="" architecture=""
  if [ -f gradlew ] || [ -f build.gradle ] || [ -f build.gradle.kts ]; then
    compile="./gradlew testClasses"; test="./gradlew test"; architecture="./gradlew test-architecture"
  elif [ -f pom.xml ]; then
    compile="./mvnw test-compile"; test="./mvnw test"; architecture="./mvnw -Dtest=*ArchitectureTest test"
  elif ls ./*.sln ./*.csproj >/dev/null 2>&1; then
    compile="dotnet build"; test="dotnet test"; architecture="dotnet test --filter FullyQualifiedName~Architecture"
  fi
  if [ -n "$conventions" ]; then
    local stated
    stated=$(grep -oE '`[^`]*(gradlew|mvnw|dotnet)[^`]*`' "$conventions" | tr -d '`' | grep -iE "arch" | head -1)
    [ -n "$stated" ] && architecture="$stated"
    echo "factory: read build facts from $conventions"
  fi
  python3 - "$compile" "$test" "$architecture" <<'PYEOF'
import sys
compile_, test, architecture = sys.argv[1:4]
path = ".agents/factory/factory.profile.yaml"
lines = open(path).read().splitlines()
values = {"compile": compile_, "test": test, "e2eTest": test, "architecture": architecture}
out = []
for line in lines:
    key = line.split(":", 1)[0].strip()
    if key in values and values[key] and "{{" in line:
        out.append(f"{key}: {values[key]}")
    elif "{{" in line and key in ("filterFlag", "filterFormat"):
        out.append(line.replace("{{FILTER_FLAG}}", "--tests").replace(
            "{{FILTER_FORMAT}}", '"{class}.{method}"'))
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

prompt_for() {                              # prompt_for <stage> <story>
  local stage=$1 story=$2
  printf '%s' "Apply the stage-$stage skill for backlog story $story. \
Read only the story and the files the skill names as its input, and write its output file under \
$TASKS/$story/. Do the stage yourself in this session; do not delegate it. Do not run other stages."
}

gate() {                                    # gate <stage> <story>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh install'" >&2; return 2; }
  python3 "$GATE" --story "$2" --stage "$1"
}

run_story() {
  local story=$1 tool=$2 from=${3:-plan} dry=${4:-}
  local started=0
  for stage in "${STAGES[@]}"; do
    [ "$stage" = "$from" ] && started=1
    [ "$started" = 1 ] || continue

    if [[ " ${GATED[*]} " == *" $stage "* ]] && [ "$stage" != "build" ] && [ "$stage" != "document" ]; then
      echo "── gate $stage"
      gate "$stage" "$story" || { echo "factory: gate '$stage' refused the story. Fix it before the stage runs." >&2; return 1; }
    fi

    echo "── stage $stage  (tool: $tool, fresh context)"
    if [ -n "$dry" ]; then
      echo "   would run: $(prompt_for "$stage" "$story")"
    else
      invoke "$tool" "$(prompt_for "$stage" "$story")" || {
        echo "factory: the tool exited non-zero during stage '$stage'." >&2; return 1; }
      [ -f "$TASKS/$story/$stage.md" ] || {
        echo "factory: stage '$stage' produced no $TASKS/$story/$stage.md — a stage is finished when its file exists." >&2
        return 1; }
    fi

    case "$stage" in
      build|document)
        echo "── gate $stage"
        [ -n "$dry" ] || gate "$stage" "$story" || {
          echo "factory: gate '$stage' failed after the stage. Re-run this stage with the gate output." >&2
          return 1; }
        ;;
    esac
  done
  echo "factory: story $story ran through $(IFS=,; echo "${STAGES[*]}")."
}

# --- main --------------------------------------------------------------------

[ $# -ge 1 ] || usage
command=$1; shift
story=""; tool=""; from="plan"; dry=""; source_dir=""

while [ $# -gt 0 ]; do
  case "$1" in
    --story) story=$2; shift 2 ;;
    --tool) tool=$2; shift 2 ;;
    --from) if [ "$command" = "install" ]; then source_dir=$2; else from=$2; fi; shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) usage ;;
  esac
done

case "$command" in
  install) install_skills "${tool:-all}" "$source_dir" ;;
  run)
    [ -n "$story" ] || usage
    [ -n "$tool" ] || tool=$(detect_tool)
    [ -n "$tool" ] || { echo "factory: no agent tool found on PATH." >&2; exit 2; }
    run_story "$story" "$tool" "$from" "$dry"
    ;;
  *) usage ;;
esac
