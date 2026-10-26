"""Which of a story's hand-overs belong to its current pass — read from the journal's order, never from file times."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..model.journal_marks import JournalMarks, MarkKind, MarkName, Seq
from ..model.stage import PIPELINE, StageName, Trait


class CurrentPass(DomainService):
    """A stage run again makes every later hand-over an earlier pass's."""

    @staticmethod
    def written_at(marks: JournalMarks, stage: StageName) -> typing.Optional[Seq]:
        """When the stage's file last held for the pass: its last write, or for a stage gated after its file a later
        pass (or hold) of its own gate; None where the file was marked an earlier pass's since."""
        row = next((s for s in PIPELINE if s.name == stage), None)
        if row is None or row.hand_over is None:
            return None
        name = MarkName(row.hand_over.value)
        at = marks.at(MarkKind.WROTE, name).value
        if Trait.POST_GATED in row.traits:
            gate = MarkName(stage.value)
            at = max(at, marks.at(MarkKind.PASS, gate).value, marks.at(MarkKind.HELD, gate).value)
        outdated = marks.has(MarkKind.OUTDATED, name)
        return None if outdated is not None and outdated.value > at else Seq(at)

    @staticmethod
    def holding(marks: JournalMarks, order: typing.Sequence[StageName],
                present: typing.AbstractSet[StageName]) -> typing.Tuple[StageName, ...]:
        """The stages, in run order, whose file on disk holds for the current pass: up to the first that is older
        than one before it — a stage that ran again ended the pass the later files were written in. A stage whose
        gate passed after the file before it was written holds, though its own file is older."""
        holding: typing.List[StageName] = []
        newest: typing.Optional[int] = None
        for stage in order:
            if stage not in present:
                continue
            written = CurrentPass.written_at(marks, stage)
            if written is None or (newest is not None and written.value < newest):
                break
            holding.append(stage)
            newest = max(written.value, newest or 0)
        return tuple(holding)
