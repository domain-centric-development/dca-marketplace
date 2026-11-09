"""A passing gate's writes as files and commits."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from .....sharedkernel.adapter.outgoing.profile.profile_files import factory_home, in_worktree, places_in, shown
from ....application.shared.stage_delivery import AcceptanceFacts, Landing
from ....domain.model.story import Delivery
from ....domain.model.decision_record import RecordId
from ....domain.model.story_state import Acceptance, AcceptanceVerdict
from ..claims.remote_claims import claim_config_here
from .decision_record_files import acceptance_state, record_path
from .delivery_writes import (
    acceptance_applies, checkout_story, commit_delivery, keep_beside_delivery, keep_published_status,
    prepare_delivery, publish_story, record_red_tree, record_tests_baseline, take_into_home)
from .run_marks import STORY_DIGEST, write_mark
from ..git.checkout import Checkouts
from .owned_files import regard_gate_line
from .signals import journal_signal, plan_left_open
from .story_layout import story_digest
from ....application.shared.stage_delivery import StageDelivery


class StageDeliveryFiles(StageDelivery):
    """The writes of a passing gate in the project <cwd> with its run folder <runs> and its profile."""

    def __init__(self, cwd: str, runs: str, profile: typing.Mapping[str, typing.Any],
                 checkouts: typing.Optional[Checkouts] = None) -> None:
        self._cwd = cwd
        self._runs = runs
        self._profile = profile
        self._checkouts = checkouts if checkouts is not None else Checkouts()

    def plan_marks(self, story: str, story_path: str) -> None:
        write_mark(self._runs, story, STORY_DIGEST, story_digest(story_path))
        record_tests_baseline(self._cwd, self._runs, story, self._checkouts)
        plan = os.path.join(self._runs, story, "plan.md")
        journal_signal(self._runs, story, "plan", open=len(plan_left_open(read_text(plan))) if os.path.isfile(plan) else 0)

    def adopted(self, result: typing.Any, story: str, story_path: str) -> None:
        regard_gate_line(story_path, self._runs)
        result.ok("plan-adopts", f"{story} is `status: adopted` now — the runner goes on with the adoption")

    def split_kept(self, result: typing.Any, story: str, story_path: str, into: str,
                   scenarios: typing.Sequence[str]) -> None:
        # the story as planned is the story without what moved: the digest the later gates compare takes it
        regard_gate_line(story_path, self._runs)
        result.ok("plan-adopts", f"{', '.join(scenarios)} moved into the adopted story {into}; {story} builds the rest")

    def red_tree(self, result: typing.Any, story: str) -> None:
        record_red_tree(result, self._cwd, self._runs, story, self._checkouts)

    def acceptance(self, story: str, story_path: str) -> AcceptanceFacts:
        try:
            if not acceptance_applies(self._cwd, self._runs, story, self._profile):
                return AcceptanceFacts(False, None, None)
            verdict, rid = acceptance_state(self._cwd, story, story_path)
        except GateError as error:
            return AcceptanceFacts(False, None, str(error))
        return AcceptanceFacts(True, Acceptance(AcceptanceVerdict(verdict), RecordId(rid) if rid else None), None)

    def record_place(self, story: str, story_path: str, record: str) -> str:
        return str(shown(record_path(story, record, story_path)))

    def in_worktree(self) -> bool:
        return bool(in_worktree())

    def landing(self) -> Landing:
        return Landing.CHECKOUT if claim_config_here(factory_home() or self._cwd) else Landing.STORY

    def prepare(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                landing: Landing) -> bool:
        if landing is Landing.STORY:
            return prepare_delivery(result, story_path, story, front, self._runs)
        with places_in(self._cwd):
            here = checkout_story(self._cwd, story_path)
            return prepare_delivery(result, here, story, read_front_matter(here)[0], self._runs)

    def delivered(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                  delivery: Delivery, landing: Landing) -> None:
        if landing is Landing.STORY:
            keep_beside_delivery(result, story_path, story, front, self._runs, delivery)
            return
        with places_in(self._cwd):
            here = checkout_story(self._cwd, story_path)
            keep_beside_delivery(result, here, story, read_front_matter(here)[0], self._runs, delivery)

    def take_in(self, result: typing.Any, story: str, story_path: str, landing: Landing) -> bool:
        if landing is Landing.STORY:
            return take_into_home(result, self._cwd, story, self._runs)
        keep_published_status(self._cwd, story_path, story, self._runs)
        return True

    def hand_on(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                landing: Landing, close: typing.Callable[[], None]) -> None:
        home = factory_home() or self._cwd
        if landing is Landing.STORY:
            commit_delivery(result, home, story, front, close)
            return
        publish_story(result, self._cwd, story_path, story, self._runs, claim_config_here(home) or {})
