"""The stack profile checked on its own, outside a story: the contract the gate reads it as with the keys nobody reads,
and the model keys against the workflow's stages."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.gateway.stage_evidence import StageEvidence
from ...domain.model.verdict import Findings
from ...domain.service.profile_checks import ProfileChecks
from ..delivery.pipeline_workflow import workflow


@dataclasses.dataclass(frozen=True)
class CheckProfileQuery:
    """No input: the profile is the evidence's."""


@dataclasses.dataclass(frozen=True)
class ProfileChecked:
    """The findings over the contract and the unknown keys, and over the model keys."""

    contract: Findings
    models: Findings


class CheckProfileInputPort(UseCase[CheckProfileQuery, ProfileChecked], typing.Protocol):
    """The profile checked on its own."""


class CheckProfileUseCase(CheckProfileInputPort):
    def __init__(self, evidence: StageEvidence) -> None:
        self._evidence = evidence

    def execute(self, query: CheckProfileQuery) -> ProfileChecked:
        evidence = self._evidence
        contract = evidence.gate().profile_findings(evidence.declared_contract(), evidence.unknown_keys())
        return ProfileChecked(contract, ProfileChecks.models(evidence, workflow()))
