"""A request checked against the project's files before it is written, and again before it is worked."""

from __future__ import annotations

import re
import typing

from ...domain.model.correction import REASON_CODES
from ...domain.model.decision_record import RecordId, RecordKind
from ...domain.model.epic import EpicId
from ...domain.model.story import StoryId, StoryStatus
from .decision_record_repository import DecisionRecordRepository, RecordNotFound
from .discovery_reports import DiscoveryReports
from .epic_catalog import EpicCatalog
from .requests import DuplicateRequest, ID_WORD, KIND, PENDING, Request, RequestRefused, written_keys
from .stage_table import StageTable
from .story_repository import StoryNotFound, StoryRepository
from ...domain.model.decision_record import ANSWERED_STATES

Fields = typing.Dict[str, str]


class RequestCheck:
    """What a request names, checked against the files and completed where they name what the person meant — an
    answer's story, an acceptance's record, a proposal's report. RequestRefused with the reason otherwise: a
    malformed request never reaches the factory."""

    def __init__(self, stories: StoryRepository, epics: EpicCatalog, records: DecisionRecordRepository,
                 reports: DiscoveryReports, stages: StageTable) -> None:
        self._stories = stories
        self._epics = epics
        self._records = records
        self._reports = reports
        self._stages = stages

    def checked(self, kind_name: str, given: typing.Optional[typing.Mapping[str, typing.Any]],
                words: typing.Optional[str]) -> typing.Tuple[Fields, str]:
        """(fields, words) as the request will be written."""
        kind = KIND.get(kind_name)
        if kind is None:
            raise RequestRefused(f"no request kind {kind_name!r} — one of: {', '.join(KIND)}")
        fields = {k: str(v).strip() for k, v in (given or {}).items() if v is not None and str(v).strip()}
        words = (words or "").strip()
        stray = sorted(set(fields) - written_keys(kind))
        if stray:
            raise RequestRefused(f"a {kind.name} request takes no {', '.join(stray)}")
        for spec in kind.keys:
            named = [key for key in spec.split("|") if key in fields]
            if not named:
                raise RequestRefused(f"a {kind.name} request names its {' or '.join(spec.split('|'))}")
            if len(named) > 1:
                raise RequestRefused(f"a {kind.name} request names its {' or its '.join(spec.split('|'))}, not both")
        for key, value in fields.items():
            for word in (value.split() if key == "story" and kind.name == "release" else [value]):
                if not ID_WORD.match(word):
                    raise RequestRefused(f"{key}: {word!r} is no id — one word, letters, digits, `.`, `_`, `-`, `#`")
        if kind.words == "required" and not words:
            raise RequestRefused(f"a {kind.name} request carries the person's words")
        if kind.words == "none" and words:
            raise RequestRefused(f"a {kind.name} request takes no words")
        if "\0" in words or len(words) > 20000:
            raise RequestRefused("the words are too long or carry a NUL")
        if kind.name == "release" and "story" in fields and len(fields["story"].split()) == 1 \
                and self._epics.exists(EpicId(fields["story"])):
            fields["epic"] = fields.pop("story")          # `release <id>`: an id that names an epic's folder is the epic
        if "story" in fields:
            for story_id in fields["story"].split():
                self.story(story_id)
        if "epic" in fields and not self._epics.exists(EpicId(fields["epic"])):
            raise RequestRefused(f"no epic {fields['epic']} under {self._epics.where()}/")
        if kind.name == "answer":
            words = self.answer(fields, words)
        if kind.name in ("accept", "correct"):
            self.acceptance(kind.name, fields)
        if kind.name == "epic-from":
            self.proposal(fields)
        if kind.name == "run":
            fields["story"] = self.story(fields["story"]).id.value
            names = self._stages.names()
            if fields.get("from") and fields["from"] not in names:
                raise RequestRefused(f"from: {fields['from']} names no stage ({' '.join(names)})")
        return fields, words

    def against(self, kind_name: str, fields: Fields, words: str, pending: typing.Iterable[Request]) -> None:
        """The checked request against the ones not done: DuplicateRequest where the same waits already; refused
        where a record has another answer queued."""
        wanted: Request = dict(fields, kind=kind_name, words=words)
        deciding = ("answer", "accept", "correct")
        for existing in pending:
            if existing["state"] not in PENDING:
                continue
            if same_request(existing, wanted):
                raise DuplicateRequest(existing["id"])
            # one record takes one answer: a second, different one would only find it answered
            if kind_name in deciding and existing.get("kind") in deciding \
                    and wanted.get("record") and existing.get("record") == wanted.get("record"):
                raise RequestRefused(f"{wanted['record']} has an answer queued already ({existing['id']}) — take that "
                                     "back first (`factory.sh requests --drop`) to answer otherwise")

    def story(self, story_id: str) -> typing.Any:
        try:
            return self._stories.get(StoryId(story_id))
        except StoryNotFound as error:
            raise RequestRefused(str(error)) from None

    def record(self, record_id: str) -> typing.Any:
        try:
            return self._records.get(RecordId(record_id))
        except RecordNotFound as error:
            raise RequestRefused(str(error)) from None

    def answer(self, fields: Fields, words: str) -> str:
        record = self.record(fields["record"])
        if record.kind is RecordKind.ACCEPTANCE:
            raise RequestRefused(f"{fields['record']} asks for an acceptance — accept or correct the story instead")
        if record.state in ANSWERED_STATES:
            raise RequestRefused(f"{fields['record']} is {record.state.value} already — an answer is never "
                                 "overwritten; a change of mind is a new question")
        keys = [option.value for option in record.options]
        named = next((key for key in keys if key.lower() == words.lower()), None)
        if not fields.get("option") and named:
            fields["option"], words = named, ""            # the words name one of the record's options: that option
        offered = (f" — its options: {', '.join(keys)}" if keys else " — it lists none; answer in words")
        # one letter or digit is a key typed: a wrong one is refused, never written as an answer in words ("no" is one)
        if not fields.get("option") and re.fullmatch(r"[A-Za-z0-9]", words or "-"):
            raise RequestRefused(f"{fields['record']} has no option {words!r}" + offered)
        if not fields.get("option") and not words:
            raise RequestRefused(f"an answer names an option{' (' + ', '.join(keys) + ')' if keys else ''} "
                                 "or carries the person's words")
        if fields.get("option") and fields["option"].lower() not in {key.lower() for key in keys}:
            raise RequestRefused(f"{fields['record']} has no option {fields['option']!r}" + offered)
        fields["record"] = record.id.value
        if record.story is not None:
            fields["story"] = record.story.value
        return words

    def acceptance(self, name: str, fields: Fields) -> None:
        story = self.story(fields["story"])
        fields["story"] = story.id.value
        record = self._records.open_acceptance_of(story.id)
        if record is not None:
            fields["record"] = record.id.value
        elif name == "accept":
            raise RequestRefused(f"{fields['story']} waits for no acceptance — nothing to accept")
        elif story.status is not StoryStatus.DELIVERED:
            raise RequestRefused(f"{fields['story']} neither waits for an acceptance nor is delivered — a change "
                                 "before is the backlog's: a wish")
        if name == "correct" and fields.get("option") and fields["option"].lower() not in REASON_CODES:
            raise RequestRefused(f"a correction's code is one of {', '.join(REASON_CODES)} — not {fields['option']!r}")

    def proposal(self, fields: Fields) -> None:
        report = self._reports.report_of(fields["topic"])
        if not report:
            raise RequestRefused(f"no discovery report for topic {fields['topic']} — `factory.sh discover --list`")
        proposals = self._reports.proposals_in(report)
        if fields["proposal"] not in proposals:
            raise RequestRefused(f"{report} proposes no {fields['proposal']}"
                                 + (f" — it proposes {', '.join(proposals)}" if proposals else ""))
        if self._epics.exists(EpicId(fields["proposal"])):
            raise RequestRefused(f"{fields['proposal']} is an epic already")
        fields["report"] = report


def same_request(one: Request, other: Request) -> bool:
    keys = ("kind", "story", "epic", "record", "topic", "proposal", "option", "from")
    return all(str(one.get(k) or "") == str(other.get(k) or "") for k in keys) and one["words"] == other["words"]
