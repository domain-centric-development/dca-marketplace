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
#   factory.sh run [--story <id>] [--tool <tool>] [--from <stage>] [--watch [--stay] [--lane]] [--interval <s>]
#                  [--max-stages <n>] [--story-budget <tokens>] [--separate-stages] [--parallel <n>] [--dry-run]
#                  [--shared-builder] [--shared-verifier] [--keep-going]
#                    one story from where its files say (--from names the stage and starts a new
#                    count of rounds), or without --story the whole backlog in the schedule's order;
#                    every story in a worktree of its own, integrated into the checkout's branch when
#                    every gate passed; --parallel runs up to <n> stories at once; shared stages are the
#                    default, --shared-builder/--shared-verifier share one half over `stages: separate`;
#                    --keep-going: a stopped story does not end the backlog run — it and what depends on it
#                    are skipped, and the run ends when nothing more can start (a stop file still ends it)
#   factory.sh up [--serve] [--port <n>] [--by <who>] [--tool <tool>] [--parallel <n>] [--interval <s>] [--keep-going] …
#                    the backlog on, and the factory's worker started where none runs: `run --watch --stay --lane` in
#                    the background, its pid and log beside the run folder; it works a person's requests at once and
#                    the backlog off until `down`. --serve: the page too. --requests: the worker alone, the backlog as
#                    it is (the page starts it so)
#   factory.sh down [--now] [--no-wait]      the backlog off — no further story of it starts; with a page open its
#                                            requests go on, without one the worker ends after its running stage;
#                                            --now interrupts the running stage and ends the worker too
#   factory.sh serve [--port <n>] [--open] [--background] [--stop] [--fixture <name>]   the factory's page on
#                    127.0.0.1 — a URL with a token of this start; every press writes a request, worked while the page
#                    is open. Each checkout takes a port of its own (8700–8899); --stop ends a page that runs in the
#                    background; --fixture all-states|empty serves it against canned views, writing nothing. A project's
#                    look: .dca-factory/theme/theme.css (and the images it names), `#components` shows it
#   factory.sh request <kind> [<target>…] [<words>…|-] [--by <who>] [--option <key>] [--from <stage>]
#                    one request the factory's worker runs at once, beside any running story: wish, release,
#                    stories, journey, describe, discover, epic-from, answer, accept, correct, run, stop
#   factory.sh requests [--format text|json] [--drop <id>] [--retry <id>]   the requests and their state
#   factory.sh status [--all] [--story <id>] [--epic <id>] [--usage] [--refusals] [--brief]   what runs, what waits, what comes next; --all: every story and the cost; --refusals: form against substance
#   factory.sh decisions [--story <id>]      the decision inbox
#   factory.sh lessons [--write] [--format json]   what repeats across the stories: the lesson candidates; --write
#                                            asks each one nobody was asked yet as a lesson record in decide
#   factory.sh spec-delta <story> [--format json]  what holds before and after the story
#   factory.sh spec [--context <c>] [--format md|json]   what holds: each context with its domain model, features,
#                                            rules and criteria, and the open stories that would change them
#   factory.sh rules [--stage <s>] [--kind <k>] [--story <id>] [--format md|json|svg|mermaid] [--check]   every rule
#                                            the gate, the runner and the stage skills hold a story to, in each kind's
#                                            flow; svg, mermaid: the flow of --kind drawn — steps, gates, rounds, ways back
#   factory.sh brief <story> <stage> [--format json]   what the stage is told for the story: its brief, from the
#                                                     workflow's stages and rules and the profile
#   factory.sh release <story> [--force]     give up a story's claim on the remote (`claim_remote:`); --force: another's
#   factory.sh integrate <story>             a published story whose merge request lost the race: delivered again
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
# What every verb decides — its flags, the checks before a run, the setup, the update — is the package's: the
# command line `dca_factory/delivery/adapter/incoming/shell/shell_command.py`, wired by `infrastructure/shell.py`,
# beside the gate's and the cli's in one process. This script finds a Python the package runs on and hands over at
# once; a process start is what a run pays most for under Git Bash. The one thing it says itself is what no Python can
# say: that there is none, or none beside it.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="$HERE/factory-cli.py"

# Every Python this runner starts writes UTF-8 — the gate's and the setup's lines carry `—` and `→`, and a Windows
# console's code page (cp1252) cannot encode them: the print raises and the step dies.
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

# Which Python runs the package. `python3` is the POSIX spelling; on Windows the interpreter is `python` or `py`, and
# `python3` is often the WindowsApps alias that opens a shop window instead of running — found on PATH all the same. So
# each name is asked to run, not only looked up. FACTORY_PYTHON overrides, for a project that pins one. The *name* is
# what reaches the profile and the permission list, so both stay portable between machines. The package needs Python
# 3.12 or newer; a versioned name is asked after the plain ones, for a machine whose `python3` is the system's older
# one (macOS' /usr/bin) while a newer one sits beside it on PATH.
PY_MIN="3.12"
fits() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1; }
PY="${FACTORY_PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in python3 python py python3.14 python3.13 python3.12; do
    fits "$candidate" && { PY=$candidate; break; }
  done
  if [ -z "$PY" ]; then
    echo "factory: needs Python $PY_MIN or newer — none on PATH (python3, python, py, python3.12–3.14); FACTORY_PYTHON names one" >&2
    exit 2
  fi
elif ! fits "$PY"; then
  echo "factory: needs Python $PY_MIN or newer — FACTORY_PYTHON=$PY is older or does not run" >&2
  exit 2
fi

# The package and the cli beside this runner are what it hands over to: `update` puts all three there. Without them
# an update or a setup that names its source is handed to that pipeline's runner; anything else stops.
if [ ! -f "$CLI" ] || [ ! -d "$HERE/dca_factory" ]; then
  case "${1:-}" in
    setup|update)
      source_dir="" previous=""
      for word in "$@"; do [ "$previous" = --from ] && source_dir=$word; previous=$word; done
      source_dir=${source_dir:-${FACTORY_PLUGIN_DIR:-}}
      newest="$source_dir/factory-run/scripts"
      if [ -n "$source_dir" ] && [ -f "$newest/factory-cli.py" ] && [ -d "$newest/dca_factory" ]; then
        exec bash "$newest/factory.sh" "$@"
      fi ;;
  esac
  if [ ! -d "$HERE/dca_factory" ]; then
    echo "factory: no dca_factory/ beside the gate — 'factory.sh update' puts it there. Nothing was started." >&2
  else
    echo "factory: no factory-cli.py beside the gate — 'factory.sh update' puts it there. Nothing was started." >&2
  fi
  exit 2
fi

exec "$PY" "$CLI" --sh "$PY" "$@"
