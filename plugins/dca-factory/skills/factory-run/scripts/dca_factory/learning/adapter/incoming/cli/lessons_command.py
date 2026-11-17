"""`factory-cli.py --lessons [--format text|json] [--write] [--issue <lesson>] [--epics <folder>]` — what repeats
across the stories: the candidates with their evidence; `--write` asks each one nobody was asked yet as a lesson record
in decide; `--issue` writes the anonymised issue text of a lesson that goes up — a person sends it."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import typing

from ....application.show_lessons import ShowLessonsInputPort, ShowLessonsQuery
from ....application.write_issue import IssueWritten, WriteIssueCommand, WriteIssueInputPort
from ....application.write_lessons import WriteLessonsCommand, WriteLessonsInputPort
from ....domain.model.words import Moment, RecordId


class LessonsRoot(typing.Protocol):
    """What this command line takes from the composition root — given at start (`wire`), never imported."""

    def show_lessons(self, cwd: str, epics: typing.Optional[str]) -> ShowLessonsInputPort: ...

    def write_lessons(self, cwd: str) -> WriteLessonsInputPort: ...

    def write_issue(self, cwd: str) -> WriteIssueInputPort: ...


#: the composition root, given by `wire` before the command line runs
wiring: LessonsRoot


def wire(root: LessonsRoot) -> None:
    """The composition root this command line builds its use cases from."""
    global wiring
    wiring = root


def render(model: typing.Dict[str, typing.Any], form: str) -> int:
    """The lesson candidates: one block per candidate — its kind, key and stories, the evidence, the places offered."""
    if form == "json":
        print(json.dumps(model, ensure_ascii=False, indent=2))
        return 0
    counted = ", ".join(f"{n} {kind}" for kind, n in model["signals"].items())
    limits = ", ".join(f"{kind} {n}" for kind, n in model["thresholds"].items())
    print(f"factory: signals counted — {counted}; a candidate from its kind's count of stories — {limits}")
    for c in model["candidates"]:
        print(f"\n{c['id']}\t{c['kind']}\t{c['key']}\t{c['stories']} stories")
        print("  evidence: " + ", ".join(e["source"] for e in c["evidence"]))
        print("  places: " + ", ".join(p["place"] + (" (recommended)" if p["place"] == c["recommended"] else "")
                                       for p in c["places"]))
    print(f"\nfactory: {len(model['candidates'])} lesson candidate(s) not yet asked")
    return 0


def main(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="factory-cli.py --lessons", description="what repeats across the stories")
    parser.add_argument("--lessons", action="store_true", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--issue", metavar="LESSON",
                        help="the anonymised issue text of a lesson answered factory, rule-library or "
                             "knowledge-catalog, under the factory's folder — a person sends it, nothing leaves by itself")
    parser.add_argument("--write", action="store_true",
                        help="write each candidate nobody was asked yet as an open lesson record")
    parser.add_argument("--epics", help="where the epics and stories are (default: the profile's `epics:`)")
    args, _rest = parser.parse_known_args(list(argv))
    cwd = os.getcwd()
    if args.issue:
        issued = wiring.write_issue(cwd).execute(WriteIssueCommand(RecordId(args.issue)))
        if not isinstance(issued, IssueWritten):
            print(f"factory: {issued.why}", file=sys.stderr)
            return 1
        print(issued.text)
        print(f"factory: the issue text is {issued.path} — it names no project, no story and no file; send it to the "
              "maintainers yourself, the factory sends nothing")
        return 0
    if args.write:
        written = wiring.write_lessons(cwd).execute(
            WriteLessonsCommand(Moment(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))))["written"]
        for one in written:
            print(f"{one['id']}\t{one['kind']}\t{one['path']}")
        print(f"factory: {len(written)} lesson record(s) written — they wait in decide beside the stories; none holds "
              "a story back")
        return 0
    return render(wiring.show_lessons(cwd, args.epics).execute(ShowLessonsQuery()), args.format)
