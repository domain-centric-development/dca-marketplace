"""The runner's questions to the cli wired: the stage table and the profile's answers — and nothing else, so a
question does not import the whole delivery context first (`question_command`)."""

from __future__ import annotations

from ..delivery.adapter.outgoing.tools.runner_table_files import RunnerTableFiles
from ..delivery.application.delivery.show_stage_table import ShowStageTableUseCase
from .profile import ask_profile as ask_profile


def show_stage_table() -> ShowStageTableUseCase:
    return ShowStageTableUseCase(RunnerTableFiles())
