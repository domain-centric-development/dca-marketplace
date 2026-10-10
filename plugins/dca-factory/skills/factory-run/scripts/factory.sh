#!/usr/bin/env bash
# The factory outside the session: one process per stage, so every stage starts with a fresh
# context and reads only its story and its predecessor's file. Same stages, same gate, same
# files as running the skills inside a session — this only changes who holds the context.
#
#   factory.sh setup [--tool claude|codex|opencode|all|none] [--copy|--link] [--from <skill folder>]
#                    installs the pipeline where it is not; on an installed project it reports only.
#                    Skills are copied when the source is a plugin cache, linked when it is a checkout
#   factory.sh setup --check                 what detection finds against the profile (read-only)
#   factory.sh setup --write [--replace <key>]   adds the detected keys the profile lacks
#   factory.sh backlog [--check]             every story's state and the next one; --check the backlog
#   factory.sh run [--story <id>] [--tool <tool>] [--from <stage>] [--watch] [--interval <s>]
#                  [--max-stages <n>] [--story-budget <tokens>] [--separate-stages] [--parallel <n>] [--dry-run]
#                    one story from where its files say (--from names the stage and starts a new
#                    count of rounds), or without --story the whole backlog in the schedule's order;
#                    every story in a worktree of its own, integrated into the checkout's branch when
#                    every gate passed; --parallel runs up to <n> stories at once
#   factory.sh status [--story <id>] [--usage] [--refusals] [--brief]   what runs, what waits, every story, the cost; --refusals: form against substance
#   factory.sh decisions [--story <id>]      the decision inbox
#   factory.sh follow [--story <id>] [--process <name>] [--once [--lines <n>]] [--all] [--format text|json]
#                    what the stage in flight does, one line per tool call, as it happens; --process one
#                    process (builder, verifier, review-ddd, …), --all every process of a story; starts nothing
#   factory.sh discover --check <topic>      the discovery report of one topic against its contract
#   factory.sh discover --list [--format text|md|json]   every topic, its proposed epics and which are epics
#   factory.sh help [--format text|md|json]  the factory explained: the flow and where this project stands,
#                                            every command in its agent and its shell form, the marks, the files
#   factory.sh update [--from <skill folder>] [--copy|--link] [--adopt <skill>,…|all]   the newest pipeline found,
#                    same tools; --adopt takes over a copy of a method skill the install did not make; the mode
#                                            the project has, or the one named
#   factory.sh verify --story <id> | --fixtures [--group <g>] [--jobs <n>]   observe a delivered story | check the machinery
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

# The stages are the gate's table, read through the cli once Python is found (below): STAGES, the run order;
# STEPS, what comes after it; BUILDER_STAGES and VERIFIER_STAGES, what each shared process carries. And which
# gate runs when: `plan` is the only gate that can run *before* its stage (PRE_GATED): it reads the backlog alone.
# Every other gate judges the file its stage writes — `tests.md`, the implementation, `document.md` — so it runs
# after it (POST_GATED). Gating `test` up front would refuse every story for the missing file its own stage is
# about to write.
GATE=".agents/factory/story-gate.py"
GATE_REL=$GATE
# What shows and coordinates, beside the gate that decides: the file next to this script (the project's
# copy beside the project's runner, the plugin's beside the plugin's). It imports the gate beside *it*,
# and it is the one reader the runner asks a project file's content from — the profile, a verdict, a
# needs-human section, an open record — so the runner parses nothing the gate parses.
CLI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/factory-cli.py"
cli() { "$PY" "$CLI" "$@"; }
RUNS=""                                      # the run folder — resolved below through the cli, from the profile
STOP_FILE=""                                 # <run folder's parent>/stop: exists → a backlog run stops before its next story
MAX_STAGES=""                                # --max-stages: the cap on them, empty for none
STORY_BUDGET=""                              # --story-budget: tokens one story may use in total
# Shared stages are the default: plan to tidy in one builder process, judge and document in one verifier
# process (never the builder's). The profile's `stages: separate` starts one process per stage instead;
# for one run, --separate-stages does the same, and FACTORY_SHARED_BUILDER / FACTORY_SHARED_VERIFIER set
# to 0 or 1 decide each half. --shared-builder and --shared-verifier are accepted and change nothing.
SHARED_BUILDER="${FACTORY_SHARED_BUILDER:-}"
case "$(printf '%s' "$SHARED_BUILDER" | tr '[:upper:]' '[:lower:]')" in 0|off|no|false) SHARED_BUILDER="" ;; esac
SHARED_VERIFIER="${FACTORY_SHARED_VERIFIER:-}"
case "$(printf '%s' "$SHARED_VERIFIER" | tr '[:upper:]' '[:lower:]')" in 0|off|no|false) SHARED_VERIFIER="" ;; esac
SHARED_BUILDER_SET="${FACTORY_SHARED_BUILDER:+set}"
SHARED_VERIFIER_SET="${FACTORY_SHARED_VERIFIER:+set}"
SEPARATE_STAGES=""                           # --separate-stages: one process per stage for this run

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
# The stage table and where the run artefacts go, in one call: the gate's stages as bash arrays — names the cli
# checks to be plain words, never read from a file — and the profile's `runs:` or its default, quoted, read through
# the cli like every other place: the runner hard-codes no path of the project's and no stage. Without a cli beside
# the runner there are no stages, and `run` stops before its first one (the cli pair's check names the update).
# The stop file lives beside the runs.
eval "$(cli --stages --shell --place runs 2>/dev/null)"
RUNS=${PLACE_RUNS:-.dca-factory/runs}
STOP_FILE="$(dirname "$RUNS")/stop"
# Every story runs in a worktree of its own (WP-92): the runner works from the main checkout, HOME_DIR, and
# enters a story's worktree for its stages. What is state stays here — the run folder is named absolutely
# while a story works in its worktree, and the stop file and the integration lock are this checkout's.
# Git Bash names the directory as Windows does (`pwd -W`), so the Python beside it reads the same path.
HOME_DIR=${FACTORY_HOME:-$(pwd -W 2>/dev/null || pwd -P)}
RUNS_REL=$RUNS
case "$RUNS" in
  /*|?:*) STOP_FILE="$(dirname "$RUNS")/stop"; LOCK_DIR="$(dirname "$RUNS")/integrate.lock" ;;   # read from a worktree
  *)      STOP_FILE="$HOME_DIR/$STOP_FILE"; LOCK_DIR="$HOME_DIR/$(dirname "$RUNS")/integrate.lock" ;;
esac
PARALLEL="${FACTORY_PARALLEL:-}"             # --parallel / FACTORY_PARALLEL / the profile's `parallel:`; 1 by default
evidence_rel() {                            # the evidence folder, relative to the main checkout
  local parent; parent=$(dirname "$RUNS_REL"); [ "$parent" = . ] && parent=.dca-factory
  printf '%s/evidence' "$parent"
}

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
# The gate's entry point names neither: they live in the package beside it (dca_factory/contract.py).
gate_field() {                              # gate_field <file> <VERSION|CONTRACT>
  [ -f "$1" ] || return 1
  local file=$1
  grep -q "^$2 = " "$file" || file="$(dirname "$1")/dca_factory/contract.py"
  [ -f "$file" ] || return 1
  sed -n "s/^$2 = *//p" "$file" | head -1 | tr -d '"' | tr -d "'"
}

#: What the project records about the pipeline it installed. Three facts, no paths and no
#: timestamps, so the file belongs in the repository: a reviewer and a CI run can see which version
#: of the pipeline governs this project, and every checkout reads the same thing. Where the plugin
#: sits is a property of a machine, not of the project, so it is resolved when it is needed instead
#: of being frozen here — an absolute path written on one machine is wrong on every other one.
STAMP=".agents/factory/gate.installed"

# The files the install puts into .agents/factory/, in the stamp's order. Their hash is the stamp's `sha256:` line:
# what was installed, so a runner can tell the pipeline it is about to trust from one a stage, a hand or a merge
# changed since. The runner (dca_factory/runner.py, the same digest) takes it at its start and compares before every
# gate it runs; a stage that rewrote the gate through a link is stopped at the next gate, whatever tool it ran in.
# The modules in the C locale's order, as Python sorts them.
# A name ending in `/` is the package: every module in it, so a module added or removed changes the hash too.
PIPELINE_FILES="story-gate.py factory-cli.py observe.py factory.sh dca_factory/"
pipeline_hash() {                           # pipeline_hash [<folder>] — one SHA-256 over PIPELINE_FILES
  local dir=${1:-$HOME_DIR/.agents/factory} hash file module LC_ALL=C
  hash=$(hasher); [ "$hash" = none ] && return 1
  for file in $PIPELINE_FILES; do
    case $file in
      */) if [ -d "$dir/$file" ]; then
            for module in "$dir/$file"*.py; do
              [ -f "$module" ] && printf '%s  %s\n' "$($hash "$module" | cut -d" " -f1)" "$file${module##*/}"
            done
          else printf 'missing  %s\n' "$file"; fi ;;
      *)  if [ -f "$dir/$file" ]; then printf '%s  %s\n' "$($hash "$dir/$file" | cut -d" " -f1)" "$file"
          else printf 'missing  %s\n' "$file"; fi ;;
    esac
  done | $hash | cut -d" " -f1
}

# The pipeline's own copy of the gate, for comparison against the project's copy. In order: an
# explicit override, the checkout this script is running from (the usual case — the runner is
# started out of the plugin), and the skill links an install may have left. When none of them
# resolves there is simply nothing to compare, which is a silence, not a finding.
plugin_gate() {
  local skills; skills=$(plugin_skills) || return 1
  echo "$skills/factory-run/scripts/story-gate.py"
}

# The pipeline's skill folder this project can update from, the newest one found: an explicit
# FACTORY_PLUGIN_DIR, the checkout this script runs from, the pipeline the skill folders the install
# linked lead to, and Claude Code's plugin cache. "Newest" decides, not the order. The project's own
# copies are never a candidate: an update replaces them, so they are no source — from themselves they
# would stay what they are, and on a version tie they would shadow the cache the copies came from.
plugin_skills() {
  local candidate dir best="" best_version="" version root; root=$(pwd -P)
  for candidate in \
      "${FACTORY_PLUGIN_DIR:-}" \
      "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)" \
      ${TOOL_SKILL_DIRS[@]+"${TOOL_SKILL_DIRS[@]}"} \
      "$HOME"/.claude/plugins/cache/*/dca-factory/*/skills; do
    [ -n "$candidate" ] && [ -f "$candidate/factory-run/scripts/story-gate.py" ] || continue
    # through the skill, not the folder: a project's skill folder holds one link per skill, so the
    # folder resolves to the project itself while its `factory-run` resolves to where the pipeline is
    dir=$(dirname "$(cd "$candidate/factory-run" && pwd -P)")
    case "$candidate" in .*/skills) case "$dir/" in "$root"/*) continue ;; esac ;; esac
    version=$(gate_field "$dir/factory-run/scripts/story-gate.py" VERSION)
    if [ -z "$best" ] || [ "$(printf '%s\n%s\n' "$best_version" "$version" | sort -V | tail -1)" != "$best_version" ]; then
      best=$dir; best_version=$version
    fi
  done
  [ -n "$best" ] && echo "$best"
}

# The list an install keeps beside the skills it placed (`<target>/.dca-factory-skills`): two header
# lines — the mode (`link` or `copy`) and where the source was (`cache` or `checkout`) — then one
# skill name per line. Committed with the project in both modes, so a clone and an update read the
# mode and the install's own entries from it instead of guessing from what the directory holds. An
# entry the list does not name is the project's, whatever its name. A list from before the header
# (names only) is read as a copy install.
MANIFEST_NAME=".dca-factory-skills"
# The pipeline's own skill names, for the one guess that remains: an install from before the list.
PIPELINE_SKILLS="factory-backlog factory-decisions factory-help factory-run factory-setup factory-status factory-update factory-verify stage-build stage-document stage-integrate stage-judge stage-plan stage-test stage-tidy"
manifest_field() {                          # manifest_field <target> <mode|source>
  sed -n "s/^$2:[[:space:]]*//p" "$1/$MANIFEST_NAME" 2>/dev/null | head -1
}
manifest_names() {                          # manifest_names <target>
  grep -v ':' "$1/$MANIFEST_NAME" 2>/dev/null || true
}
manifest_has() {                            # manifest_has <target> <name>
  manifest_names "$1" | grep -qx "$2"
}
manifest_start() {                          # manifest_start <target> <mode> <source kind> — begins <list>.new
  printf 'mode: %s\nsource: %s\n' "$2" "$3" > "$1/$MANIFEST_NAME.new"
}
adopts() {                                  # adopts <name> — the person named it with --adopt (or all)
  case " ${ADOPT:-} " in *" all "*|*" $1 "*) return 0 ;; esac
  return 1
}
manifest_add() {                            # manifest_add <target> <name> — into the list, once
  grep -qsx "$2" "$1/$MANIFEST_NAME" || {
    [ -f "$1/$MANIFEST_NAME" ] || printf 'mode: link\nsource: checkout\n' > "$1/$MANIFEST_NAME"
    echo "$2" >> "$1/$MANIFEST_NAME"; }
}
# Where a source lies: a plugin cache (`<cache>/<marketplace>/<plugin>/<version>/skills` — versioned,
# and a version is removed some time after an update, so a link into it goes stale) or a checkout
# (a clone of the marketplace, or FACTORY_PLUGIN_DIR — live, a developer's).
source_kind() {                             # source_kind <source_abs>
  if [ -n "${FACTORY_PLUGIN_DIR:-}" ] && [ "$(cd "$FACTORY_PLUGIN_DIR" 2>/dev/null && pwd -P)" = "$1" ]; then
    echo checkout; return
  fi
  case "$1" in */plugins/cache/*/*/*/skills) echo cache ;; *) echo checkout ;; esac
}

# How the project holds the skills for one tool: `link` (into a checkout or cache — live), `copy`
# (its own folders — pinned, committed with the project), or nothing for a tool it does not use.
# The list says it; without one (an install from before the list, or a clone that lost the folder)
# the pipeline's own names decide by majority — never one entry, which a project may own itself.
skills_mode() {                             # skills_mode <target dir>
  local target=$1 mode name links=0 dirs=0
  [ -L "$target" ] && { echo link; return; }
  mode=$(manifest_field "$target" mode)
  [ -n "$mode" ] && { echo "$mode"; return; }
  [ -f "$target/$MANIFEST_NAME" ] && { echo copy; return; }        # names only: the list before the header
  for name in $PIPELINE_SKILLS; do
    # a link whose target is gone is still a link: the update is what repairs it
    if [ -L "$target/$name" ]; then links=$((links + 1)); elif [ -d "$target/$name" ]; then dirs=$((dirs + 1)); fi
  done
  if [ "$links" -eq 0 ] && [ "$dirs" -eq 0 ]; then
    # Links are machine-local and kept out of git, so a fresh clone has none — the ignore rule is what
    # says the project used them, and `update` is how a clone gets them back.
    git check-ignore -q "$target/factory-run" 2>/dev/null && echo link || echo ""
  elif [ "$links" -ge "$dirs" ]; then
    echo link
  else
    echo copy
  fi
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
  # The project's own skills are what an update replaces, never where it comes from: linked onto
  # themselves they become loops, and a copy updated from itself stays what it was. A folder of links
  # (what an older runner hands over) names the pipeline through its factory-run link.
  local root; root=$(pwd -P)
  case "$src/" in "$root"/*) src=$(dirname "$(cd "$src/factory-run" && pwd -P)") ;; esac
  case "$src/" in
    "$root"/*) echo "factory: $src lies inside this project — update from the plugin's skills folder" \
                    "(--from <plugin>/skills, or FACTORY_PLUGIN_DIR); nothing was changed" >&2; return 2 ;;
  esac
  local newest="$src/factory-run/scripts/factory.sh" self
  self=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/$(basename "${BASH_SOURCE[0]}")
  if [ -z "${FACTORY_UPDATE_HANDED:-}" ] && [ -f "$newest" ] && [ "$self" != "$newest" ]; then
    FACTORY_UPDATE_HANDED=1 exec bash "$newest" update --from "$src" ${copy_mode:+--copy} ${LINK_MODE:+--link} \
      ${ADOPT:+--adopt "$ADOPT"}
  fi
  before=$(sed -n 's/^version:[[:space:]]*//p' "$STAMP" 2>/dev/null | head -1)
  before_contract=$(sed -n 's/^contract:[[:space:]]*//p' "$STAMP" 2>/dev/null | head -1)
  for tool in ${TOOL_NAMES[@]+"${TOOL_NAMES[@]}"}; do
    target=$(skill_dir_of "$tool")
    mode=$(skills_mode "$target")
    [ -n "$mode" ] || continue
    # the mode the project has — unless the person names the other one, which is how a project switches
    [ -n "$copy_mode" ] && mode=copy
    [ -n "${LINK_MODE:-}" ] && mode=link
    if [ "$mode" = copy ]; then
      install_project "$tool" "$src" 1
    else
      LINK_MODE=1 install_project "$tool" "$src" ""       # explicit: the mode stays, whatever the source
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
  declared=$(cli --get contract 2>/dev/null)
  if [ -n "$declared" ] && [ "$declared" != "$after_contract" ]; then
    echo "factory: the stack profile declares contract $declared — raise it to 'contract: $after_contract' once" >&2
    echo "factory:   the profile uses what that contract describes; the gate reads it as older until then." >&2
  fi
  # the layout before `project/` is not read by the new gate; the move is said here as well
  cli --schedule 2>/dev/null | sed -n 's/^layout: /factory: /p' >&2
  echo "factory: review and commit the changed files — the update commits nothing. 'factory.sh setup --check'"
  echo "factory:   names what the project gained since, as profile lines to confirm; the update writes none."
}

# A copied skill under a name the method plugins renamed: removed when it is byte for byte the newest
# version of its old plugin still on this machine (the plugin cache, or a checkout beside the pipeline)
# — nobody edited it — and kept and named otherwise, because then the project made it its own.
prune_renamed_copies() {                    # prune_renamed_copies <pipeline skill folder>
  local src=$1 target old new plugin copy candidate reference version best_version
  for target in ${TOOL_SKILL_DIRS[@]+"${TOOL_SKILL_DIRS[@]}"}; do
    [ -d "$target" ] && [ ! -L "$target" ] || continue
    while read -r old new plugin; do
      copy="$target/$old"
      # A link under the old name whose folder is gone points at nothing: the rename moved the folder,
      # and the new name is linked by the install. A link that still resolves is the project's own choice.
      if [ -L "$copy" ] && [ ! -e "$copy" ]; then
        rm -f "$copy"
        [ -f "$target/.dca-factory-skills" ] && { grep -vx "$old" "$target/.dca-factory-skills" > "$target/.dca-factory-skills.new"; mv -f "$target/.dca-factory-skills.new" "$target/.dca-factory-skills"; }
        echo "factory: removed the link $copy — renamed to $new, and its folder is gone"
        continue
      fi
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

# What the runner knows of a tool is a row of the cli's tool table (`TOOL_*`, read at the start); a value of one
# row by its tool: `tool_field TOOL_SKILLS claude` → .claude/skills.
tool_field() {                              # tool_field <TOOL_* table> <tool>
  local table=" ${!1:-} " entry
  entry=${table#* "$2":}
  [ "$entry" != "$table" ] && printf '%s' "${entry%% *}"
}

detect_tool() {
  for candidate in ${TOOL_NAMES[@]+"${TOOL_NAMES[@]}"}; do
    command -v "$candidate" >/dev/null 2>&1 && { echo "$candidate"; return; }
  done
  echo ""
}

# A stage process sees the project and nothing else: not the person's own skills, plugins or MCP
# servers, and not a second copy of this pipeline from an installed plugin — which one a stage would
# pick is chance, and a colleague with other plugins would get another pipeline. It also starts
# smaller: the built-in tools no stage uses cost context on every turn. The tool list is the same
# for every stage, and nothing in the system prompt changes between stages, so from the second
# stage on the tool's prompt cache serves the prefix instead of writing it again.
# FACTORY_ISOLATION=off runs a stage with the tool's full setup, for a run that needs something the
# project does not carry; the run says so.
isolated() { [ "${FACTORY_ISOLATION:-on}" != off ]; }

# The craft a profile names — carrier.<stage>, review.<perspective>, knowledge — has to be in the
# project's own skill directory, because an isolated stage sees nothing else. Checked before the
# first invocation, so a missing carrier stops the run instead of every stage quietly falling back.
skill_dir_of() { tool_field TOOL_SKILLS "$1"; }
is_plugin_dir() { [[ " ${TOOL_PLUGIN_DIRS[*]:-} " == *" $1 "* ]]; }   # is_plugin_dir <skill folder>
named_carriers() { cli --carriers 2>/dev/null; }
# Skills the method plugins renamed: <old> <new> <the plugin that shipped the old one>. A profile that
# still names an old one would run yesterday's copy without a word, so the run stops on it, and
# `update` removes a copy under the old name that nobody edited.
RENAMED_SKILLS="dca-review dca-audit dca-core
review-domain review-ddd dca-core
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
  local key value new_key new_value
  cli --carrier-lines 2>/dev/null \
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

# The tool, before any stage is paid for: its binary is asked once whether it knows every flag its record passes
# (`cli --tool-probe`) — a flag a stage needs and the binary lacks stops the run; an isolation flag it lacks is left
# out and named, as is a run without isolation or OpenCode without the pipeline's permission block.
check_tool() {                              # check_tool <tool>
  isolated || echo "factory: FACTORY_ISOLATION=off — stages run with the tool's full setup, user plugins included" >&2
  [ -n "$1" ] && [ -n "$(tool_field TOOL_SKILLS "$1")" ] && [ -z "${FACTORY_TOOL_CMD:-}" ] || return 0
  local out code=0
  out=$(cli --tool-probe "$1" 2>/dev/null) || code=$?
  if [ "$code" = 1 ]; then
    printf 'factory: %s\n' "$out" >&2
    echo "factory:   nothing was started — update the tool, or run with another (--tool)." >&2
    return 2
  fi
  isolated && printf '%s\n' "$out" | sed -n 's/^\([a-z]*\): no /factory: \1 knows no /p' >&2
  [ "$1" = opencode ] && [ "${FACTORY_OPENCODE_PERMISSIONS:-on}" = off ] && [ -z "${OPENCODE_CONFIG_CONTENT:-}" ] \
    && echo "factory: FACTORY_OPENCODE_PERMISSIONS=off — OpenCode runs the stages with its own permissions" >&2
  return 0
}

# The profile's contract and model keys, before any stage is paid for: a run started --from a later
# stage has no plan gate in front of it, and a stage run on the wrong model is spent money.
check_contract_first() {
  [ -f "$GATE" ] || return 0
  # The gate and the cli are two entry points of one package: without the package beside the gate, or without the
  # cli, nothing runs — `update` puts all three there.
  if [ ! -d "$(dirname "$GATE")/dca_factory" ]; then
    echo "factory: no dca_factory/ beside the gate — 'factory.sh update' puts it there. Nothing was started." >&2
    return 2
  fi
  if [ ! -f .agents/factory/factory-cli.py ]; then
    echo "factory: no factory-cli.py beside the gate — 'factory.sh update' puts it there. Nothing was started." >&2
    return 2
  fi
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

# The model a local tool runs with, for the context check above: the -m/--model in its extra flags.
model_flag() {                              # model_flag <tool>
  local name args; name=$(tool_field TOOL_ARGS_ENV "$1"); [ -n "$name" ] && args=${!name:-}
  # -E: BSD sed (macOS) has no `\|` in a basic expression, so the alternation is written extended
  printf '%s\n' "${args:-}" | sed -n -E 's/.*(-m|--model)[ =]([^ ]*).*/\2/p' | head -1
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
  local target=$1 dir plugin
  for dir in $2 $3; do
    case "$target" in "$dir"/*) return 0 ;; esac
    # Another version of the same plugin in a plugin cache (<cache>/<marketplace>/<plugin>/<version>/skills)
    # is the install's too: an update from a newer version replaces it, it is not the project's own.
    plugin=$(basename "$(dirname "$dir")")
    case "$dir" in */plugins/cache/*/*/*/skills) plugin=$(basename "$(dirname "$(dirname "$dir")")") ;; esac
    case "$target" in */plugins/cache/*/"$plugin"/*/skills/*) return 0 ;; esac
    # The same plugin in a checkout elsewhere (`<clone>/plugins/<plugin>/skills`): the install's as well,
    # so an update moves a link between a checkout and a cache instead of keeping it as the project's.
    case "$target" in */"$plugin"/skills/*) return 0 ;; esac
  done
  return 1
}

# Whether an entry of a skill directory is the install's to replace: named in the install's list
# (a link — or a copy, when the list says the project held copies and is switching), or, from before
# the list, a link into a source the install uses. A folder the list does not name is the project's,
# and so is a link it made itself, whatever their names.
ours_entry() {                              # ours_entry <target> <name> <source> <method dirs>
  local entry="$1/$2"
  if manifest_has "$1" "$2"; then
    [ -L "$entry" ] && return 0
    [ "$(manifest_field "$1" mode)" = copy ] && [ -d "$entry" ] && return 0
    [ -z "$(manifest_field "$1" mode)" ] && [ -d "$entry" ] && return 0     # the list before the header
    return 1
  fi
  [ -L "$entry" ] && ours "$(readlink "$entry")" "$3" "$4"
}

# The links are machine-local and stay out of git — one line per link, never the folder, so the
# list beside them and `.claude/settings.json` are committed. Copies are the project's: the lines go.
write_skill_ignores() {                     # write_skill_ignores <target> <mode>
  local target=$1 mode=$2 line names want="" out="" folder_line=0 changed=0
  names=$(manifest_names "$target")
  if [ "$mode" = link ]; then
    if [ -L "$target" ]; then want="$target"; else want=$(printf '%s\n' $names | sed "s|^|$target/|"); fi
  fi
  if [ -f .gitignore ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in
        "$target"|"$target/")
          # a folder-wide line hides the list too; it is replaced by one line per link, and named
          [ -L "$target" ] && [ "$mode" = link ] || { folder_line=1; changed=1; continue; } ;;
        "$target"/*)
          { [ -L "$target" ] || printf '%s\n' $names | grep -qx "${line#"$target"/}"; } && { changed=1; continue; } ;;
      esac
      out="$out$line
"
    done < .gitignore
  fi
  for line in $want; do
    printf '%s' "$out" | grep -qx "$line" || { out="$out$line
"; changed=1; }
  done
  [ "$changed" = 1 ] || return 0
  printf '%s' "$out" > .gitignore.new && mv -f .gitignore.new .gitignore
  if [ "$mode" = link ]; then
    echo "factory: .gitignore keeps the skill links out of git, one line per link$([ "$folder_line" = 1 ] && echo " (the folder-wide line is replaced, so the list beside the links is committed)")"
  else
    echo "factory: .gitignore no longer ignores the skills under $target — they are copies, committed with the project"
  fi
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

only_links_into() {                         # only_links_into <dir> <source> [<method dirs>]
  local dir=$1 source_abs=$2 method_dirs=${3:-} entry
  [ -d "$dir" ] || return 1
  for entry in "$dir"/* "$dir"/.[!.]*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    [ "$(basename "$entry")" = "$MANIFEST_NAME" ] && continue
    [ -L "$entry" ] || return 1
    ours "$(readlink "$entry")" "$source_abs" "$method_dirs" || return 1
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
  local ours_copy
  for name in $(named_carriers); do
    # A copy this install made (in its list) is refreshed; any other skill of that name is the project's.
    ours_copy=""
    [ -n "$copy_mode" ] && manifest_has "$target" "$name" && ours_copy=1
    # A link into this pipeline or a method plugin — any version of it — is the install's to refresh.
    if [ -f "$target/$name/SKILL.md" ] && ! { [ -L "$target/$name" ] && ! [ -e "$target/$name" ]; } \
       && [ -z "$ours_copy" ] && ! ours_entry "$target" "$name" "$source_abs" "$method_dirs"; then
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
    rm -rf "${target:?}/$name"
    if [ -n "$copy_mode" ]; then
      cp -R "$found" "$target/$name"
    else
      ln -s "$found" "$target/$name"
    fi
    manifest_add "$target" "$name"
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
    all)      targets=(${TOOL_SKILL_DIRS[@]+"${TOOL_SKILL_DIRS[@]}"}) ;;
    none)     targets=() ;;                  # only the project's files: gate, runner, hook, stamp
    *)        [ -n "$(skill_dir_of "$tool")" ] || usage; targets=("$(skill_dir_of "$tool")") ;;
  esac
  local source_abs; source_abs=$(cd "$from" && pwd)
  local copy_reason="" kind; kind=$(source_kind "$source_abs")
  # The profile first: the carriers it names are linked by this same run, so the first `run` does not
  # stop in the carrier check, and the per-skill branch for Claude's directory below sees them.
  must "create .agents/factory and .githooks" mkdir -p .agents/factory .githooks
  # An older layout first — the profile under .agents/factory/, project/backlog/, a decisions store, run
  # artefacts under tasks/ — so the profile below is found where it now lives and not written twice.
  cli --migrate-layout | grep -v "^migrate: nothing to move" | sed 's/^migrate: /factory: migrated /'
  [ -f "$PROFILE" ] || write_profile "$from"
  # The mode follows the source: a plugin cache holds one folder per version and drops a version some
  # time after an update, so a link into it goes stale for everyone who installed from the marketplace
  # — copies, pinned and committed. A checkout is a developer's: linked, so an edit is live. --copy and
  # --link name the other one.
  if [ -z "$copy_mode" ] && [ -z "${LINK_MODE:-}" ] && [ "$kind" = cache ]; then
    copy_mode=1; copy_reason=" — the source is a plugin cache, whose versions are removed after an update, so the install copies (--link links anyway)"
  fi
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
    # An older install linked the whole directory to the pipeline's folder. Through that link every
    # write below would land in the plugin's own folder — so the link goes first, and the directory
    # holds one entry per skill from here on.
    [ -L "$target" ] && must "replace the $target link" rm -f "$target"
    if [ -n "$copy_mode" ]; then
      # A copy looks like a skill of the project's own, so the install keeps a list of what it copied
      # (`.dca-factory-skills`): only those are its to replace, and one the pipeline no longer has is
      # removed. A folder of the project's own with a pipeline skill's name is left alone and named.
      must "create $target" mkdir -p "$target"
      local manifest="$target/$MANIFEST_NAME" previous="" skill name copied=0 kept=0 removed=0
      # The same set a link install gives this tool: for a tool without a plugin mechanism the craft
      # of the method plugins beside the pipeline, not only the carriers the profile already names.
      local copy_dirs="$source_abs"
      ! is_plugin_dir "$target" && copy_dirs=$(printf '%s\n%s' "$source_abs" "$(method_skill_dirs "$source_abs" | tr ' ' '\n')")
      if [ -f "$manifest" ]; then
        previous=$(manifest_names "$target")               # links too, when the project switches to copies
      else
        # A copy from before the list: a folder is taken as the pipeline's only when it is byte for
        # byte the source's skill — an edited one, or one that merely shares a name, is the project's.
        previous=$(printf '%s\n' "$copy_dirs" | while IFS= read -r dir; do
          for skill in "$dir"/*; do
            [ -d "$skill" ] && [ -d "$target/$(basename "$skill")" ] && [ ! -L "$target/$(basename "$skill")" ] \
              && diff -rq "$skill" "$target/$(basename "$skill")" >/dev/null 2>&1 && basename "$skill"
          done; done)
      fi
      manifest_start "$target" copy "$kind"
      while IFS= read -r skill; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        grep -qx "$name" "$manifest.new" && continue         # the pipeline's own wins a name clash
        if { [ -e "$target/$name" ] || [ -L "$target/$name" ]; } && ! printf '%s\n' "$previous" | grep -qx "$name" \
           && ! adopts "$name"; then
          echo "factory: kept the project's own $target/$name — the pipeline's $name was not copied" \
               "('factory.sh update --adopt $name' takes it over)" >&2
          kept=$((kept + 1))
          continue
        fi
        rm -rf "${target:?}/$name"
        must "copy $name into $target" cp -R "$skill" "$target/$name"
        echo "$name" >> "$manifest.new"
        copied=$((copied + 1))
      done < <(printf '%s\n' "$copy_dirs" | while IFS= read -r dir; do [ -n "$dir" ] && printf '%s\n' "$dir"/*; done)
      # Claude's directory gets the method plugins' skills only as carriers — but a project may hold copies of
      # them made by hand (`dca-new`, a bench base). Not the install's, so never replaced unasked: a copy that is
      # byte for byte the plugin's, or one the person names with --adopt, becomes the install's and follows the
      # plugin from then on; a different one is named. Only what the project already holds — nothing is added.
      if is_plugin_dir "$target"; then
        local method_dir
        for method_dir in $(method_skill_dirs "$source_abs"); do
          for skill in "$method_dir"/*; do
            [ -d "$skill" ] || continue
            name=$(basename "$skill")
            grep -qx "$name" "$manifest.new" && continue
            { [ -e "$target/$name" ] || [ -L "$target/$name" ]; } || continue
            if printf '%s\n' "$previous" | grep -qx "$name" || adopts "$name" \
               || diff -rq -x __pycache__ "$skill" "$target/$name" >/dev/null 2>&1; then
              rm -rf "${target:?}/$name"
              must "copy $name into $target" cp -R "$skill" "$target/$name"
              echo "$name" >> "$manifest.new"
              copied=$((copied + 1))
            else
              echo "factory: kept the project's own $target/$name — the method plugin beside the pipeline has another" \
                   "version; 'factory.sh update --adopt $name' takes it over and keeps it current" >&2
              kept=$((kept + 1))
            fi
          done
        done
      fi
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
    if [ -n "$method_dirs" ] && ! is_plugin_dir "$target"; then
      # A tool without a plugin mechanism finds *only* what is in this directory, so the craft the
      # profile names as a carrier (`carrier.build:`, `review.<perspective>:`) has to be here too —
      # otherwise the pipeline ports and the craft does not, and every stage falls back with a note.
      # Several sources cannot be one directory link, so these are per skill: an edited skill is
      # still live, but a *newly added* one needs another install, and that is said out loud.
      mkdir -p "$target"
      manifest_start "$target" link "$kind"
      # Never wipe the directory: a project may keep skills of its own in it, and an install that
      # deletes them while reporting success is the worst kind of helpfulness. Only links that
      # point into a source we install from are ours to replace, and a stale one — its skill gone
      # from the source — is pruned and named.
      local linked=0 kept=0 pruned=0 dir skill entry name
      for entry in "$target"/*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        if ours_entry "$target" "$(basename "$entry")" "$source_abs" "$method_dirs"; then
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
            if ! ours_entry "$target" "$name" "$source_abs" "$method_dirs"; then
              echo "factory: kept the project's own $target/$name — the pipeline's $name was not installed" >&2
              kept=$((kept + 1))
              continue
            fi
            rm -rf "${target:?}/$name"                       # a copy of ours, when the project switches to links
          fi
          ln -s "$skill" "$target/$name"
          echo "$name" >> "$target/$MANIFEST_NAME.new"
          linked=$((linked + 1))
        done
      done
      mv -f "$target/$MANIFEST_NAME.new" "$target/$MANIFEST_NAME"
      [ "$kept" -gt 0 ] && echo "factory: left $kept entry/entries in $target that are the project's own" >&2
      [ "$pruned" -gt 0 ] && echo "factory: pruned $pruned link(s) whose skill is gone from the source" >&2
      echo "factory: skills → $target ($linked linked: the pipeline plus the craft it names as carriers)"
      echo "factory:   per skill, because they come from several sources — 'factory.sh update' after a skill is added" >&2
    elif [ ! -e "$target" ] || only_links_into "$target" "$source_abs" "$method_dirs"; then
      # One link per skill, never the whole folder: through a folder link every skill a tool writes
      # into the project's directory would land in the plugin's own, and a carrier the profile names
      # could not sit beside the pipeline's skills. Per skill freezes the set: a skill added to the
      # pipeline later needs another install (or update), and the report says so.
      must "create $target" mkdir -p "$target"
      manifest_start "$target" link "$kind"
      local skill linked=0
      for skill in "$source_abs"/*; do
        [ -d "$skill" ] || continue
        ln -sfn "$skill" "$target/$(basename "$skill")"
        echo "$(basename "$skill")" >> "$target/$MANIFEST_NAME.new"
        linked=$((linked + 1))
      done
      mv -f "$target/$MANIFEST_NAME.new" "$target/$MANIFEST_NAME"
      echo "factory: skills → $target ($linked linked one by one, beside the carriers the profile names)"
      echo "factory:   'factory.sh update' after a skill is added to the pipeline" >&2
    else
      mkdir -p "$target"
      manifest_start "$target" link "$kind"
      local own_kept=0
      for skill in "$source_abs"/*; do
        [ -d "$skill" ] || continue
        # a link of ours is replaced; a folder or a link of the project's own with that name is its skill
        if { [ -e "$target/$(basename "$skill")" ] || [ -L "$target/$(basename "$skill")" ]; } \
           && ! ours_entry "$target" "$(basename "$skill")" "$source_abs" "$method_dirs"; then
          echo "factory: kept the project's own $target/$(basename "$skill") — the pipeline's $(basename "$skill") was not linked" >&2
          own_kept=$((own_kept + 1))
          continue
        fi
        rm -rf "${target:?}/$(basename "$skill")"
        ln -s "$skill" "$target/$(basename "$skill")"
        echo "$(basename "$skill")" >> "$target/$MANIFEST_NAME.new"
      done
      mv -f "$target/$MANIFEST_NAME.new" "$target/$MANIFEST_NAME"
      echo "factory: skills → $target (per skill: the directory holds skills of its own$([ "$own_kept" -gt 0 ] && echo "; $own_kept kept"))" >&2
      echo "factory:   'factory.sh update' after a skill is added to the source" >&2
    fi
  done
  for target in ${targets[@]+"${targets[@]}"}; do
    [ -d "$target" ] && [ ! -L "$target" ] || continue
    if is_plugin_dir "$target" || [ -n "$copy_mode" ]; then
      install_named_carriers "$target" "$source_abs" "$copy_mode"
    fi
  done
  for target in ${targets[@]+"${targets[@]}"}; do
    write_skill_ignores "$target" "$([ -n "$copy_mode" ] && echo copy || echo link)"
  done
  check_dca_setup "$from"
  # The package first, swapped in whole: a module the new release no longer has must not stay behind, and no
  # __pycache__ travels with it.
  rm -rf .agents/factory/.dca_factory.new
  must "create the package folder" mkdir -p .agents/factory/.dca_factory.new
  must "copy the package to .agents/factory/dca_factory" cp "$from/factory-run/scripts/dca_factory/"*.py .agents/factory/.dca_factory.new/
  rm -rf .agents/factory/dca_factory
  must "put the package in place" mv .agents/factory/.dca_factory.new .agents/factory/dca_factory
  must "copy the gate to $GATE" cp "$from/factory-run/scripts/story-gate.py" "$GATE"
  # What shows and coordinates, beside the gate that decides — the same release, checked before a run.
  must "copy the cli to .agents/factory/factory-cli.py" \
    cp "$from/factory-run/scripts/factory-cli.py" .agents/factory/factory-cli.py
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
  must "make the gate, the cli and the commit hook executable" chmod +x .githooks/pre-commit "$GATE" .agents/factory/factory-cli.py
  # Which pipeline this project is governed by — committed with the project, so it is the same
  # answer for everyone who checks it out. Deliberately no path and no timestamp: both describe the
  # machine that happened to run the install, and neither survives a second developer.
  {
    echo "plugin: dca-factory"
    echo "version: $(gate_field "$GATE" VERSION)"
    echo "contract: $(gate_field "$GATE" CONTRACT)"
    echo "files: $PIPELINE_FILES"
    echo "sha256: $(pipeline_hash .agents/factory)"
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
    printf '%s\n' "$(evidence_rel)/**/journal.tsv merge=union" >> .gitattributes
    echo "factory: .gitattributes merges the story journals by keeping both sides (merge=union)"
  fi
  # What a file manager drops into any folder it shows: no one's work, but a changed file to the gate's
  # files-listed check and the schedule's unclaimed-changes check — one would stop a run.
  local os_file os_added=""
  for os_file in .DS_Store Thumbs.db; do
    grep -qsxF "$os_file" .gitignore && continue
    [ -s .gitignore ] && [ -n "$(tail -c 1 .gitignore)" ] && printf '\n' >> .gitignore
    printf '%s\n' "$os_file" >> .gitignore
    os_added="$os_added $os_file"
  done
  [ -n "$os_added" ] && echo "factory: .gitignore keeps the files a file manager drops out of git:$os_added"
  write_agents_block
  if [ -n "$copy_mode" ]; then
    echo "factory: the skills are copies — commit .claude/.codex/.opencode skills with the project, and"
    echo "factory:   every clone delivers stories with this pipeline, without the marketplace ('factory.sh update' refreshes them)."
  elif [ -n "${targets[*]+x}" ] && [ "${#targets[@]}" -gt 0 ]; then
    echo "factory: the skill links point into $source_abs — kept out of git; a clone gets them"
    echo "factory:   with 'factory.sh update', or use --copy to commit the skills with the project."
    if [ "$kind" = cache ]; then
      echo "factory: that source is a plugin cache: its versions are removed some time after an update, and the" >&2
      echo "factory:   links then point nowhere until 'factory.sh update' — 'setup --copy' or 'update --copy' avoids it." >&2
    fi
  fi
  local target
  for target in ${targets[@]+"${targets[@]}"}; do
    is_plugin_dir "$target" || continue
    echo "factory: with the dca-factory plugin enabled, Claude Code lists these skills a second time as"
    echo "factory:   dca-factory:<skill>; the project's entry is the one a session and a runner stage use."
  done
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
PROFILE="dca-factory.profile.yaml"          # at the project root: the person's, committed; the one fixed path

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
CARRIERS="knowledge dca-knowledge governance
carrier.plan dca-modelling governance
carrier.build dca-modelling governance
carrier.guard dca-discipline governance
review.ddd review-ddd -
review.hexagonal review-hexagonal -
review.clean-code review-clean-code -
carrier.glossary ubiquitous-language -
carrier.domain context-map -
carrier.test e2e-testing -
carrier.discover product-discovery -"

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
KINDS = ("stack", "browser", "format", "governance", "stub", "integration")
#: Folders no detection looks into: build output, dependencies, tool state. Bounded in depth as well,
#: so a detection never walks a whole disk from a mistaken directory.
PRUNED = {".git", ".gradle", ".idea", ".vs", "build", "bin", "obj", "target", "dist", "out",
          "node_modules", ".venv", "venv", "__pycache__", ".agents", ".claude", ".codex", ".opencode", ".dca-factory"}
DEPTH = 4
#: The project description's default places — the gate's defaults, so no key is needed for them.
LOCATIONS = {"product": "project/product.md", "tech": "project/tech.md", "domain": "project/domain.md"}
#: Which check or stage a profile key switches on — what `--check` says beside a proposed line.
SWITCHES = {
    "knowledge": "every stage cites that catalog instead of recalling",
    "knowledge.read": "a stage reads these catalog nodes once before it writes code",
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
                values[key] = value.replace("{match_dir}", os.path.dirname(match or "") or ".") \
                    .replace("{match}", match or "").replace("{python}", python)
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
            # the three built-in perspectives always run; `reviews:` lists only those added to them
            if key.startswith("review.") and key not in ("review.ddd", "review.hexagonal", "review.clean-code"):
                values["reviews"] = ", ".join(filter(None, [values.get("reviews", ""), key[len("review."):]]))
    # What a stage reads once before it writes code, from the method's conventions file (its API node) — the file
    # is the source, the profile the factory's view of it; the runner reads only the profile.
    if values.get("knowledge") and conventions and os.path.isfile(conventions):
        found = re.search(r"^building_blocks_api:[^`\n]*`([^`\n]+)`", open(conventions, encoding="utf-8").read(), re.M)
        if found:
            values["knowledge.read"] = found.group(1)
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
    # Every scenario but a story's happy path runs at the integration level (contract 9), so a profile
    # without one stops the first plan. Nothing detects a decision, so it is named until it is taken.
    no_level = not any(k.startswith("test.") for k in list(profile) + list(values)) and "integration" not in profile
    # A browser suite outside `required:` never runs whole at a gate: each story runs its own tests, so a test that
    # depends on another's data or on the order passes every gate and fails the first full run.
    browser = str(profile.get("e2eTest", "")).strip()
    required = profile.get("required", "").split()
    browser_out = bool(browser) and browser != "none" and bool(required) and "e2eTest" not in required
    if rest[1:] == ["brief"]:
        if missing:
            print(f"factory: profile — detection finds {', '.join(k for k, _ in missing)} the profile does not declare "
                  "(factory.sh setup --check)")
        if no_level:
            print("factory: profile — no integration level (`test.<name>:`, or `integration: none`); the first "
                  "story's plan stops on it (/factory-setup)")
        if browser_out:
            print("factory: profile — the browser suite (e2eTest) is not in `required:`, so no gate runs it whole "
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
    if no_level:
        print("    " + paint("? integration level", "33") + "   none — every scenario but a story's happy path runs there")
        print(f"        {label('set one up')}   the method's integration-test capability (in a DCA project "
              f"`dca-add integration-tests`), then setup --write")
        print(f"        {label('or decide')}   `integration: none` in the profile — the scenarios then take the next level the project has\n")
    if browser_out:
        print("    " + paint("? e2eTest in required", "33") + "   the browser suite runs only story by story — no gate runs it whole")
        print(f"        {label('why')}   a test that depends on another's data or on the order passes every gate and fails the first full run")
        print(f"        {label('to add it')}   `required: {' '.join(required + ['e2eTest'])}` — where the suite starts the application itself;")
        print(f"        {label('')}   one that needs a system started by hand stays out and runs in CI\n")
    if not missing and not differing:
        print("    The profile declares everything detection finds.\n")
    print("─" * 72)
    if missing:
        print(f"  {paint('Next', '1')}   add the {len(missing)} missing key(s).")
        print(f"         {paint('agent'.ljust(10), '2')}   {paint('/factory-setup', '36')}")
        print(f"         {paint('shell'.ljust(10), '2')}   bash .agents/factory/factory.sh setup --write")
        print()
        raise SystemExit(1)
    if no_level:
        print(f"  {paint('Next', '1')}   decide the integration level.")
        print(f"         {paint('agent'.ljust(10), '2')}   {paint('/factory-setup', '36')}")
        print()
        raise SystemExit(0)
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
person names a task right away, run `python3 .agents/factory/factory-cli.py --status --brief`, show
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
managing session writes backlog and decision files only; a stage the runner started is that worker's own
session and writes its stage file. Every change — by a stage or by hand in a
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
    echo "factory: CLAUDE.md does not import AGENTS.md — a Claude Code before 2.1.277 (it reads AGENTS.md" >&2
    echo "factory:   natively since) gets the section through the SessionStart hook only; add '@AGENTS.md'" >&2
    echo "factory:   to CLAUDE.md if such a version should read the rest too." >&2
  fi
}

write_claude_permissions() {
  # Claude Code asks before running a command. In a non-interactive run there is nobody to ask,
  # so the gate cannot run and no stage can be verified — the tool then stops, correctly. These
  # two entries are the smallest allowlist that lets the pipeline verify itself; every other
  # command still asks.
  "$PY" - "$PY" $(cli --command-heads 2>/dev/null) <<'PYEOF'
import json, os, sys
python = sys.argv[1]
path = ".claude/settings.json"
os.makedirs(".claude", exist_ok=True)
settings = {}
if os.path.isfile(path):
    with open(path) as handle:
        settings = json.load(handle)
allow = settings.setdefault("permissions", {}).setdefault("allow", [])
wanted = [f"Bash({python} .agents/factory/story-gate.py:*)", f"Bash({python} .agents/factory/factory-cli.py:*)"]
# the commands the profile declares, read through the cli (sys.argv[2:]) — the runner parses no profile
for head in sys.argv[2:]:
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
hook_command = f"{python} .agents/factory/factory-cli.py --status --brief --session-start"
starts = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
for entry in starts:                         # an earlier install's hook through factory.sh or the gate is replaced
    entry["hooks"] = [h for h in entry.get("hooks", []) if "factory.sh status --brief" not in h.get("command", "")
                      and "story-gate.py --status --brief" not in h.get("command", "")]
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

# --shared-verifier: judge and document in ONE tool process — the document stage starts on what the judge
# has just read (the story, the diff, the plan, the glossary) instead of reading it again. The twin of
# --shared-builder, and never one process with it: the judge's independence from the builder is the point
# of the split; the verifier shares a context only with the stage after the verdict, which writes no code.
# The process runs the document gate itself; the runner reads the verdict, re-checks the document gate,
# and takes a `changes-requested` back to the build stage as it always does.

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
  local code=$?
  # One architecture command, checked: the profile's `architecture:` was copied from the conventions file at
  # setup, and nothing merges them — changed on one side, the gate and the method's review run different
  # commands. Named, never fixed: the person decides which is right.
  cli --drift ${brief:+--brief} || true
  return $code
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
  # A carrier line just written names a skill the stage processes must find in the project: put it there the
  # way `update` does — a profile that names a carrier the project does not hold stops the next run.
  local source_abs target mode
  source_abs=$(cd "$dir/../../.." 2>/dev/null && pwd)
  if [ -n "$source_abs" ] && [ -f "$source_abs/factory-run/scripts/story-gate.py" ]; then
    for target in ${TOOL_SKILL_DIRS[@]+"${TOOL_SKILL_DIRS[@]}"}; do
      [ -d "$target" ] && [ ! -L "$target" ] || continue
      mode=$(skills_mode "$target")
      if is_plugin_dir "$target" || [ "$mode" = copy ]; then
        install_named_carriers "$target" "$source_abs" "$([ "$mode" = copy ] && echo 1)"
      fi
    done
  fi
  [ -d .claude ] && write_claude_permissions
  return 0
}

# --- main --------------------------------------------------------------------

[ $# -ge 1 ] || usage
command=$1; shift
story=""; tool=""; from=""; dry=""; source_dir=""; copy_mode=""; LINK_MODE=""; watch=""; interval=60
setup_mode=""; replace_key=""; want_usage=""; want_refusals=""; want_brief=""; session_start=""; live=""; view=()

# The reading commands are the CLI's; the runner passes them on, so a project calls one script.
# Whether this run shares its stages: --separate-stages, else an explicit FACTORY_SHARED_* or flag per half,
# else the profile's `stages:` line, else shared.
resolve_stages() {
  if [ -n "$SEPARATE_STAGES" ]; then SHARED_BUILDER=""; SHARED_VERIFIER=""; return 0; fi
  local mode default
  mode=$(cli --get stages 2>/dev/null | awk '{print $1}')
  case "$mode" in
    ""|shared) default=1 ;;
    separate) default="" ;;
    *) echo "factory: the profile's stages: '$mode' is neither shared nor separate" >&2; return 1 ;;
  esac
  [ -n "$SHARED_BUILDER_SET" ] || SHARED_BUILDER=$default
  [ -n "$SHARED_VERIFIER_SET" ] || SHARED_VERIFIER=$default
  return 0
}

# The run itself is the package's runner (`dca_factory/runner.py`): the checks above passed, this process becomes
# it — the same process id, so the worker's name on the claim is the one the checks saw. It takes the claim, guards
# the pipeline's hash, runs the story or the backlog and gives the claim and the lock back however it ends.
run_python() {                              # run_python <runner flags…>
  exec env FACTORY_RUNNER_PYTHON="$PY" "$PY" "$CLI" --run "$@" ${dry:+--dry-run} \
    ${MAX_STAGES:+--max-stages "$MAX_STAGES"} ${STORY_BUDGET:+--story-budget "$STORY_BUDGET"} \
    --builder "$([ -n "$SHARED_BUILDER" ] && echo shared || echo separate)" \
    --verifier "$([ -n "$SHARED_VERIFIER" ] && echo shared || echo separate)" ${PARALLEL:+--parallel "$PARALLEL"}
}

read_command() {                            # read_command <cli flags…>
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh setup' from the plugin" >&2; exit 2; }
  exec "$PY" "$CLI" "$@"
}
gate_command() {                            # gate_command <gate flags…> — a check, not a view
  [ -f "$GATE" ] || { echo "factory: no gate at $GATE — run 'factory.sh setup' from the plugin" >&2; exit 2; }
  exec "$PY" "$GATE" "$@"
}
case "$command" in
  status)
    while [ $# -gt 0 ]; do
      case "$1" in
        --story) [ $# -ge 2 ] || usage; story=$2; shift 2 ;;
        --usage) want_usage=1; shift ;;
        --refusals) want_refusals=1; shift ;;
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
    [ -n "${want_refusals:-}" ] && { read_command --refusals ${story:+--story "$story"} ${view[@]+"${view[@]}"}; exit $?; }
    # Which pipeline this machine has is not the project's state: said with --live only, so the same
    # files give the same view everywhere.
    [ -n "${live:-}" ] && check_gate_freshness
    read_command --status ${story:+--story "$story"} ${view[@]+"${view[@]}"} ;;
  backlog)
    # The person's view of the backlog; the runner reads the schedule's lines from the gate itself.
    case "${1:-}" in
      --check) gate_command --check-backlog ;;
      *) read_command --status --part backlog "$@" ;;
    esac ;;
  decisions) read_command --list-decisions "$@" ;;
  follow) read_command --follow "$@" ;;
  discover)
    # The discovery report's check; the report itself is written in a session, by `factory-discover`.
    case "${1:-}" in
      --check) [ $# -eq 2 ] || usage; gate_command --check-discovery "$2" ;;
      --list) shift; read_command --discover-list "$@" ;;
      *) usage ;;
    esac ;;
  help)
    # The help works before the pipeline is installed too: then the plugin's gate explains it.
    exec "$PY" "$CLI" --help-view "$@" ;;
  check)
    case "${1:-}" in
      --parity) [ $# -eq 2 ] || usage; gate_command --parity "$2" ;;
      *) gate_command --change "$@" ;;
    esac ;;
  verify)
    case "${1:-}" in
      --story)
        [ $# -eq 2 ] || usage
        [ -f .agents/factory/observe.py ] || {
          echo "factory: no observer at .agents/factory/observe.py — 'factory.sh update' copies it there" >&2; exit 2; }
        exec "$PY" .agents/factory/observe.py --story "$2" ;;
      --fixtures)
        shift
        skills=$(plugin_skills) && [ -f "$skills/factory-verify/scripts/verify.py" ] || {
          echo "factory: no pipeline found whose fixtures could run — FACTORY_PLUGIN_DIR names one" >&2; exit 2; }
        echo "factory: the machinery of $skills"
        exec "$PY" "$skills/factory-verify/scripts/verify.py" "$@" ;;
      *) usage ;;
    esac ;;
esac

while [ $# -gt 0 ]; do
  case "$1" in
    --story) story=$2; shift 2 ;;
    --tool) tool=$2; shift 2 ;;
    --from) case "$command" in setup|update) source_dir=$2 ;; *) from=$2 ;; esac; shift 2 ;;
    --copy) copy_mode=1; shift ;;
    --link) LINK_MODE=1; shift ;;
    --adopt) [ $# -ge 2 ] || usage; ADOPT="${ADOPT:+$ADOPT }$(printf '%s' "$2" | tr ',' ' ')"; shift 2 ;;
    --check) [ "$command" = setup ] || usage; setup_mode=check; shift ;;
    --write) [ "$command" = setup ] || usage; setup_mode=write; shift ;;
    --replace) [ "$command" = setup ] && [ $# -ge 2 ] || usage; replace_key=$2; shift 2 ;;
    --dry-run) dry=1; shift ;;
    --watch) watch=1; shift ;;
    --interval) interval=$2; shift 2 ;;
    --max-stages) MAX_STAGES=$2; shift 2 ;;
    --story-budget) STORY_BUDGET=$2; shift 2 ;;
    --shared-builder) SHARED_BUILDER=1; SHARED_BUILDER_SET=set; shift ;;
    --shared-verifier) SHARED_VERIFIER=1; SHARED_VERIFIER_SET=set; shift ;;
    --separate-stages) SEPARATE_STAGES=1; shift ;;
    --parallel) [ $# -ge 2 ] || usage; PARALLEL=$2; shift 2 ;;
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
        # Adding a tool installs the gate, runner and hook as well: from another version that is an update
        # nobody asked for, so it is refused and named.
        local_src=${source_dir:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
        [ -f "$local_src/factory-run/scripts/story-gate.py" ] || local_src=$(plugin_skills) || local_src=""
        local_have=$(gate_field "$GATE" VERSION) local_new=""
        [ -n "$local_src" ] && local_new=$(gate_field "$local_src/factory-run/scripts/story-gate.py" VERSION)
        if [ -n "$local_new" ] && [ "$local_new" != "$local_have" ]; then
          echo "factory: adding $tool would also replace the installed pipeline $local_have with $local_new —" >&2
          echo "factory:   update first ('factory.sh update', or /factory-update), then add the tool; nothing was changed" >&2
          exit 2
        fi
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
    resolve_stages || exit 2
    if [ -n "$story" ]; then
      [ -z "$watch" ] || { echo "factory: --watch works the backlog off — it takes no --story" >&2; exit 2; }
      tool=${tool:-stand-in}
      check_gate_freshness                  # once per invocation; run_story recurses on a verdict
      [ -n "$dry" ] || refuse_nested || exit $?
      check_carriers "$tool" || exit $?
      check_contract_first || exit $?
      check_local_context "$tool"
      check_tool "$tool" || exit $?
      run_python --story "$story" --tool "$tool" ${from:+--from "$from"}
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
    check_tool "${tool:-}" || exit $?
    run_python --tool "${tool:-stand-in}" ${watch:+--watch} --interval "$interval"
    ;;
  *) usage ;;
esac
