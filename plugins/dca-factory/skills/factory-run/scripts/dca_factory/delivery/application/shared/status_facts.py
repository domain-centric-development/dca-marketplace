"""What the status reads: the facts of the project's files, the schedule and the factory's processes — raw, as they
are written; what they mean for a person is the read model's."""

from __future__ import annotations

import datetime
import typing

from ....building_blocks import OutputPort

Facts = typing.Dict[str, typing.Any]


class StatusFacts(OutputPort, typing.Protocol):
    """The project as the status reads it."""

    def now(self) -> datetime.datetime:
        """This moment, in UTC."""
        ...

    def project_name(self) -> str:
        ...

    def profile(self) -> typing.Dict[str, str]:
        ...

    def schedule(self) -> Facts:
        """The schedule: `stories` by id (state, start, detail, path, front, body, title, epic …), their `order`,
        the `next` story, the `reason` nothing runs, a layout `hint`."""
        ...

    def story_facts(self, story_id: str, front: typing.Optional[Facts]) -> Facts:
        """What the story's journal says: started, delivered, stages, passes, tokens, seconds, cost."""
        ...

    def story_records(self, story_id: str, path: typing.Optional[str]) -> typing.List[typing.Tuple[typing.Any, ...]]:
        """The story's decision records: (path, front, body, state, answer)."""
        ...

    def decision_files(self) -> typing.List[typing.Tuple[typing.Any, ...]]:
        """Every record, beside the stories and the project's own: (name, front, body, state, error, path)."""
        ...

    def has_journal(self, story_id: str) -> bool:
        ...

    def flaky_tests(self, story_id: str) -> typing.List[str]:
        ...

    def story_signals(self, story_id: str, records: typing.List[typing.Tuple[typing.Any, ...]], body: str) -> Facts:
        ...

    def running_stages(self) -> typing.List[typing.Tuple[str, str, str]]:
        """(story, stage, started) of every stage the journals show running."""
        ...

    def shared_windows(self) -> typing.Mapping[str, typing.Tuple[str, ...]]:
        """The shared processes that carry several stages, with the stages each carries."""
        ...

    def window_part(self, story_id: str, window: str) -> str:
        """The stage a running shared window is in — '' before it loaded one."""
        ...

    def story_round(self, story_id: str) -> int:
        ...

    def claim(self) -> typing.Optional[Facts]:
        """Who holds the checkout: {owner, since, beat}, or None."""
        ...

    def activity(self, owner: str, started: str, now: datetime.datetime, story_id: str) -> str:
        """The sign of life inside a running stage: `activity: <age> — <what>`."""
        ...

    def epic_files(self) -> typing.List[Facts]:
        """Every epic folder with its `epic.md`: epic, folder, created, path, title, goal, metric, discovery, intent,
        domain_contact."""
        ...

    def story_kind(self, path: str) -> str:
        """The kind of the story at <path> — `story` where its file cannot be read."""
        ...

    def epic_text(self, story_path: str) -> str:
        """The `epic.md` of the epic the story lies in, '' where there is none."""
        ...

    def worker(self) -> typing.Optional[Facts]:
        """The worker: {owner, since, beat, how, pid, alive, log, by, stopping}, or None."""
        ...

    def ended(self) -> typing.Optional[Facts]:
        """The factory `up` started that is gone without a `down`: {at, why, log}, or None."""
        ...

    def listener(self) -> typing.Optional[str]:
        """`listening: …` — the session that looked at the backlog last — or None."""
        ...

    def dangling_skill_links(self) -> typing.List[str]:
        """The entries of the tools' skill folders that link to nothing, as paths from the project root."""
        ...

    def duplicate_pipeline_note(self) -> typing.Optional[str]:
        ...

    def findings_name(self) -> str:
        """The file a story keeps its open findings in, beside its story file."""
        ...

    def finding_records(self) -> typing.List[Facts]:
        ...

    def perspectives(self, profile: typing.Dict[str, str]) -> typing.List[typing.Tuple[str, str]]:
        ...

    def foreign_claims(self) -> typing.List[Facts]:
        """The claims other factories hold, each with what this checkout has under its id: `here` (False where it
        has no such story), `epic` and `title` of its own story."""
        ...

    def shown(self, path: str) -> str:
        """A path as a person reads it."""
        ...

    def names_story(self, word: str) -> bool:
        """Whether one word is a story's id."""
        ...
