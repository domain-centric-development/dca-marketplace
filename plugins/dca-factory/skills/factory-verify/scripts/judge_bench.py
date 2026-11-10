#!/usr/bin/env python3
"""The judge measured: a seeded-defect bench's two steps around a real run — plant one known defect into a story's
built code before its judge runs, and score the judges' verdicts afterwards.

    judge_bench.py plant <defects.json> <story>      in the bench project: apply the story's planted patch
    judge_bench.py score <defects.json> <project>    recall and false alarms over every story of the set

The set (`defects.json`) is a list of items, one per story:

    {"story": "<id>", "kind": "defect" | "control",
     "patch": "<a unified diff, applied with git apply after the build>",          (a defect only)
     "files": ["<path the planted defect sits in>", …],                            (a defect only)
     "words": ["<a regular expression a finding about it would say>", …],          (a defect only)
     "about": "<what is planted, in general words>"}

A planted defect is one the tests do not catch — the gate would, and the judge is what is measured: a rule of the
model left out, a dependency that points the wrong way, a value compared by identity, a translation skipped at the
edge. Its description names no project's vocabulary.

Scoring reads each story's `judge.md` (`## Confirmed defects`, the factory's contract): a defect is **found** where a
confirmed row ranked `major` or `blocker` names one of its files or says one of its words; a control story's rows
ranked `major` or `blocker` are **false alarms**. recall = found / defects. Counted, never rated by a model.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import typing

#: The ranks a finding must have to count — what would send a story back.
COUNTED = ("major", "blocker")


def items_of(path: str) -> typing.List[typing.Dict[str, typing.Any]]:
    with open(path, encoding="utf-8") as handle:
        items = json.load(handle)
    for item in items:
        if item.get("kind") not in ("defect", "control") or not item.get("story"):
            raise ValueError(f"{path}: every item names its story and its kind, defect or control — {item!r}")
        if item["kind"] == "defect" and not (item.get("patch") and (item.get("files") or item.get("words"))):
            raise ValueError(f"{path}: the defect of {item['story']} needs its patch and files or words to find it by")
    return items


def confirmed(judge_text: str) -> typing.List[typing.Dict[str, str]]:
    """The `## Confirmed defects` rows of a judge's file, by the header's names."""
    rows, inside, names = [], False, ["perspective", "file:line", "severity", "defect", "fix"]
    for line in judge_text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "confirmed defects"
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower() == "perspective":
            names = [c.lower() for c in cells]
            continue
        if len(cells) < 4 or set(cells[0]) <= set("-: "):
            continue
        rows.append(dict(zip(names, cells)))
    return rows


def counted(row: typing.Mapping[str, str]) -> bool:
    return any(rank in row.get("severity", "").lower() for rank in COUNTED)


def found(item: typing.Mapping[str, typing.Any], rows: typing.Sequence[typing.Mapping[str, str]]) -> bool:
    """Whether a counted row names the planted defect: one of its files in `file:line`, or one of its words anywhere."""
    for row in rows:
        if not counted(row):
            continue
        place = row.get("file:line", "").strip("`")
        if any(place.startswith(f) or f in place for f in item.get("files", ())):
            return True
        text = " ".join(row.values())
        if any(re.search(word, text, re.I) for word in item.get("words", ())):
            return True
    return False


def judge_file(project: str, story: str) -> str:
    """The story's judge.md: the run folder of the project, or the evaluation copy the bench keeps."""
    for folder in (os.path.join(project, ".dca-factory", "runs", story), os.path.join(project, "runs", story)):
        path = os.path.join(folder, "judge.md")
        if os.path.isfile(path):
            return path
    return ""


def score(items: typing.Sequence[typing.Mapping[str, typing.Any]], project: str) -> typing.Dict[str, typing.Any]:
    lines, defects, hits, alarms, missing = [], 0, 0, 0, []
    for item in items:
        path = judge_file(project, item["story"])
        if not path:
            missing.append(item["story"])
            lines.append(dict(story=item["story"], kind=item["kind"], judged=False))
            continue
        with open(path, encoding="utf-8") as handle:
            rows = confirmed(handle.read())
        if item["kind"] == "defect":
            defects += 1
            hit = found(item, rows)
            hits += hit
            lines.append(dict(story=item["story"], kind="defect", judged=True, found=hit, about=item.get("about", "")))
        else:
            raised = sum(1 for row in rows if counted(row))
            alarms += raised
            lines.append(dict(story=item["story"], kind="control", judged=True, false_alarms=raised))
    return dict(defects=defects, found=hits, recall=round(hits / defects, 2) if defects else None,
                false_alarms=alarms, not_judged=missing, stories=lines)


def plant(items: typing.Sequence[typing.Mapping[str, typing.Any]], story: str) -> int:
    item = next((i for i in items if i["story"] == story), None)
    if item is None:
        print(f"judge-bench: no item for {story}", file=sys.stderr)
        return 2
    if item["kind"] == "control":
        print(f"judge-bench: {story} is the control — nothing planted")
        return 0
    done = subprocess.run(["git", "apply", "-"], input=item["patch"], text=True, capture_output=True)
    if done.returncode != 0:
        print(f"judge-bench: the patch of {story} does not apply — {done.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"judge-bench: planted into {story}: {item.get('about', '')}")
    return 0


def main(argv: typing.Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="judge_bench.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="verb", required=True)
    planting = sub.add_parser("plant", help="apply the story's planted defect in the working directory")
    planting.add_argument("defects")
    planting.add_argument("story")
    scoring = sub.add_parser("score", help="recall and false alarms over the set")
    scoring.add_argument("defects")
    scoring.add_argument("project")
    scoring.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    items = items_of(args.defects)
    if args.verb == "plant":
        return plant(items, args.story)
    result = score(items, args.project)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    for line in result["stories"]:
        if not line["judged"]:
            print(f"  {line['story']:<32} not judged")
        elif line["kind"] == "defect":
            print(f"  {line['story']:<32} {'found' if line['found'] else 'missed'} — {line['about']}")
        else:
            print(f"  {line['story']:<32} control — {line['false_alarms']} false alarm(s)")
    recall = "—" if result["recall"] is None else f"{result['recall']:.2f}"
    print(f"judge-bench: recall {recall} ({result['found']}/{result['defects']}), "
          f"false alarms {result['false_alarms']}" + (f", not judged: {', '.join(result['not_judged'])}"
                                                      if result["not_judged"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
