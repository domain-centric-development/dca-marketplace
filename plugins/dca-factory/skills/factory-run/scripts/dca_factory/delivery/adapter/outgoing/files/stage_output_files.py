"""The processes' raw outputs: a stage's under its story's evidence folder (`<process>.<n>.out`), a request's beside
the requests — read through the tool's stream reader."""

from __future__ import annotations

import glob
import os
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from ....application.shared.stage_outputs import Output
from ..tools.streams import follow_lines
from .request_files import out_path
from .status_facts import follow_newest


class StageOutputFiles:
    def __init__(self, runs: str) -> None:
        self._runs = runs

    def outputs(self, story: str, process: typing.Optional[str]) -> typing.Sequence[Output]:
        pattern = os.path.join(evidence_dir(self._runs, story), f"{process}.*.out" if process else "*.out")
        outs = [p for p in glob.glob(pattern) if os.path.isfile(p)]
        return [Output(story, os.path.basename(p).split(".")[0], os.path.relpath(p))
                for p in sorted(outs, key=lambda p: (os.path.getmtime(p), p))]

    def newest(self, story: typing.Optional[str], process: typing.Optional[str],
               request: typing.Optional[str]) -> typing.Optional[Output]:
        if request:
            path = out_path(request)
            return Output("request", request, os.path.relpath(path)) if os.path.isfile(path) else None
        found = follow_newest(self._runs, story, process)
        return Output(found[0], found[1], os.path.relpath(found[2])) if found else None

    def read(self, output: Output, offset: int) -> typing.Tuple[str, int]:
        try:
            with open(output.path, encoding="utf-8", errors="replace") as handle:
                handle.seek(offset)
                text = handle.read()
                return text, handle.tell()
        except OSError:
            return "", offset

    def lines(self, text: str) -> typing.Tuple[typing.List[str], bool]:
        return follow_lines(text)
