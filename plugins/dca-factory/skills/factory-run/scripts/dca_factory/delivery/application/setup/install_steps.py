"""The install's steps for the tools named, from one pipeline — what a first setup does, what adding a tool does and
what an update repeats for every tool the project already has."""

from __future__ import annotations

import typing

from ..shared.pipeline_install import InstallStopped, PipelineInstall, SkillMode, Stop

CACHE_REASON = (" — the source is a plugin cache, whose versions are removed after an update, so the install copies "
                "(--link links anyway)")
NO_LINK_REASON = (" — this shell cannot make symlinks (Windows without developer mode or MSYS=winsymlinks:nativestrict), "
                  "so the install copies")


def install(port: PipelineInstall, tool: str, named: typing.Optional[str], mode: typing.Optional[SkillMode],
            adopt: typing.Sequence[str]) -> None:
    """The pipeline's files for <tool> (`all`, `none` or one tool) from <named> or the pipeline found. <mode> is the one
    the person or the project's skills ask for; without one the source decides — a plugin cache holds one folder per
    version and drops a version after an update, so a link into it goes stale: copies, pinned and committed. A
    checkout is a developer's: linked, so an edit is live. Where no link can be made, copies anyway."""
    source = port.install_source(named)
    folders = port.tool_folders(tool)
    if folders is None:
        raise InstallStopped(Stop.USAGE)
    # The profile first: the carriers it names are linked by this same run, so the first `run` does not stop in the
    # carrier check.
    port.prepare(source)
    reason = ""
    chosen = mode
    if chosen is None and port.cache_source(source):
        chosen, reason = SkillMode.COPY, CACHE_REASON
    if chosen is not SkillMode.COPY and not port.can_link():
        chosen, reason = SkillMode.COPY, NO_LINK_REASON
    final = chosen or SkillMode.LINK
    for folder in folders:
        port.fill(folder, source, final, reason, adopt)
    for folder in folders:
        if port.holds_plugins(folder) or final is SkillMode.COPY:
            port.refresh_carriers(folder, source, final)
    for folder in folders:
        port.write_ignores(folder, final)
    port.copy_pipeline(source)
    if tool == "all" or any(port.holds_plugins(folder) for folder in folders):
        port.allow_commands()
    port.project_lines()
    port.closing(folders, source, final)
