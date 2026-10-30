"""What the gate found over a story, read back: the latest report the runner filed per stage beside the journal
(`gate-<stage>.<time>.txt`, every finding a line `gate:<state> <check> — …`), and the refusals the journal counts per
check."""

from __future__ import annotations

import collections
import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from .journal_files import journal_events

REPORT = re.compile(r"^gate-([a-z]+)\.\d+\.txt$")
FINDING = re.compile(r"^gate:(pass|fail|skip|note|wait) (\S+) — (.*)$")
#: The brief form's one line for every pass: `gate:pass <n> check(s) — a, b`.
PASSED = re.compile(r"^gate:pass \d+ check\(s\) — (.*)$")

Findings = typing.List[typing.Dict[str, str]]


def latest_reports(runs: str, story_id: str) -> typing.Dict[str, str]:
    """{stage: path} of the newest report per stage — a view's question, so the file's time picks it."""
    folder = evidence_dir(runs, story_id)
    newest: typing.Dict[str, typing.Tuple[float, str]] = {}
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            found = REPORT.match(name)
            if found:
                path = os.path.join(folder, name)
                at = os.path.getmtime(path)
                if found.group(1) not in newest or at > newest[found.group(1)][0]:
                    newest[found.group(1)] = (at, path)
    return {stage: path for stage, (_at, path) in newest.items()}


def report_findings(path: str) -> Findings:
    found: Findings = []
    for line in read_text(path).splitlines():
        passed = PASSED.match(line)
        if passed:
            found += [dict(state="pass", check=name.strip()) for name in passed.group(1).split(",") if name.strip()]
            continue
        finding = FINDING.match(line)
        if finding and finding.group(2) != "stage":      # `gate:note stage <s> ran without …` sums the skips up
            found.append(dict(state=finding.group(1), check=finding.group(2)))
    return found


def story_findings(runs: str, story_id: str) -> typing.Dict[str, typing.Any]:
    """{stages: {stage: [{state, check}]}, refused: {check: n}} — empty where the story left no report."""
    stages = {stage: report_findings(path) for stage, path in sorted(latest_reports(runs, story_id).items())}
    refused: typing.Counter[str] = collections.Counter()
    for event in journal_events(runs, story_id):
        if event["kind"] == "gate" and event["fields"].get("exit") == "1":
            refused.update(c for c in str(event["fields"].get("fail", "")).split(",") if c)
    return dict(stages=stages, refused=dict(refused))
