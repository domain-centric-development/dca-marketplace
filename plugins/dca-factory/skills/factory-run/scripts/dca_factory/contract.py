"""The files' contract — what a project file says, read one way for every caller.

The places (profile keys, the evidence folder, a story's worktree), front matter, the profile, the story and
epic files, the decision records, the stage table (`STAGES`, one row per stage) and the contract's version.
Nothing here runs a command or decides a stage; the modules above read through these functions, so two callers
can never disagree about what a file says.
"""

import os
import re
import typing

from .sharedkernel.adapter.outgoing.profile.profile_files import (
    place, PROFILE_FILE, shown)
from .delivery.adapter.outgoing.files.findings_files import FINDINGS_FILE
from .sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError
from .delivery.adapter.outgoing.files.story_layout import DECISIONS_DIR, flat_stories, STORY_FILE
from .delivery.domain.model.story_state import MAX_ROUNDS  # noqa: F401 — read by the gate and the runner
from .delivery.domain.model.stage import PIPELINE, StoryKind, TESTED_KINDS as DOMAIN_TESTED_KINDS, Trait


#: What the gate calls a project file it cannot read as it should — the shared kernel's `MarkdownError`.
GateError = MarkdownError


EPIC_FIELDS = ("intent", "goal", "metric", "domain_contact")



#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools
#: have comparable budgets. Reported as a note, never a failure — the size is not this story's fault.
DOC_BUDGET_BYTES = 32 * 1024


CONTEXT_MAP_CANDIDATES = (
    "product/domain.md",
    "docs/context-map.md",
    "docs/architecture/context-map.md",
    "context-map.md",
)


INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")


CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*:\s*(\S.*)$")


#: The one scenario per story that shows its value, marked where the story is written: `#### <key> (happy path)`
#: or `- <key> (happy path): <criterion>`. It gets the end-to-end test; the others are integrated.
HAPPY_MARK = re.compile(r"^(?:####\s+|-\s+)([a-z0-9][a-z0-9-]*)\s*\(happy path\)\s*(?::.*)?$")


MAPPING_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|")


SELECTOR = re.compile(r"^([\w.]+)#([\w]+)$")


#: Two different questions, so two different numbers.
#:
#: CONTRACT is the version of the *files* the gate reads and writes: the stack profile's keys, the
#: `gate:tests` table, the red ledger, the shape of a document claim. It goes up only when an older
#: or newer artefact would be read wrongly — that is what makes a mismatch a refusal.
#:
#: VERSION is where this copy came from. The gate is *copied* into a project (`.agents/factory/`),
#: so a project can be governed by a release older than the pipeline it was installed from without
#: anything being incompatible. That is an update to offer, never a reason to refuse, and only the
#: installer can see it — it is the one place that holds both files.
CONTRACT = 26


VERSION = "0.94.0"




# --- what is the person's: the story and the answers (WP-94) --------------------------------------------------
# A story's file and every decision's `## Answer` are written by a person — through `/factory-decisions`, by hand —
# and by the gate where it delivers or reopens a story; never by a stage. At a stage window's start the runner (or a
# session's `--stage-start`) records a digest of them; a gate inside the window and the window's end compare. A
# change under a stage is marked (`.owned-changed`) and the story stays stopped until a person looked at it and
# confirms (`factory-cli.py --owned-confirm <story>`). `by:` is free text: the digest is the proof, not the name.
OWNED_DIGEST = ".owned-digest"


#: The hand-overs' digests at a window's start: what the window left as it was.
WINDOW_DIGEST = ".window-digest"


def layout_hint(cwd, profile):
    """An older layout, named and never read: `factory.sh update` migrates it. The places this gate reads are
    the profile's and the defaults; a folder from before is not a fallback, because a reader that quietly
    took it would keep two layouts alive."""
    old = []
    if profile.get("backlog") and not profile.get("epics"):
        old.append("`backlog:` in the profile is now `epics:`")
    if os.path.isdir(os.path.join(cwd, "backlog")) and not os.path.isdir(os.path.join(cwd, "project")):
        old.append("backlog/ at the root is now product/epics/ (and backlog/product.md product/overview.md)")
    if os.path.isdir(os.path.join(cwd, "project", "backlog")) and not os.path.isdir(os.path.join(cwd, place("epics"))):
        old.append(f"project/backlog/ is now {place('epics')}/")
    if os.path.isdir(os.path.join(cwd, "project")) and not os.path.isdir(os.path.join(cwd, "product")) \
            and place("epics").replace("\\", "/").endswith("product/epics"):
        old.append("project/ is now product/ (and project/product.md product/overview.md)")
    if os.path.isfile(os.path.join(cwd, ".agents", "factory", "factory.profile.yaml")) \
            and not os.path.isfile(os.path.join(cwd, PROFILE_FILE)):
        old.append(f".agents/factory/factory.profile.yaml is now {PROFILE_FILE} at the project root")
    if os.path.isdir(os.path.join(cwd, ".agents", "factory", "decisions")):
        old.append(f".agents/factory/decisions/ now lives in each story's folder, as <story>/{DECISIONS_DIR}/")
    flat = flat_stories(os.path.join(cwd, place("epics")))
    if flat:
        old.append(f"{len(flat)} story file(s) in the flat layout ({shown(flat[0])}{', …' if len(flat) > 1 else ''}) — "
                   f"a story is a folder now, <epic>/<story>/{STORY_FILE} with its {DECISIONS_DIR}/ and "
                   f"{FINDINGS_FILE} inside")
    tasks = os.path.join(cwd, "tasks")
    if os.path.isdir(tasks) and any(os.path.isdir(os.path.join(tasks, d, ".verify")) or os.path.isfile(os.path.join(tasks, d, ".story-digest"))
                                    for d in os.listdir(tasks)):
        old.append(f"the run artefacts under tasks/ now live under {place('runs')}/ (tasks/ is the project's again)")
    if not old:
        return None
    return "the layout changed — `factory.sh update` migrates it (once, and says what it moved): " + "; ".join(old)


class Stage(typing.NamedTuple):
    """One row of the pipeline, flat — the domain's `Stage` in words and flags."""
    name: str
    file: str = ""            #: the hand-over it writes under the run folder ("" — a gate-only step)
    window: str = ""          #: the shared process that may carry it ("builder", "verifier"), "" — its own
    kinds: tuple = ("story",) #: the story kinds that run it (story, journey, adopt, task)
    gated: bool = True        #: a gate runs for it (`--stage <name>`)
    post_gated: bool = False  #: that gate runs after its file is written, so a pass vouches for the file
    commands: tuple = ()      #: the profile's extra commands its gate runs, in this order; a key not declared is
                              #: skipped and named — a gate failing on a command nobody configured gets switched off
    tested: bool = False      #: its gate runs the mapped tests (red or green) and the checks before them
    red: bool = False         #: a story's mapped tests are red at its gate (a journey's and an adoption's green)
    sizes: tuple = ()         #: the hand-overs whose size its gate weighs against the criteria
    lists: bool = False       #: its hand-over lists the files it changed, and its gate holds it to that list
    guarded: bool = False     #: it writes production code, under the profile's guard skill (`carrier.guard`)
    suite: bool = False       #: its gate runs the policy's required suites whole
    in_order: bool = True     #: a step of the story's run order (adopt and integrate are steps after it)


#: The kinds of story, in the domain's order.
ALL_KINDS = tuple(kind.value for kind in StoryKind)


#: A task (WP-106) changes nothing an actor sees — a refactoring, a finding without a change of behaviour, a dependency
#: or build change: no criterion, so no test stage; the existing suite, run whole, is its evidence.
TESTED_KINDS = tuple(kind.value for kind in StoryKind if kind in DOMAIN_TESTED_KINDS)


def flat_row(row):
    """A stage of the domain's pipeline as the gate, the runner and the cli read it: words and flags."""
    return Stage(row.name.value, row.hand_over.value if row.hand_over else "",
                 row.window.value if row.window else "", tuple(k.value for k in StoryKind if k in row.kinds),
                 Trait.GATED in row.traits, Trait.POST_GATED in row.traits, tuple(c.value for c in row.commands),
                 Trait.TESTED in row.traits, Trait.RED in row.traits, tuple(h.value for h in row.sizes),
                 Trait.LISTS in row.traits, Trait.GUARDED in row.traits, Trait.SUITE in row.traits,
                 Trait.IN_ORDER in row.traits)


#: The pipeline, one row per stage — the domain's (`delivery/domain/model/stage.py`), in the words the modules not
#: yet moved read.
STAGES = tuple(flat_row(row) for row in PIPELINE)


STAGE = {stage.name: stage for stage in STAGES}


#: The hand-over each stage of the run order writes.
STAGE_FILES = {s.name: s.file for s in STAGES if s.in_order}


#: One process may carry several stages and mark its window under one name: the shared builder (plan to
#: tidy) and the shared verifier (judge, then document). The journal, the changed-files record and the
#: usage are that window's; every stage still writes its own file.
SHARED_WINDOWS = {w: tuple(s.name for s in STAGES if s.window == w) for w in dict.fromkeys(s.window for s in STAGES if s.window)}


#: Extra profile commands run per stage, in this order.
STAGE_CHECKS = {s.name: s.commands for s in STAGES if s.gated}


#: The stages whose gate runs after their file is written, so a pass of that gate vouches for the file as it stands.
POST_GATED = tuple(s.name for s in STAGES if s.post_gated)


def stage_order(kind="story"):
    """The run order of a story of this kind."""
    return tuple(s.name for s in STAGES if s.in_order and kind in s.kinds)


# Several stories are a loop over one story run, and the loop needs to know what comes next without
# anyone remembering it. So the state is read off the same files a single run leaves — stage files,
# refusal reports, the round counter, the verdict, the decision records — and never stored.
STAGE_ORDER = stage_order("story")


JOURNEY_ORDER = stage_order("journey")                       # nothing to build: the steps are delivered


ADOPT_ORDER = stage_order("adopt")                           # nothing built: the adopt gate delivers it


TASK_ORDER = stage_order("task")                             # nothing new to test: the existing suite holds


def order_for(kind):
    """The run order of a story of this kind, from the stage table."""
    return {"journey": JOURNEY_ORDER, "adopt": ADOPT_ORDER, "task": TASK_ORDER}.get(kind, STAGE_ORDER)


#: Checks about how a hand-over is written rather than whether the work is right: a refusal by one of them costs a
#: round without the code being wrong. The journal names every refusal's checks; reports count the two apart.
FORM_CHECKS = ("files-listed", "story-pass", "tests-mapped", "test-titles", "plan-levels", "levels", "documented",
               "decisions", "reviews", "layout")
