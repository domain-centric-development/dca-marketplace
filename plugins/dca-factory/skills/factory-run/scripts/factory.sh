#!/usr/bin/env bash
# The factory outside the session: one process per stage, so every stage starts with a fresh
# context and reads only its story and its predecessor's file. Same stages, same gate, same
# files as running the skills inside a session — this only changes who holds the context.
#
#   factory.sh install [--tool claude|codex|opencode|all] [--from <skill folder>] [--copy]
#   factory.sh run --story <id> [--tool <tool>] [--from <stage>] [--dry-run]
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
  # Which model, which effort, which sandbox a tool runs with is the tool's configuration and not
  # the pipeline's — but a default that does not work stops the run, so each adapter takes extra
  # flags from the environment: FACTORY_CLAUDE_ARGS, FACTORY_CODEX_ARGS, FACTORY_OPENCODE_ARGS.
  # Example: FACTORY_OPENCODE_ARGS="--model <provider>/<model>" where the default provider is not
  # authenticated. The pipeline never chooses a model; it only stops standing in the way of one.
  # One seam, for two honest purposes: a project whose tool is none of the three can plug it in,
  # and the runner's own loop can be exercised without a model — which is the only way a defect in
  # the loop is found by a test rather than by a wasted run.
  if [ -n "${FACTORY_TOOL_CMD:-}" ]; then
    FACTORY_STAGE="${stage_in_flight:-}" FACTORY_PROMPT="$prompt" sh -c "$FACTORY_TOOL_CMD"
    return $?
  fi
  case "$tool" in
    claude)   claude -p "$prompt" --permission-mode acceptEdits \
                --allowed-tools "Read,Write,Edit,Glob,Grep,Skill,$(allowed_commands)" \
                ${FACTORY_CLAUDE_ARGS:+$FACTORY_CLAUDE_ARGS} ;;
    codex)    codex exec -s workspace-write \
                -c sandbox_workspace_write.network_access=true \
                ${FACTORY_CODEX_ARGS:+$FACTORY_CODEX_ARGS} "$prompt" ;;
    opencode) opencode run ${FACTORY_OPENCODE_ARGS:+$FACTORY_OPENCODE_ARGS} "$prompt" ;;
    *)        echo "factory: unknown tool '$tool'" >&2; return 2 ;;
  esac
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
  local source_abs; source_abs=$(cd "$from" && pwd)
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
      mkdir -p "$target"
      cp -R "$source_abs"/* "$target"/
      echo "factory: skills → $target (copied; re-run install after a skill is added)"
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
    elif [ -L "$target" ] || [ ! -e "$target" ] || only_links_into "$target" "$source_abs"; then
      rm -rf "$target"
      mkdir -p "$(dirname "$target")"
      ln -s "$source_abs" "$target"
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
    compile="dotnet build"; test="dotnet test"; architecture="dotnet test --filter FullyQualifiedName~Architecture"
    filter_flag="--filter"; filter_format='"FullyQualifiedName~{class}.{method}"'
    # Without a project argument `dotnet test` runs every test project of the solution, so this
    # command's scope is the whole project. A Gradle or Maven task is *not* that — `./gradlew test`
    # runs one source set — which is why this is declared here rather than guessed by the gate.
    covers="**"
  fi
  if [ -n "$conventions" ]; then
    local stated
    stated=$(grep -oE '`[^`]*(gradlew|mvnw|dotnet)[^`]*`' "$conventions" | tr -d '`' | grep -iE "arch" | head -1)
    [ -n "$stated" ] && architecture="$stated"
    echo "factory: read build facts from $conventions"
  fi
  python3 - "$compile" "$test" "$architecture" "$filter_flag" "$filter_format" "$covers" <<'PYEOF'
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
  local report="$TASKS/$2/.gate-$1.txt" journal="$TASKS/$2/.verify"
  mkdir -p "$TASKS/$2" "$journal"
  python3 "$GATE" --story "$2" --stage "$1" 2>&1 | tee "$report"
  local code=${PIPESTATUS[0]}
  # Every gate run is kept for the observer, with its verdict; only a *refusal* is kept where the
  # next stage reads it. A run that has to be reconstructed afterwards from what a stage claimed is
  # exactly the evidence the gate exists to replace.
  cp "$report" "$journal/gate-$1.$(date -u +%H%M%S).txt"
  printf '%s\tgate\t%s\texit=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$code" >> "$journal/journal.tsv"
  [ "$code" = 0 ] && rm -f "$report"
  return "$code"
}

# What the working tree looks like right now, so a later stage's claim about what it changed can be
# checked rather than believed. Cheap: one porcelain listing plus a hash per file git reports.
snapshot() {                                # snapshot <story> <label>
  local journal="$TASKS/$1/.verify" file
  mkdir -p "$journal"
  {
    # -uall: without it a newly added directory is listed as one entry and every file in it is
    # missing from the snapshot — so a test added by this run, and edited afterwards, would look
    # untouched. `--porcelain` also quotes unusual names, hence the -z form and the NUL split.
    git -c core.fileMode=false status --porcelain -z -uall 2>/dev/null \
      | tr '\0' '\n' | sed 's/^...//' | while read -r file; do
      [ -n "$file" ] && [ -f "$file" ] \
        && printf '%s  %s\n' "$(shasum -a 256 "$file" 2>/dev/null | cut -d" " -f1)" "$file"
    done
  } > "$journal/tree-$2.txt" 2>/dev/null || true
}

run_story() {
  local story=$1 tool=$2 from=${3:-plan} dry=${4:-}
  local started=0 ran=""
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
      # Never `started` — that name is the loop's "have we reached --from yet" flag, and
      # overwriting it skips every later stage while the run still reports success.
      local stage_started; stage_started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      snapshot "$story" "before-$stage"
      printf '%s\tstage-start\t%s\ttool=%s\n' "$stage_started" "$stage" "$tool" >> "$TASKS/$story/.verify/journal.tsv"
      stage_in_flight="$stage" invoke "$tool" "$(prompt_for "$stage" "$story")" || {
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
      if grep -q '^## needs-human' "$artefact"; then
        echo "factory: stage '$stage' ends with a needs-human section — the run stops here." >&2
        echo "factory:   read $artefact and decide; the stages after it were not run." >&2
        return 1
      fi
    fi

    if [[ " ${POST_GATED[*]} " == *" $stage "* ]]; then
      echo "── gate $stage"
      [ -n "$dry" ] || gate "$stage" "$story" || {
        echo "factory: gate '$stage' failed after the stage. Re-run this stage with the gate output." >&2
        return 1; }
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
