"""What a person can do, every way: in an agent session (`skill`), in a terminal (`shell`), from a page (`request`).

An action is decided here and drawn by every view — its words, its label, whether it is the one to press, and the
request a press writes (WP-91)."""

from __future__ import annotations

import re
import typing

from ...domain.model.correction import REASON_CODES
from ...domain.model.run_argument import ArgumentMeaning, RunArgument
from ...domain.model.story import StoryId
from ..shared.requests import ID_WORD

#: A request as an action offers it: {kind, fields, words, open} — `open` names what the person still has to give.
Offer = typing.Dict[str, typing.Any]
#: An action as a view draws it.
Action = typing.Dict[str, typing.Any]
#: Whether one word is a story's id.
NamesStory = typing.Callable[[str], bool]

#: The runner as a terminal starts it in a project.
RUNNER = "bash .agents/factory/factory.sh"


def make_action(names_story: NamesStory, text: str = "", skill: str = "", shell: str = "", look: str = "",
                label: str = "", primary: bool = False) -> Action:
    """What to do, every way: `skill` in an agent session, `shell` in a terminal — empty where a
    terminal cannot do it (writing a story needs an agent) —, and `request` from a page. `label` is the
    word on its button and `primary` marks the one to press: a view draws them, it never chooses them."""
    action: Action = dict(text=text, skill=skill, shell=shell, look=look, label=label, primary=primary)
    request = request_of(skill, names_story)        # the same press from a page: the request it writes (WP-91)
    if request:
        action["request"] = request
    return action


def offered(*actions: typing.Optional[Action]) -> typing.List[Action]:
    """The actions a page can press — those a request does — in the order given."""
    return [a for a in actions if a and a.get("request")]


def entry_actions(names_story: NamesStory) -> typing.Dict[str, Action]:
    """Where a person starts something in their own words: a wish, a change to the description, a discovery."""
    return dict(
        wish=make_action(names_story, text="What should the product do that it does not do yet?",
                         skill="/factory-backlog", label="wish", primary=True),
        describe=make_action(names_story, text="e.g. tech: the shop runs on PostgreSQL 17", skill="/dca-describe",
                             label="describe", primary=True),
        discover=make_action(names_story, text="What problem is worth solving, or what should exist?",
                             skill="/factory-discover", label="discover", primary=True))


def request_of(skill: typing.Optional[str], names_story: NamesStory) -> typing.Optional[Offer]:
    """The request that does what a view's action does in a session — `/factory-run <story>`, `/factory-backlog …`,
    `/factory-decisions <story> <record>: answer <key>`, `/dca-describe <change>`, `/factory-discover <words>` — as
    {kind, fields, words, open}: `open` names what the person still has to give (words, an option). None for an
    action no request does (setting the factory up, updating it, a verification). <names_story> says whether a word
    is a story's id."""
    text = " ".join(str(skill or "").split())
    head, _, rest = text.partition(" ")
    if head == "/factory-run":
        # as the skill reads it (`RunArgument`): a story's id runs that story, more words are a wish; a button that
        # names one word no story has offers it as a wish, since a page writes the words it offers itself
        argument = RunArgument(rest)
        meaning = argument.meaning(StoryId(rest) if argument.single_word() and names_story(rest) else None)
        if meaning is ArgumentMeaning.BACKLOG:
            return None
        return dict(kind="run", fields=dict(story=rest), words="", open="") if meaning is ArgumentMeaning.STORY \
            else dict(kind="wish", fields={}, words=rest, open="")
    if head == "/factory-backlog":
        verb, _, tail = rest.partition(" ")
        if verb == "release" and tail:
            return dict(kind="release", fields=dict(story=tail), words="", open="")
        if verb in ("stories", "journey") and ID_WORD.match(tail or "-"):
            return dict(kind=verb, fields=dict(epic=tail), words="", open="")
        match = re.match(r"^epic (\S+) --from (\S+)$", rest)
        if match:
            folders = match.group(2).replace("\\", "/").split("/")
            topic = folders[-2] if len(folders) > 1 else ""         # the report's folder: its topic
            return dict(kind="epic-from", fields=dict(topic=topic, proposal=match.group(1)), words="", open="")
        return dict(kind="wish", fields={}, words=rest, open="" if rest else "words")
    if head == "/factory-decisions":
        # `<story> <record>: answer <words>`, `<record>: answer` (the words still to give), and at an acceptance
        # `answer accepted` or `answer correction` — which name the story, its record the factory finds itself
        match = re.match(r"^(?:(\S+) )?(\S+): answer(?: (.+))?$", rest)
        if match:
            story, record, given = match.group(1) or match.group(2), match.group(2), match.group(3) or ""
            if given == "accepted":
                return dict(kind="accept", fields=dict(story=story), words="", open="")
            if given in ("correction", "correction:"):
                return dict(kind="correct", fields=dict(story=story), words="", open="words",
                            choices=list(REASON_CODES))
            return dict(kind="answer", fields=dict(record=record), words=given, open="" if given else "words")
        story = rest.split()[0] if rest else ""
        return dict(kind="answer", fields=dict(story=story) if story else {}, words="", open="record")
    if head == "/dca-describe":
        return dict(kind="describe", fields={}, words=rest, open="" if rest else "words")
    if head == "/factory-discover":
        return dict(kind="discover", fields={}, words=rest, open="" if rest else "words")
    return None
