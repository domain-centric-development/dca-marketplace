"""A passing gate's writes as files and commits."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import factory_home, in_worktree, shown
from ....application.shared.stage_delivery import AcceptanceFacts
from ....domain.model.decision_record import RecordId
from ....domain.model.story_state import Acceptance, AcceptanceVerdict
from ..claims.remote_claims import claim_config_here
from .decision_record_files import acceptance_state, record_path
from .delivery_writes import (
    acceptance_applies, ask_acceptance, deliver, integrate_into_home, publish_story, record_red_tree,
    record_tests_baseline)
from .run_marks import STORY_DIGEST, write_mark
from .signals import journal_signal, plan_left_open
from .story_layout import story_digest


class StageDeliveryFiles:
    """The writes of a passing gate in the project <cwd> with its run folder <runs> and its profile."""

    def __init__(self, cwd: str, runs: str, profile: typing.Mapping[str, typing.Any]) -> None:
        self._cwd = cwd
        self._runs = runs
        self._profile = profile

    def plan_marks(self, story: str, story_path: str) -> None:
        write_mark(self._runs, story, STORY_DIGEST, story_digest(story_path))
        record_tests_baseline(self._cwd, self._runs, story)
        plan = os.path.join(self._runs, story, "plan.md")
        journal_signal(self._runs, story, "plan", open=len(plan_left_open(read_text(plan))) if os.path.isfile(plan) else 0)

    def red_tree(self, result: typing.Any, story: str) -> None:
        record_red_tree(result, self._cwd, self._runs, story)

    def acceptance(self, story: str, story_path: str) -> AcceptanceFacts:
        try:
            if not acceptance_applies(self._cwd, self._runs, story, self._profile):
                return AcceptanceFacts(False, None, None)
            verdict, rid = acceptance_state(self._cwd, story, story_path)
        except GateError as error:
            return AcceptanceFacts(False, None, str(error))
        return AcceptanceFacts(True, Acceptance(AcceptanceVerdict(verdict), RecordId(rid) if rid else None), None)

    def ask(self, story: str, story_path: str, criteria: typing.Sequence[typing.Tuple[str, str]]
            ) -> typing.Tuple[str, str, typing.Optional[str]]:
        try:
            asked = ask_acceptance(self._cwd, self._runs, story, story_path, self._profile, list(criteria))
        except GateError as error:
            return "", "", str(error)
        return asked, shown(record_path(story, asked, story_path)), None

    def in_worktree(self) -> bool:
        return bool(in_worktree())

    def deliver(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any]) -> None:
        deliver(result, story_path, story, front, self._runs)

    def integrate(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                  close: typing.Callable[[], None]) -> None:
        config = claim_config_here(factory_home() or self._cwd)
        if config:
            publish_story(result, self._cwd, story_path, story, front, self._runs, config)
        else:
            integrate_into_home(result, self._cwd, story_path, story, front, self._runs, close=close)
