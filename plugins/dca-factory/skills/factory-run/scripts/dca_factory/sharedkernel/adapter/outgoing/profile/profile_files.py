"""The stack profile and the places it names — read one way for every caller.

The profile is `dca-factory.profile.yaml` at the project root, flat `key: value`, layered on the method's
configuration beside it (`dca.profile.yaml`): default → method → factory profile → a flag. From it the places: the
project description, the epics, the living spec, the discovery, the run folder and the evidence beside it, the
project's findings — resolved once per process; in a story's worktree the main checkout's.
"""

from __future__ import annotations

import contextlib
import difflib
import os
import typing

from ..markdown.front_matter import read_text
from ....application.profile import Profile


#: Every place the factory reads and writes, from the profile with its default: the project description
#: and the epics with their stories, the living spec and the discovery under `product/` (the people's), the run artefacts under
#: `.dca-factory/` (the run's protocol). The profile itself is the one fixed path — `dca-factory.profile.yaml`
#: at the project root — because it is where the others are read from.
DEFAULTS = {
    "product": "product/overview.md",
    "tech": "product/tech.md",
    "domain": "product/domain.md",
    "epics": "product/epics",
    "runs": ".dca-factory/runs",
    "discovery": "product/discovery",
    "spec": "product/spec",
}


PROFILE_FILE = "dca-factory.profile.yaml"


#: The method's configuration (WP-99): one file at the project root, flat `key: value`, every key optional — the
#: places of the project description and the conventions every DCA skill reads. The factory's profile layers on it:
#: default → `dca.profile.yaml` → `dca-factory.profile.yaml` → a flag.
METHOD_PROFILE = "dca.profile.yaml"


#: The method's place keys and the factory's key each feeds, with the file or folder under `root:` it defaults to.
METHOD_PLACES = (("overview", "product", "overview.md"), ("tech", "tech", "tech.md"), ("domain", "domain", "domain.md"),
                 ("epics", "epics", "epics"), ("discovery", "discovery", "discovery"), ("spec", "spec", "spec"))


#: The method's root of the project description, where `dca.profile.yaml` names none.
METHOD_ROOT = "product/"


def method_profile_path(cwd: typing.Optional[str] = None) -> str:
    """`dca.profile.yaml` of this project — in a story's worktree the main checkout's, like the factory profile."""
    base = (factory_home() or "") if in_worktree(cwd) else (cwd or os.getcwd())
    return os.path.join(base, METHOD_PROFILE)


def method_layer(method: typing.Mapping[str, typing.Any]) -> typing.Dict[str, str]:
    """What the method's configuration gives the factory's profile: a place for every key it names, or that its
    `root:` moves — and `architecture:` from its `verify_command:`. The factory's profile wins over each."""
    layer: typing.Dict[str, str] = {}
    root = str(method.get("root", "")).strip().replace("\\", "/")
    for method_key, factory_key, under in METHOD_PLACES:
        own = str(method.get(method_key, "")).strip().replace("\\", "/")
        if own:
            layer[factory_key] = own
        elif root:
            layer[factory_key] = root.rstrip("/") + "/" + under
    verify = str(method.get("verify_command", "")).strip().strip("`")
    if verify:
        layer["architecture"] = verify
    return layer


#: The places as this process resolved them once — a flag wins, then the profile's key, then the default —
#: so no reader in the gate, the CLI, the runner or the observer hard-codes one.
PLACES: typing.Dict[str, str] = {}


#: The places as the profile names them, relative to the project — what a story's worktree links to the main
#: checkout's, and what the gate leaves out of a worktree's changes.
PLACES_REL: typing.Dict[str, str] = {}


def set_places(profile: typing.Mapping[str, typing.Any], **given: typing.Any) -> None:
    PLACES.clear()
    PLACES_REL.clear()
    home = factory_home() if in_worktree() else None
    for key in DEFAULTS:
        relative = str(given.get(key) or "").strip().replace("\\", "/") or location(profile, key)
        PLACES_REL[key] = relative
        PLACES[key] = os.path.join(home, relative).replace("\\", "/") if home and not os.path.isabs(relative) \
            else relative


def place(key: str) -> str:
    return PLACES.get(key) or DEFAULTS[key]


def runs_top() -> str:
    """The first segment of the run folder — what a walk over the project leaves out."""
    return place("runs").strip("/").split("/")[0]


# --- a story in a worktree of its own (WP-92) -------------------------------------------------------------
# The runner gives every story a git worktree on a branch of its own, `story/<id>`, under the run folder's
# parent (`.dca-factory/worktrees/<id>`): the story's code lives there until it is integrated, so a story that
# waits — for an answer, for an acceptance — holds no checkout, and several stories run at once. What is state
# stays in the main checkout: the stories with their decisions, the run folder, the profile, the installed
# pipeline and the skills. The worktree sees them through links; a process in the worktree is told the main
# checkout by FACTORY_HOME, and the gate and the CLI read every place from there. Nothing that is state ever
# lands on the story's branch, so no answer and no delivery can fork with it.
HOME_VARIABLE = "FACTORY_HOME"


#: What a worktree links to the main checkout besides the profile's places: the installed pipeline and the
#: tools' skill folders — a link in a skill folder is git-ignored and would be missing from a fresh checkout.
WORKTREE_LINKED = (".agents/factory", ".claude/skills", ".codex/skills", ".opencode/skills", ".agents/skills")


#: Where a story's branch begins its name: `story/<id>`.
STORY_BRANCH = "story/"


def factory_home() -> typing.Optional[str]:
    """The main checkout a process in a story's worktree belongs to, from FACTORY_HOME; None outside one."""
    value = os.environ.get(HOME_VARIABLE, "").strip()
    return os.path.abspath(value) if value else None


def in_worktree(cwd: typing.Optional[str] = None) -> bool:
    """Whether this process works in a story's worktree: FACTORY_HOME names a main checkout other than here."""
    home = factory_home()
    return home is not None and os.path.realpath(home) != os.path.realpath(cwd or os.getcwd())


def worktree_places() -> typing.Tuple[typing.List[str], typing.List[str]]:
    """(folders, files) a worktree takes from the main checkout, relative: the epics, the run folder, the
    discovery reports and the project's findings as links with the pipeline and the skill folders; the description and the profile as
    copies, read alone."""
    def rel(key: str) -> str:
        return (PLACES_REL.get(key) or DEFAULTS[key]).rstrip("/")
    folders = [rel("epics"), rel("runs"), evidence_rel(), rel("discovery"), findings_rel()] + list(WORKTREE_LINKED)
    files = [rel("product"), rel("tech"), rel("domain"), PROFILE_FILE]
    return folders, files


def worktree_owned(path: str) -> bool:
    """A path in a worktree that is the main checkout's, not the story's: under a linked place, or a copied file."""
    folders, files = worktree_places()
    return path in files or any(path == f or path.startswith(f + "/") for f in folders)


#: Where the gate and the runner keep what proves a story's work — the journal, the red ledger, the tree snapshots,
#: the changed-files records, the base tree, the story's digest, the round count: beside the run folder, never in
#: it. A stage writes the run folder (its hand-over files); what it is judged by lies where no stage may write.
EVIDENCE = "evidence"


def evidence_rel() -> str:
    """The evidence folder relative to the project: beside the run folder."""
    runs = (PLACES_REL.get("runs") or DEFAULTS["runs"]).rstrip("/")
    return os.path.join(os.path.dirname(runs) or ".dca-factory", EVIDENCE).replace("\\", "/")


def evidence_dir(runs: str, story_id: typing.Optional[str] = None) -> str:
    """A story's evidence folder (or the folder of all of them) beside the run folder `runs` — relative or
    absolute as `runs` is."""
    root = os.path.join(os.path.dirname(os.path.normpath(runs)) or ".dca-factory", EVIDENCE)
    return os.path.join(root, story_id) if story_id else root


#: The story's journal: one line per event — `<UTC time>\t<kind>\t<name>\t<field=value>…\tseq=<n>`. The sequence
#: number orders the events, never the clock: two events in one second, a file written in the same second as a gate
#: ran, are told apart by it. The runner, the gate and the cli append through `journal_append`, nothing else writes.
JOURNAL = "journal.tsv"


def unquoted(value: str) -> str:
    """A profile value without the one pair of quotes around it — a quote inside it, at its end too, stays."""
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def read_flat(path: typing.Optional[str]) -> typing.Dict[str, str]:
    """A flat `key: value` file; {} where there is none."""
    if not path or not os.path.isfile(path):
        return {}
    values = {}
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = unquoted(value.strip())
    return values


def read_profile(path: typing.Optional[str]) -> typing.Dict[str, str]:
    """Flat `key: value` profile, layered on the method's configuration beside it (`dca.profile.yaml`): a place
    or the architecture command the factory's profile does not name comes from there. Missing file is not an
    error — every command is then reported as not declared."""
    if path and os.path.basename(path) == PROFILE_FILE:
        method = read_flat(os.path.join(os.path.dirname(path) or ".", METHOD_PROFILE))
    elif not path:
        method = read_flat(method_profile_path())
    else:
        method = {}
    if not path or not os.path.isfile(path):
        return dict(method_layer(method)) if method else {}
    profile = read_flat(path)
    for key, value in method_layer(method).items():
        profile.setdefault(key, value)
    return profile


#: The profile's schema: every key the gate, the cli, the runner or a stage reads, as written in
#: `templates/factory.profile.yaml.tmpl`. A key outside it is read by nobody, so the contract check names it — a
#: note, never a refusal: a misspelt `requried:` is a check that quietly went, a key from a newer release is one
#: this copy cannot use.
PROFILE_KEYS = frozenset((
    # several factories on one backlog (WP-93): the remote whose branches are the claims, and their prefix
    "claim_remote", "claim_branch_prefix",
    # what declares a test double, where the built-in list does not cover the stack (WP-100)
    "mockMarkers",
    # the tool a run starts its units with where `--tool` names none (WP-95); `tool.<unit>` per unit
    "tool",
    # the commands and how the gate selects and reads a single test
    "compile", "test", "e2eTest", "architecture", "format", "formatFix",
    "filterFlag", "filterFormat", "filterJoin", "testReport", "testEvidence",
    # what the project has, and what must hold
    "required", "checks.backlog", "browser", "integration", "http.stub", "adopt.breakProof", "acceptance", "run",
    # where things are (DEFAULTS), the generated map and the glossary; `backlog` is the older layout's, named by
    # the layout hint
    *DEFAULTS, "contextMap", "glossary", "backlog",
    # what the stages read and how the runner starts them
    "knowledge", "knowledge.read", "reviews", "stages", "parallel", "stageTimeout", "sessionUsage", "contract",
    # how long a delivered story's raw streams and snapshots are kept (WP-150)
    "evidence.keepDays",
    # `model` alone is refused by the model check, which names the right form
    "model",
))

#: Key families: `<prefix><name>`, with an open list of names — a test command (`test.integration`), what a
#: command covers (`covers.test`), a carrier (`carrier.build`), a perspective's reviewer (`review.ddd`), a model
#: (`model.claude`, `model.claude.tidy`; the model check holds tool and stage).
PROFILE_FAMILIES = ("test.", "covers.", "carrier.", "review.", "model.", "tool.", "effort.")


def unknown_profile_keys(profile: typing.Mapping[str, typing.Any]) -> typing.List[typing.Tuple[str, typing.Optional[str]]]:
    """The profile's keys outside the schema, each with the nearest known one where one is close (else None)."""
    unknown = []
    for key in sorted(profile):
        if key in PROFILE_KEYS or any(key.startswith(family) and len(key) > len(family)
                                      for family in PROFILE_FAMILIES):
            continue
        head, dot, tail = key.partition(".")
        family = difflib.get_close_matches(head + ".", PROFILE_FAMILIES, n=1, cutoff=0.75) if dot and tail else []
        near = [family[0] + tail] if family else difflib.get_close_matches(key, PROFILE_KEYS, n=1, cutoff=0.75)
        unknown.append((key, near[0] if near else None))
    return unknown


#: The project's own findings — one that belongs to no story, such as a test that turns out flaky in more than one
#: story (WP-146) — beside the epics: `<product>/findings/<name>.md`, the same table as a story's findings.md, a row
#: named `<name>#<n>` where a task `closes:` it.
PROJECT_FINDINGS = "findings"


#: The file a flaky test's finding goes to: `<product>/findings/flaky.md`.
FLAKY_FINDINGS = "flaky"


def findings_dir() -> str:
    """The project's findings folder beside the epics: `product/findings` for `product/epics`."""
    epics = place("epics").rstrip("/")
    return os.path.join(os.path.dirname(epics) or ".", PROJECT_FINDINGS)


def findings_rel() -> str:
    """The project's findings folder relative to the project, as the profile places the epics."""
    epics = (PLACES_REL.get("epics") or DEFAULTS["epics"]).rstrip("/")
    return os.path.join(os.path.dirname(epics) or ".", PROJECT_FINDINGS).replace("\\", "/")


def shown(path: str) -> str:
    """A path as a person reads it — relative to the project, with `/` on every platform. In a story's worktree a
    path of the main checkout's is shown from there: the story, its records, the run folder."""
    home = factory_home()
    if home and in_worktree():
        absolute, here = os.path.abspath(path), os.path.abspath(os.getcwd())
        if absolute.startswith(home + os.sep) and not absolute.startswith(here + os.sep):
            return os.path.relpath(absolute, home).replace(os.sep, "/")
    return os.path.relpath(path).replace(os.sep, "/")


def location(profile: typing.Mapping[str, typing.Any], key: str) -> str:
    """Where the profile puts one part of the project description, or its default under `product/`."""
    return str(profile.get(key, "")).strip().replace("\\", "/") or DEFAULTS[key]


def resolve_profile(given: typing.Optional[str], cwd: str) -> typing.Optional[str]:
    """The stack profile: the one named, else `dca-factory.profile.yaml` at the project root — the one fixed
    path, since every other place is read from it. An older place is not read; `layout_hint` names it."""
    if given:
        return given
    if in_worktree(cwd):
        # in a story's worktree the profile is the main checkout's — the person's, as it is now
        home_profile = os.path.join(factory_home() or "", PROFILE_FILE)
        return home_profile if os.path.isfile(home_profile) else None
    return PROFILE_FILE if os.path.isfile(os.path.join(cwd, PROFILE_FILE)) else None


def profile_of(cwd: str, given: typing.Optional[str] = None) -> Profile:
    """The project's stack profile as a value, read once: the one named, else the project's own."""
    return Profile(read_profile(resolve_profile(given, cwd)))


@contextlib.contextmanager
def places_in(cwd: str) -> typing.Iterator[None]:
    """The epics and the spec read from this worktree, not the main checkout — where the remote main line is what
    the story was merged with (WP-93 D)."""
    home = factory_home() or cwd
    saved = dict(PLACES)
    try:
        for key in ("epics", "spec"):
            own = saved.get(key) or DEFAULTS[key]
            PLACES[key] = os.path.join(cwd, os.path.relpath(own if os.path.isabs(own) else os.path.join(home, own), home))
        yield
    finally:
        PLACES.clear()
        PLACES.update(saved)


class ProfileFiles:
    """The stack profile at <path> (None: no profile), read anew on every question: a person may edit it meanwhile."""

    def __init__(self, path: typing.Optional[str]) -> None:
        self._path = path

    def profile(self) -> typing.Mapping[str, str]:
        return read_profile(self._path)
