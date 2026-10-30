"""The rulebook's use case, wired to delivery's open host service and to the skills' text."""

from __future__ import annotations

import os

from ..rulebook.adapter.outgoing.delivery.delivery_rules import DeliveryRules
from ..rulebook.adapter.outgoing.skills.skill_files import SkillFiles, skills_folder
from ..rulebook.application.show_rulebook import ShowRulebookUseCase

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def show_rulebook(cwd: str) -> ShowRulebookUseCase:
    return ShowRulebookUseCase(DeliveryRules(), SkillFiles(skills_folder(cwd, PACKAGE)))
