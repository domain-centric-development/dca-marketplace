"""What the unit cases share: the package on the path, and a throwaway project with epics, stories and a run folder.

The cases call the package's functions directly — no gate process, no runner — so they run in seconds and pin
down what the parsers, the story state and the schedule say today."""

import contextlib
import os
import sys
import tempfile

sys.dont_write_bytecode = True                              # the repository carries no __pycache__
SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                        "factory-run", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
os.environ.pop("FACTORY_HOME", None)                        # a case runs in no story's worktree

from dca_factory import contract, reports, state  # noqa: E402,F401


STORY = """---
id: {id}
status: {status}
depends_on: [{deps}]
---
# {title}

## Acceptance criteria
- shows-the-thing (happy path): the thing shows
"""


EPIC = """---
intent: widgets for everyone
goal: more widgets
metric: widgets shown
domain_contact: the-expert
depends_on: [{deps}]
---
# {epic}
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


class Project:
    """A project in a temporary folder: `project/epics/` and `.dca-factory/runs/` under it, absolute paths."""

    def __init__(self, root):
        self.root = root
        self.epics = os.path.join(root, "project", "epics")
        self.runs = os.path.join(root, ".dca-factory", "runs")
        os.makedirs(self.epics)
        os.makedirs(self.runs)

    def epic(self, name, deps=()):
        return write(os.path.join(self.epics, name, contract.EPIC_FILE), EPIC.format(epic=name, deps=", ".join(deps)))

    def story(self, story_id, epic="sample", status="approved", deps=(), text=None):
        if not os.path.isfile(os.path.join(self.epics, epic, contract.EPIC_FILE)):
            self.epic(epic)
        body = text if text is not None else STORY.format(id=story_id, status=status, deps=", ".join(deps),
                                                          title=story_id)
        return write(os.path.join(self.epics, epic, story_id, contract.STORY_FILE), body)

    def handover(self, story_id, stage, text=None):
        """A stage's hand-over file under the run folder, as the stage would leave it."""
        name = contract.STAGE_FILES[stage]
        return write(os.path.join(self.runs, story_id, name), text if text is not None else f"# {stage}\n")

    def run_file(self, story_id, name, text=""):
        return write(os.path.join(self.runs, story_id, name), text)

    def evidence(self, story_id, name, text=""):
        return write(os.path.join(contract.evidence_dir(self.runs, story_id), name), text)

    def wrote(self, story_id, stage, at=None):
        """The journal's `wrote` event for the hand-over as it is on disk now."""
        name = contract.STAGE_FILES[stage]
        digest = contract.file_digest(os.path.join(self.runs, story_id, name))
        return state.journal_append(self.runs, story_id, "wrote", name, f"sha={digest}", at=at)

    def write_and_journal(self, story_id, stage, text=None, at=None):
        self.handover(story_id, stage, text)
        return self.wrote(story_id, stage, at=at)

    def state_of(self, story_id):
        path = contract.find_story(self.epics, story_id)
        front, _body = contract.read_front_matter(path)
        return state.story_state(self.root, self.runs, story_id, front, path)


@contextlib.contextmanager
def project():
    """A project, and the process working in it — the pipeline reads its places relative to the project."""
    here = os.getcwd()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        os.chdir(root)
        try:
            yield Project(os.path.realpath(root))
        finally:
            os.chdir(here)
