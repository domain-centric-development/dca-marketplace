"""What the run folder knows about the stories: who holds the checkout, a gate's pass, the passes and claims kept."""

from __future__ import annotations

import os
import typing

from ..git.integration import MAIN_TESTS
from .kept_files import TESTS_BASELINE
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..pipeline.stage_rows import STAGE_FILES
from ....application.schedule.stand_story import stand_story
from ....domain.model.moment import Moment
from ....domain.model.story import Delivery, StoryId
from .run_marks import gate_passed_on_record, STORY_DIGEST
from .snapshots import STAGES_MADE
from .story_facts_files import StoryFactsFiles
from .story_layout import find_story, story_files, story_id_of
from ....domain.model.story_state import ENDED

#: What the gate and the runner keep in a story's evidence folder that a new pass starts without: the red ledger, the
#: story's digest, the tests baseline, the round count, the base tree and the red tree. The journal and the snapshots carry on.
PASS_MARKS = (".tests-red", STORY_DIGEST, TESTS_BASELINE, ".rounds", "base-tree", "red-tree", STAGES_MADE, MAIN_TESTS)

#: Where `--prove` keeps the claim it took out of the story: one line in the story's evidence.
CLAIM_FILE = "claim"


def keep_pass(folder: str) -> typing.Optional[str]:
    """Before a story runs again from plan: its hand-overs and refusals, and the marks of the pass (`PASS_MARKS`, the
    base tree the pass's diff was taken against among them), go to `<evidence>/<story>/pass-<n>/` — the next pass
    records its own. The journal and the tree snapshots stay where they are; the history continues. Returns the
    folder, or None without a run folder."""
    if not os.path.isdir(folder):
        return None
    folder = os.path.normpath(folder)
    evidence = evidence_dir(os.path.dirname(folder), os.path.basename(folder))
    os.makedirs(evidence, exist_ok=True)
    number = 1 + sum(1 for name in os.listdir(evidence) if name.startswith("pass-"))
    target = os.path.join(evidence, f"pass-{number}")
    os.makedirs(target)
    for name in sorted(os.listdir(folder)):
        os.replace(os.path.join(folder, name), os.path.join(target, name))
    for name in PASS_MARKS:
        if os.path.isfile(os.path.join(evidence, name)):
            os.replace(os.path.join(evidence, name), os.path.join(target, name))
    return target


class StoryRunFiles:
    """The stories' runs as files: the run folder <runs>, the stories under <epics>, the project <cwd>."""

    def __init__(self, cwd: str, epics: str, runs: str) -> None:
        self._cwd = cwd
        self._epics = epics
        self._runs = runs

    def holding_checkout(self, exclude: StoryId) -> typing.Sequence[StoryId]:
        holders = []
        for path in story_files(self._epics):
            try:
                front, _body = read_front_matter(path)
            except (GateError, MarkdownError):
                continue
            story_id = story_id_of(path, front)
            if story_id == exclude.value or not os.path.isfile(os.path.join(self._runs, story_id, STAGE_FILES["test"])):
                continue
            standing = stand_story(StoryFactsFiles(self._cwd, self._runs, story_id, front, path))
            if standing.state not in ENDED:
                holders.append(StoryId(story_id))
        return sorted(holders, key=lambda s: s.value)

    def gate_passed(self, story: StoryId) -> bool:
        return bool(gate_passed_on_record(self._cwd, self._runs, story.value, find_story(self._epics, story.value)))

    def keep_pass(self, story: StoryId) -> str:
        return keep_pass(os.path.join(self._runs, story.value)) or ""

    def keep_claim(self, story: StoryId, claim: Delivery, at: Moment) -> str:
        evidence = evidence_dir(self._runs, story.value)
        os.makedirs(evidence, exist_ok=True)
        path = os.path.join(evidence, CLAIM_FILE)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{at.value}\tdelivered_by={claim.by.value or 'unknown'}\tdelivered={claim.on.value}\n")
        return path
