"""The kind of question a stage asks: one word from a short list the factory keeps, used for counting alone."""

from __future__ import annotations

import enum
import typing

from .story_words import Detail


class QuestionTag(enum.Enum):
    """What a question is about, in one word. The asking stage writes it (`tag:` in the record) and the gate checks
    it is one of these. It counts the same kind of question across stories, so a question asked again and again
    becomes a lesson; it never answers a question, nor says that a new one is like an old one."""

    SCOPE = "scope"
    BEHAVIOUR = "behaviour"
    DOMAIN_TERM = "domain-term"
    DOMAIN_BOUNDARY = "domain-boundary"
    FAILURE = "failure"
    TEST_LEVEL = "test-level"
    TEST_DATA = "test-data"
    PAGE_LAYOUT = "page-layout"
    PERSISTENCE = "persistence"
    INTEGRATION = "integration"
    DEPENDENCY = "dependency"
    MERGE_ORDER = "merge-order"
    OTHER = "other"

    @classmethod
    def written(cls, word: Detail) -> typing.Optional[QuestionTag]:
        """The tag a record's `tag:` names — any case, surrounding spaces and back ticks ignored; None for none of the
        list."""
        said = word.value.strip().strip("`").strip().lower()
        return next((tag for tag in cls if tag.value == said), None)

    @classmethod
    def listed(cls) -> Detail:
        """The list as a stage reads it: `scope`, `behaviour`, … in the order kept here."""
        return Detail(", ".join(f"`{tag.value}`" for tag in cls))
