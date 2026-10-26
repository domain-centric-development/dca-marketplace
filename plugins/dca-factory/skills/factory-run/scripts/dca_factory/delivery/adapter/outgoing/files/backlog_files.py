"""The backlog as the project keeps it: the story files under the epics, the epics' graph, the stages the journals
show running — and the main line, asked through git."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .migrations import layout_hint
from ..pipeline.stage_rows import STAGE_FILES
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    factory_home, PROFILE_FILE, read_profile, resolve_profile, shown)
from ....application.shared.backlog_facts import BacklogStory, OpenStage
from ....application.status.texts import parse_time
from ....domain.model.schedule import EpicGraph
from ....domain.model.story import StoryId
from ....domain.model.story_state import Detail, Standing, StateName
from ....domain.service.scheduling import Scheduling
from ..git.repository import git
from ..git.worktrees import has_worktree, uncommitted_story
from .epic_files import epic_graph, graph_of
from .owned_files import run_owned
from .run_marks import running_stages, stale_after, story_title
from .snapshots import DELETED, tree_snapshot
from .story_facts_files import StoryFactsFiles
from .story_layout import (
    delivered_on, depends_on, duplicate_ids, epic_folder, story_files, story_folder, story_kind)

#: What people write and the pipeline installs: a change there is not code a story left behind.
PEOPLE_OWNED = ("product/", "project/", ".agents/", ".claude/", ".codex/", ".opencode/", ".githooks/", "docs/")


def stopped(why: str) -> Standing:
    return Standing(StateName.STOPPED, None, Detail(why))


class BacklogFiles:
    """The backlog under <epics>, its runs under <runs>, in the checkout <cwd>."""

    def __init__(self, cwd: str, epics: str, runs: str) -> None:
        self.cwd, self.folder, self.runs = cwd, epics, runs
        self.home = factory_home() or cwd

    def stories(self) -> typing.Sequence[BacklogStory]:
        found = []
        twice = duplicate_ids(self.folder)
        for path in story_files(self.folder):
            name = os.path.basename(story_folder(path))
            epic = os.path.basename(epic_folder(path))
            try:
                front, body = read_front_matter(path)
            except GateError as error:
                found.append(BacklogStory(name, path, epic, {}, "", "", None, (), "", False, False, None,
                                          stopped(str(error))))
                continue
            story_id = str(front.get("id") or name).strip()
            title, kind = story_title(front, body), story_kind(front)
            others = [Detail(shown(p)) for p in twice.get(story_id.lower(), [])
                      if os.path.normpath(p) != os.path.normpath(path)]
            twin = Scheduling.twin(StoryId(story_id), others)
            if twin is not None:
                found.append(BacklogStory(
                    f"{story_id} ({shown(path)})", path, epic, front, body, title, kind, (), "", False, False, None, twin))
                continue
            found.append(BacklogStory(
                story_id, path, str(front.get("epic") or epic).strip(), front, body, title, kind,
                tuple(depends_on(front)), str(front.get("context", "")).strip(),
                os.path.isfile(os.path.join(self.runs, story_id, STAGE_FILES["test"])),
                has_worktree(story_id, self.home), StoryFactsFiles(self.cwd, self.runs, story_id, front, path)))
        return found

    def epics(self) -> EpicGraph:
        return graph_of(epic_graph(self.folder))

    def open_stages(self) -> typing.Sequence[OpenStage]:
        return [OpenStage(story, stage, started) for story, stage, started in running_stages(self.runs)]

    def main_line(self, stories: typing.Sequence[BacklogStory]) -> MainLineGit:
        return MainLineGit(self.cwd, self.home, self.runs, stories)

    def hint(self) -> typing.Optional[str]:
        return layout_hint(self.cwd, read_profile(resolve_profile(None, self.cwd)))

    def stale_after(self) -> int:
        return stale_after()


class MainLineGit:
    """The main line as git has it, for the stories of the backlog."""

    def __init__(self, cwd: str, home: str, runs: str, stories: typing.Sequence[BacklogStory]) -> None:
        self.cwd, self.home, self.runs = cwd, home, runs
        self.paths = {StoryId(s.key): s.path for s in stories}
        self.fronts = [s.front for s in stories]

    def uncommitted(self, story: StoryId) -> typing.Optional[Detail]:
        why = uncommitted_story(self.home, self.paths[story])
        return Detail(why) if why else None

    def stray(self) -> typing.Tuple[Detail, ...]:
        """Code changed in the checkout that no story's run folder claims — a run folder removed while a story was
        past its plan, or a person's work in progress. Neither is something to start the next story on top of.
        Not read as that: a story delivered after HEAD was committed (its code waits for its commit, the normal
        state), and a project without a commit, where nothing can be compared."""
        code, stamp = git(self.cwd, "log", "-1", "--format=%cI")
        committed = parse_time(stamp.strip()) if code == 0 else None
        if not committed:
            return ()
        for front in self.fronts:
            delivered = parse_time(delivered_on(front or {}))
            if delivered and delivered > committed:
                return ()
        snapshot = tree_snapshot(self.cwd) or {}
        fixed = (PROFILE_FILE, "AGENTS.md", "CLAUDE.md", ".gitignore", ".gitattributes")
        # A file that is gone is no code to build on — and a move (the migration's, a person's) reads as a
        # deletion at its origin and an addition where it now is, which the places above already judge.
        return tuple(Detail(path) for path in sorted(
            path for path, digest in snapshot.items()
            if digest != DELETED and not run_owned(path, self.runs) and not path.startswith(PEOPLE_OWNED)
            and path not in fixed))
