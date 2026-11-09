"""The installer: the pipeline put into the project in its root folder and kept up to date, each step saying what it did
as `factory.sh setup` and `update` always said it. What it asks of the profile it asks the cli's command line in this
process (<cli>), as the runner it was once asked as a process."""

from __future__ import annotations

import os
import subprocess
import sys
import typing

from ....application.shared.pipeline_install import (
    InstallStopped, PipelineInstall, ProfileOutcome, Proposal, SkillMode, Stop)
from ..files.pipeline_digest import STAMP
from ..stack.commands import posix_shell
from . import presets as detection
from .project_files import GATE, agents_block, claude_permissions, copy_pipeline, hooks_path, project_ignores
from .skill_folders import (InstallFailed, SkillFolder, can_symlink, makedirs, must, prune_renamed_copies,
                            skills_mode, warn, write_skill_ignores)
from .sources import (GATE_IN_SKILLS, RENAMED_KEYS, RENAMED_SKILLS, gate_field, inside, later, method_skill_names,
                      plugin_skills, presets_dir, source_kind)

PROFILE = "dca-factory.profile.yaml"          # at the project root: the person's, committed; the one fixed path

#: The cli's command line in this process: its exit, what it printed and what it said on stderr — or both in
#: their order in the second, where it is asked to merge them.
Cli = typing.Callable[[typing.Sequence[str], bool], typing.Tuple[int, str, str]]


class ToolFolder(typing.NamedTuple):
    tool: str
    folder: str
    plugins: bool


def stamped(field: str) -> str:
    """A line of the installed stamp, "" without it."""
    try:
        with open(STAMP, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(f"{field}:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def runner_folder() -> str:
    """The folder this runner's entry points are in — the package's parent."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))


def evidence_of(runs: str) -> str:
    """The evidence folder beside the run folder, relative to the checkout."""
    parent = os.path.dirname(runs) or "."
    return f"{'.dca-factory' if parent == '.' else parent}/evidence"


def gate_freshness(own: str, tool_dirs: typing.Sequence[str]) -> None:
    """Whether the gate in this project is still the one the pipeline ships: a difference in VERSION is an update to
    run, never a reason to refuse a story; an incompatible contract is refused by the gate, against the profile."""
    if not os.path.isfile(STAMP):
        return
    skills = plugin_skills(own, tool_dirs)
    if not skills:
        return
    source = os.path.join(skills, GATE_IN_SKILLS)
    installed_version, installed_contract = stamped("version"), stamped("contract")
    source_version = gate_field(source, "VERSION")
    if source_version is None:
        return
    source_contract = gate_field(source, "CONTRACT") or ""
    # a pipeline older than the installed one (an old plugin cache) is nothing to update to
    if later(installed_version, source_version) != source_version:
        return
    if installed_contract != source_contract:
        warn(f"factory: this project was installed against file contract {installed_contract} and the")
        warn(f"factory:   pipeline here implements {source_contract} — run 'factory.sh update' and check")
        warn("factory:   the stack profile's 'contract:' line before trusting a run.")
    elif installed_version != source_version:
        warn(f"factory: this project was installed from pipeline {installed_version}, the one here is")
        warn(f"factory:   {source_version} — same file contract, so the run is valid; 'factory.sh update'")
        warn("factory:   brings the project up to date.")


class PipelineInstaller(PipelineInstall):
    """The installer for one call of `factory.sh`, run by <python> (the name that reaches the profile and the allow
    list), its runner in <own> (the skill folder it belongs to), the tools' skill folders as the records name them."""

    def __init__(self, python: str, own: str, folders: typing.Sequence[ToolFolder], cli: Cli, runs: str) -> None:
        self.python, self.own, self.folders, self.cli, self.runs = python, own, list(folders), cli, runs

    # --- what the steps read --------------------------------------------------------------------------------------
    def tool_dirs(self) -> typing.List[str]:
        return [entry.folder for entry in self.folders]

    def found(self) -> typing.Optional[str]:
        return plugin_skills(self.own, self.tool_dirs())

    def carriers(self) -> typing.List[str]:
        return self.cli(["--carriers"], False)[1].split()

    def presets(self, folder: typing.Optional[str], mode: str, *rest: str) -> int:
        names = method_skill_names(folder or "", self.own, self.tool_dirs())
        return detection.run(detection.Detection(folder or "", self.python, detection.conventions_file(), names),
                             mode, rest)

    def skill_folder(self, folder: str, source: str, adopt: typing.Sequence[str] = ()) -> SkillFolder:
        return SkillFolder(folder, source, source_kind(source), self.holds_plugins(folder), self.carriers, adopt)

    # --- the port --------------------------------------------------------------------------------------------------
    def install_source(self, named: typing.Optional[str]) -> str:
        source = named
        if not source:
            source = self.own if os.path.isfile(os.path.join(self.own, GATE_IN_SKILLS)) else self.found()
            if not source:
                warn("factory: no pipeline found to install from — pass --from <the plugin's skills folder>")
                raise InstallStopped(Stop.REFUSED)
        return os.path.abspath(source)

    def update_source(self, named: typing.Optional[str]) -> str:
        source, found = named, False
        if not source:
            source, found = self.found(), True
            if not source:
                warn("factory: no pipeline found to update from — pass --from <the plugin's skills folder>")
                raise InstallStopped(Stop.REFUSED)
        if not os.path.isfile(os.path.join(source, GATE_IN_SKILLS)):
            warn(f"factory: {source} is not the pipeline's skills folder (no factory-run/scripts/story-gate.py)")
            raise InstallStopped(Stop.REFUSED)
        source = os.path.realpath(source)
        # The newest pipeline found can still be older than the installed one — an old plugin cache on a machine whose
        # project was installed from a checkout. Updating to it is a silent downgrade, so a source found is refused
        # there; a source the person names with --from is what they asked for.
        have, offered = stamped("version"), gate_field(os.path.join(source, GATE_IN_SKILLS), "VERSION") or ""
        if found and have and offered and have != offered and later(have, offered) == have:
            warn(f"factory: the newest pipeline found is {offered} ({source}), older than the installed {have} —")
            warn(f"factory:   an update would go back. Name the source: --from <the dca-factory {have} or newer>/skills")
            warn("factory:   (or FACTORY_PLUGIN_DIR); nothing was changed")
            raise InstallStopped(Stop.REFUSED)
        # The project's own skills are what an update replaces, never where it comes from: linked onto themselves they
        # become loops. A folder of links names the pipeline through its factory-run link.
        root = os.path.realpath(os.getcwd())
        if inside(source, root):
            source = os.path.dirname(os.path.realpath(os.path.join(source, "factory-run")))
        if inside(source, root):
            warn(f"factory: {source} lies inside this project — update from the plugin's skills folder "
                 "(--from <plugin>/skills, or FACTORY_PLUGIN_DIR); nothing was changed")
            raise InstallStopped(Stop.REFUSED)
        return source

    def runner_of(self, source: str) -> typing.Optional[str]:
        newest = os.path.join(source, "factory-run", "scripts", "factory.sh")
        this = os.path.join(os.path.realpath(runner_folder()), "factory.sh")
        if os.environ.get("FACTORY_UPDATE_HANDED") or not os.path.isfile(newest) or this == newest:
            return None
        return newest

    def hand_over(self, runner: str, mode: typing.Optional[SkillMode], adopt: typing.Sequence[str], source: str) -> int:
        # forward slashes: the paths as bash reads them on every platform (`C:/…` under Git Bash)
        argv = [posix_shell() or "bash", runner.replace(os.sep, "/"), "update", "--from", source.replace(os.sep, "/")]
        argv += ["--copy"] if mode is SkillMode.COPY else ["--link"] if mode is SkillMode.LINK else []
        argv += ["--adopt", " ".join(adopt)] if adopt else []
        sys.stdout.flush()
        sys.stderr.flush()
        return subprocess.run(argv, env=dict(os.environ, FACTORY_UPDATE_HANDED="1")).returncode

    def tool_folders(self, tool: str) -> typing.Optional[typing.List[str]]:
        if tool == "all":
            return self.tool_dirs()
        if tool == "none":
            return []
        named = [entry.folder for entry in self.folders if entry.tool == tool]
        return named or None

    def tools(self) -> typing.List[str]:
        return [entry.tool for entry in self.folders]

    def holds_plugins(self, folder: str) -> bool:
        return any(entry.plugins and entry.folder == folder for entry in self.folders)

    def skills_mode(self, folder: str) -> typing.Optional[SkillMode]:
        mode = skills_mode(folder)
        return SkillMode(mode) if mode in ("link", "copy") else None

    def cache_source(self, source: str) -> bool:
        return source_kind(source) == "cache"

    def can_link(self) -> bool:
        return can_symlink()

    def prepare(self, source: str) -> None:
        self.must_do(lambda: must("create .agents/factory and .githooks",
                                  makedirs(".agents/factory") and makedirs(".githooks")))
        # An older layout first — the profile under .agents/factory/, product/backlog/, a decisions store, run
        # artefacts under tasks/ — so the profile below is found where it now lives and not written twice.
        _code, out, err = self.cli(["--migrate-layout"], False)
        for line in out.splitlines():
            if not line.startswith("migrate: nothing to move"):
                print(line.replace("migrate: ", "factory: migrated ", 1) if line.startswith("migrate: ") else line)
        if err:
            warn(err.rstrip("\n"))
        if not os.path.isfile(PROFILE):
            # Prefilled from what the project already states, so the profile is not a second truth.
            folder = presets_dir(source, self.own, self.tool_dirs())
            template = os.path.join(source, "factory-run", "templates", "factory.profile.yaml.tmpl")
            self.must_do(lambda: must("write the stack profile", self.presets(folder, "new", template, PROFILE) == 0))

    def must_do(self, step: typing.Callable[[], None]) -> None:
        """A step that had to work: where it did not, said, and nothing more changes."""
        try:
            step()
        except InstallFailed as failed:
            warn(f"factory: could not {failed.what} — install aborted, the project is unchanged from here on.")
            raise InstallStopped(Stop.FAILED)

    def fill(self, folder: str, source: str, mode: SkillMode, reason: str, adopt: typing.Sequence[str]) -> None:
        # An older install linked the whole folder to the pipeline's. Through that link every write below would land
        # in the plugin's own folder — so the link goes first, and the folder holds one entry per skill from here on.
        if os.path.islink(folder):
            def unlinked() -> None:
                try:
                    os.unlink(folder)
                    done = True
                except OSError:
                    done = False
                must(f"replace the {folder} link", done)
            self.must_do(unlinked)
        skills = self.skill_folder(folder, source, adopt)
        if mode is SkillMode.COPY:
            self.must_do(lambda: skills.copy(reason))
        else:
            self.must_do(skills.link)

    def refresh_carriers(self, folder: str, source: str, mode: SkillMode) -> None:
        if os.path.isdir(folder) and not os.path.islink(folder):
            self.skill_folder(folder, source).refresh_carriers(mode is SkillMode.COPY)

    def write_ignores(self, folder: str, mode: SkillMode) -> None:
        write_skill_ignores(folder, mode.value)

    def copy_pipeline(self, source: str) -> None:
        self.governance(source)
        self.must_do(lambda: copy_pipeline(source))
        hooks_path()

    def governance(self, source: str) -> None:
        """The factory delivers stories; it does not install an architecture. That is the method's setup skill's job,
        and it runs once. Said instead of quietly starting without one. What counts as governance is the
        `governance` presets' — a rule package or an architecture test."""
        folder = presets_dir(source, self.own, self.tool_dirs())
        found = False
        if folder:
            names = method_skill_names(folder, self.own, self.tool_dirs())
            try:
                found = detection.Detection(folder, self.python, detection.conventions_file(), names).detect()[2]
            except detection.PresetError as failed:
                warn(str(failed))
        if found:
            print("factory: architecture governance found — the pipeline has something to gate on.")
        else:
            warn("factory: no architecture governance found in this project.")
            warn("factory: run the method's setup skill first (in a DCA project /dca-init) — it adds the building")
            warn("factory:   blocks and the rule catalog, and it is what the build gate checks against.")
            warn("factory: installing the pipeline anyway; its architecture check will be skipped and named.")

    def allow_commands(self) -> None:
        claude_permissions(self.python, self.cli(["--command-heads"], False)[1].split())

    def project_lines(self) -> None:
        project_ignores(self.runs, evidence_of(self.runs))
        # The story journals are the stories' record and are committed (WP-150): the folder's ignore lets them in.
        _code, out, err = self.cli(["--ignore-journals"], True)
        for line in out.splitlines():
            print(line.replace("journals: ", "factory: ", 1) if line.startswith("journals: ") else line)
        agents_block()

    def closing(self, folders: typing.Sequence[str], source: str, mode: SkillMode) -> None:
        if mode is SkillMode.COPY:
            print("factory: the skills are copies — commit .claude/.codex/.opencode skills with the project, and")
            print("factory:   every clone delivers stories with this pipeline, without the marketplace "
                  "('factory.sh update' refreshes them).")
        elif folders:
            print(f"factory: the skill links point into {source} — kept out of git; a clone gets them")
            print("factory:   with 'factory.sh update', or use --copy to commit the skills with the project.")
            if self.cache_source(source):
                warn("factory: that source is a plugin cache: its versions are removed some time after an update, and "
                     "the")
                warn("factory:   links then point nowhere until 'factory.sh update' — 'setup --copy' or 'update --copy' "
                     "avoids it.")
        for folder in folders:
            if self.holds_plugins(folder):
                print("factory: with the dca-factory plugin enabled, Claude Code lists these skills a second time as")
                print("factory:   dca-factory:<skill>; the project's entry is the one a session and a runner stage use.")

    def installed(self) -> bool:
        return os.path.isfile(GATE) and os.path.isfile(".agents/factory/factory.sh")

    def stamp(self) -> typing.Tuple[str, str]:
        return stamped("version"), stamped("contract")

    def version_of(self, source: typing.Optional[str]) -> str:
        return gate_field(os.path.join(source, GATE_IN_SKILLS) if source else GATE, "VERSION") or ""

    def tool_source(self, named: typing.Optional[str]) -> typing.Optional[str]:
        source = named or self.own
        if not os.path.isfile(os.path.join(source, GATE_IN_SKILLS)):
            return self.found()
        return source

    def prune_renamed(self, source: str) -> None:
        prune_renamed_copies(source, self.tool_dirs())

    def profile_renames(self) -> typing.List[str]:
        """The profile lines that name a renamed skill or key, as "<old line> → <new line>"."""
        keys, skills = dict(RENAMED_KEYS), {old: new for old, new, _plugin in RENAMED_SKILLS}
        found = []
        for line in self.cli(["--carrier-lines"], False)[1].splitlines():
            words = line.split()
            if not words:
                continue
            key, value = words[0], words[1] if len(words) > 1 else ""
            new_key, new_value = keys.get(key, key), skills.get(value, value)
            if f"{key}: {value}" != f"{new_key}: {new_value}":
                found.append(f"{key}: {value} → {new_key}: {new_value}")
        return found

    def updated(self, before: typing.Tuple[str, str], source: str) -> None:
        renames = self.profile_renames()
        if renames:
            warn("factory: the profile names skills by their old names — the update writes nothing into it; change:")
            for rename in renames:
                warn(f"factory:   {rename}")
        after, after_contract = gate_field(GATE, "VERSION") or "", gate_field(GATE, "CONTRACT") or ""
        print(f"factory: updated {before[0] or 'an unstamped install'} → {after} (file contract {before[1] or '?'} → "
              f"{after_contract}) from {source}")
        # When each story and epic was written orders the backlog, newest first: filled once from git where it is
        # missing, never over a value there.
        _code, out, err = self.cli(["--backfill-created"], True)
        for line in out.splitlines():
            print(line.replace("backfill: ", "factory: ", 1) if line.startswith("backfill: ") else line)
        declared = self.cli(["--get", "contract"], False)[1].rstrip("\n")
        if declared and declared != after_contract:
            warn(f"factory: the stack profile declares contract {declared} — raise it to 'contract: {after_contract}' "
                 "once")
            warn("factory:   the profile uses what that contract describes; the gate reads it as older until then.")
        # without `release:` a story without `status:` is still delivered, and a draft by hand — said, never written
        if not self.cli(["--get", "release"], False)[1].strip("\n"):
            warn("factory: the stack profile has no 'release:' — add 'release: required' to deliver only what a person")
            warn("factory:   released (a draft, or a story without status:, never — by the gate or by hand).")
        # an older layout (`project/`, `project/backlog/`, …) is not read by the new gate; the move is said here as well
        for line in self.cli(["--schedule"], False)[1].splitlines():
            if line.startswith("layout: "):
                warn("factory: " + line[len("layout: "):])
        print("factory: review and commit the changed files — the update commits nothing. 'factory.sh setup --check'")
        print("factory:   names what the project gained since, as profile lines to confirm; the update writes none.")

    def check_detected(self, proposal: Proposal) -> ProfileOutcome:
        brief = proposal is Proposal.BRIEF
        if not self.installed():
            if brief:
                return ProfileOutcome.HOLDS
            print("factory: no runner — factory.sh setup")
            return ProfileOutcome.LACKS
        folder = presets_dir(None, self.own, self.tool_dirs())
        if not folder:
            if not brief:
                print("factory: no presets found — no pipeline beside this project to detect with (FACTORY_PLUGIN_DIR "
                      "names one)")
            return ProfileOutcome.HOLDS
        if not os.path.isfile(PROFILE):
            if brief:
                return ProfileOutcome.HOLDS
            print(f"factory: no stack profile at {PROFILE} — 'factory.sh update' writes one from detection")
            return ProfileOutcome.LACKS
        code = self.presets(folder, "check", PROFILE, *(["brief"] if brief else []))
        return ProfileOutcome.HOLDS if code == 0 else ProfileOutcome.LACKS

    def write_detected(self, key: typing.Optional[str]) -> ProfileOutcome:
        if not self.installed():
            print("factory: no runner — factory.sh setup")
            return ProfileOutcome.LACKS
        if not os.path.isfile(PROFILE):
            print(f"factory: no stack profile at {PROFILE} — 'factory.sh update' writes one")
            return ProfileOutcome.LACKS
        folder = presets_dir(None, self.own, self.tool_dirs())
        if not folder:
            warn("factory: no presets found — nothing to write from (FACTORY_PLUGIN_DIR names a pipeline)")
            return ProfileOutcome.REFUSED
        # The presets and the carriers come from the pipeline found beside the project — the newest one, which can be
        # an older plugin-cache entry than the copy this project runs: its carriers would replace the project's newer
        # ones. An older source is refused; the one the installed copy came from is named with FACTORY_PLUGIN_DIR.
        have = gate_field(GATE, "VERSION") or ""
        gate_there = os.path.join(folder, "..", "..", "scripts", "story-gate.py")
        offered = (gate_field(gate_there, "VERSION") or "") if os.path.isfile(gate_there) else ""
        if have and offered and have != offered and later(have, offered) == have:
            where = os.path.abspath(os.path.join(folder, "..", "..", ".."))
            warn(f"factory: the pipeline found to write from is {offered} ({where}), older than the")
            warn(f"factory:   installed {have} — its presets and carriers would replace newer ones. Name the source the "
                 "project")
            warn(f"factory:   was installed from: FACTORY_PLUGIN_DIR=<the dca-factory {have}>/skills; nothing was changed")
            return ProfileOutcome.REFUSED
        if self.presets(folder, "write", PROFILE, *([key] if key else [])) != 0:
            return ProfileOutcome.LACKS
        # A carrier line just written names a skill the stage processes must find in the project: put it there the way
        # `update` does — a profile that names a carrier the project does not hold stops the next run.
        source = os.path.abspath(os.path.join(folder, "..", "..", ".."))
        if os.path.isdir(source) and os.path.isfile(os.path.join(source, GATE_IN_SKILLS)):
            for entry in self.folders:
                target = entry.folder
                if not os.path.isdir(target) or os.path.islink(target):
                    continue
                mode = skills_mode(target)
                if entry.plugins or mode == "copy":
                    self.skill_folder(target, source).refresh_carriers(mode == "copy")
        if os.path.isdir(".claude"):
            self.allow_commands()
        return ProfileOutcome.HOLDS
