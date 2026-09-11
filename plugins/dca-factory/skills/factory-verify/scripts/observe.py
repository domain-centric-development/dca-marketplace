#!/usr/bin/env python3
"""Observe one real run and report the facts about whatever did not hold.

Rides along a story that was actually delivered — it changes nothing and judges no code. What it
does is cross-check the **claims** in the stage files against what the repository, the gate and the
run's journal show. A stage saying "all tests green" is a claim; the gate's own report is evidence;
a test file whose content changed after the test stage is a fact.

    observe.py --story <id> [--tasks tasks] [--backlog backlog] [--project .] [--json]

Exit code 0 means every claim it could check held. Anything it could not see is listed as such
rather than counted as fine.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

CONTRACT = {
    "plan.md": ("Context", "Changes", "Acceptance criteria"),
    "tests.md": ("gate:tests",),
    "build.md": ("Changed", "Criteria", "Checks"),
    "tidy.md": ("Moves", "Checks"),
    "judge.md": ("Verdict",),
    "document.md": ("Glossary",),
}
CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)\s*:\s*\S")
MAPPING_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|")
SELECTOR = re.compile(r"([\w.]+)#(\w+)")
BACKTICKED = re.compile(r"`([^`\n]{2,120})`")
PROFILE_KEYS = ("compile", "test", "e2eTest", "architecture", "format")


class Report:
    def __init__(self):
        self.findings, self.held, self.unseen = [], [], []

    def finding(self, kind, detail, evidence=""):
        self.findings.append({"kind": kind, "detail": detail, "evidence": evidence})

    @staticmethod
    def listing(items, limit=8):
        """A finding a reader can act on names a few files and the count, never a screenful."""
        items = sorted(items)
        if len(items) <= limit:
            return ", ".join(items)
        return ", ".join(items[:limit]) + f", … and {len(items) - limit} more"

    def ok(self, kind, detail):
        self.held.append({"kind": kind, "detail": detail})

    def blind(self, kind, detail):
        self.unseen.append({"kind": kind, "detail": detail})


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def front_matter(text):
    if not text or not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    data = {}
    for line in parts[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def story_file(backlog, story_id):
    for root, _dirs, files in os.walk(backlog):
        for name in files:
            if not name.endswith(".md") or name == "epic.md":
                continue
            path = os.path.join(root, name)
            if os.path.splitext(name)[0].lower() == story_id.lower():
                return path
            if front_matter(read(path)).get("id", "").lower() == story_id.lower():
                return path
    return None


def criteria_of(text):
    keys, collecting = [], False
    for line in (text or "").splitlines():
        if line.strip().lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting:
            match = CRITERION.match(line.strip())
            if match:
                keys.append(match.group(1))
    return keys


def mapping_of(text):
    mapping, inside = {}, False
    for line in (text or "").splitlines():
        if "gate:tests" in line:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            match = MAPPING_ROW.match(line.strip())
            if match and SELECTOR.fullmatch(match.group(2).strip()):
                mapping.setdefault(match.group(1), []).append(match.group(2).strip())
    return mapping


def git(project, *args):
    result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True)
    return result.returncode, result.stdout


def changed_files(project):
    """Every path git reports as changed, one per line — `-uall` so a new directory is listed as
    its files and `.gitignore` still applies. Walking it here instead would pull in build output."""
    code, out = git(project, "-c", "core.fileMode=false", "status", "--porcelain", "-uall")
    if code != 0:
        return None
    return [line[3:].strip().strip('"') for line in out.splitlines() if line[3:].strip()]


def digest(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


#: The first line the runner writes when the machine has no sha256 command (see `snapshot` in
#: factory.sh). Such a file carries names and no content.
NO_HASHES = "# no-sha256-command"


def snapshot(path):
    """`tree-<label>.txt` written by the runner: digest and path per line.

    A snapshot without content hashes is reported as *absent*, not compared: every digest in it is
    a placeholder, so every comparison against it would come out equal and every check would read
    "nothing changed" — the strongest claim in the report from no evidence at all.
    """
    text = read(path)
    if text is None or text.startswith(NO_HASHES):
        return None
    entries = {}
    for line in text.splitlines():
        parts = line.split("  ", 1)
        if len(parts) == 2:
            entries[parts[1].strip()] = parts[0].strip()
    return entries


def snapshot_reason(path):
    """Why a snapshot could not be compared, where the file itself says so."""
    text = read(path)
    if text is not None and text.startswith(NO_HASHES):
        return (" — the runner found no sha256 command on that machine and recorded file names "
                "without content")
    return ""


def locate(project, selector):
    """Where the test behind a selector lives, by the same rule the gate uses."""
    cls, method = SELECTOR.fullmatch(selector).groups()
    simple = cls.rsplit(".", 1)[-1]
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in ("build", "out", "bin", "obj", "target",
                                                "node_modules", ".git", "tasks")]
        for name in files:
            if os.path.splitext(name)[0] == simple:
                path = os.path.join(root, name)
                body = read(path)
                if body and method in body:
                    return os.path.relpath(path, project)
    return None


def observe(project, tasks, backlog, story_id):
    report = Report()
    run_dir = os.path.join(project, tasks, story_id)
    journal_dir = os.path.join(run_dir, ".verify")

    if not os.path.isdir(run_dir):
        report.finding("run", f"no run artefacts at {os.path.join(tasks, story_id)} — nothing to observe")
        return report

    # --- 1. the file contract -------------------------------------------
    present = {}
    for name, sections in CONTRACT.items():
        text = read(os.path.join(run_dir, name))
        present[name] = text
        if text is None:
            if name == "tidy.md":
                report.blind("contract", "tidy.md is absent — the tidy stage did not run here")
            else:
                report.finding("contract", f"{name} is missing, so that stage produced no hand-over")
            continue
        missing = [s for s in sections if s.lower() not in text.lower()]
        if missing:
            report.finding("contract", f"{name} has no {', '.join(missing)} section",
                           "the file contract names it")
        else:
            report.ok("contract", f"{name} carries the sections the contract names")

    # --- 2. criterion keys are committed identifiers ---------------------
    story_path = story_file(os.path.join(project, backlog), story_id)
    if not story_path:
        report.blind("criteria", f"no story file for {story_id} under {backlog}/")
        story_keys = []
    else:
        story_keys = criteria_of(read(story_path))
    mapping = mapping_of(present.get("tests.md"))
    if story_keys and mapping:
        unmapped = [k for k in story_keys if k not in mapping]
        invented = [k for k in mapping if k not in story_keys]
        if unmapped:
            report.finding("criteria", f"criteria with no test: {', '.join(unmapped)}",
                           "the story names them, the test table does not")
        if invented:
            report.finding("criteria", f"the test table names keys the story does not: {', '.join(invented)}",
                           "a key is a committed identifier; a renamed one silently drops a criterion")
        if not unmapped and not invented:
            report.ok("criteria", f"all {len(story_keys)} criterion keys map, verbatim")

    # --- 3. red before, green after — from the gate, not from a claim ----
    ledger = read(os.path.join(run_dir, ".tests-red"))
    recorded = {line.strip() for line in (ledger or "").splitlines() if line.strip()}
    selectors = [s for group in mapping.values() for s in group]
    if not selectors:
        report.blind("red-green", "no mapped tests, so nothing to check")
    elif ledger is None:
        report.finding("red-green", "no .tests-red from the test stage — nothing proves a mapped test ever failed",
                       "the build gate can only skip that check, and did")
    else:
        never_red = [s for s in selectors if s not in recorded]
        if never_red:
            report.finding("red-green", f"never recorded red: {', '.join(never_red)}",
                           "a test that never failed proves nothing about its criterion")
        else:
            report.ok("red-green", f"all {len(selectors)} mapped tests were recorded red by the test stage")

    gate_reports = sorted(f for f in os.listdir(journal_dir) if f.startswith("gate-")) \
        if os.path.isdir(journal_dir) else []
    if gate_reports:
        for name in gate_reports:
            text = read(os.path.join(journal_dir, name)) or ""
            for line in text.splitlines():
                if not line.startswith("gate:fail"):
                    continue
                detail = line.strip()[10:]
                # The last line of a gate report restates the verdict for the whole stage; the
                # findings above it are what a reader can act on.
                if re.match(rf"story\s+{re.escape(story_id)}\s+stage\s+\w+$", detail):
                    continue
                report.finding("gate", f"{name.split('.')[0]} reported: {detail}",
                               f"{tasks}/{story_id}/.verify/{name}")
            skipped = [l.strip()[10:] for l in text.splitlines() if l.startswith("gate:skip")]
            for entry in skipped:
                report.blind("gate", f"{name.split('.')[0]} skipped: {entry}")
    else:
        report.blind("gate", "no gate reports in the run journal — the run was not driven by the runner, "
                             "so only the files can be cross-checked")

    # --- 4. did a stage change a test after the test stage? --------------
    before_path = os.path.join(journal_dir, "tree-after-test.txt")
    before = snapshot(before_path)
    if before is None:
        report.blind("tests-untouched", "no tree snapshot from the test stage to compare — cannot tell "
                                        "whether a later stage edited a test"
                                        + snapshot_reason(before_path))
    else:
        touched, unhashed = [], []
        for selector in selectors:
            path = locate(project, selector)
            if not path:
                unhashed.append(f"{selector} (no source file found now)")
                continue
            was = before.get(path)
            now = digest(os.path.join(project, path))
            if was is None:
                # No digest for it in the snapshot: the file was not tracked as changed at that
                # point, or the snapshot missed it. Either way this check saw nothing — saying
                # "unchanged" here would be the strongest claim in the report and the least founded.
                unhashed.append(f"{path} (not in the snapshot from the test stage)")
                continue
            if now is None:
                touched.append(f"{path} (gone)")
            elif was != now:
                touched.append(path)
        for entry in unhashed:
            report.blind("tests-untouched", f"no digest to compare for {entry}")
        if touched:
            report.finding("tests-untouched", f"a stage after the test stage changed {report.listing(set(touched))}",
                           "the code changes until the test passes; the test does not")
        elif len(unhashed) < len(selectors):
            report.ok("tests-untouched",
                      f"no mapped test changed after the test stage "
                      f"({len(selectors) - len(unhashed)} of {len(selectors)} compared)")

    # --- 5. what the build claimed it changed vs. what changed -----------
    actual = changed_files(project)
    window_path = os.path.join(journal_dir, "tree-before-build.txt")
    window = snapshot(window_path)
    if actual is not None and window is not None:
        # Only what changed *during* the run is the run's to account for. Without the journal the
        # working tree also holds whatever was there before, and blaming a stage for that is noise.
        after = snapshot(os.path.join(journal_dir, "tree-after-build.txt")) or {}
        actual = [f for f in actual if window.get(f) != after.get(f, window.get(f))] or \
                 [f for f in after if window.get(f) != after.get(f)]
    elif actual is not None:
        journalled = sorted(f[5:-4] for f in os.listdir(journal_dir)
                            if f.startswith("tree-")) if os.path.isdir(journal_dir) else []
        report.blind("claims", "no tree snapshot from around the build stage to compare"
                               + snapshot_reason(window_path)
                               + (f" (the journal has {', '.join(journalled)})" if journalled else
                                  " and no journal at all")
                               + " — without the run's own window the check would blame a stage for "
                                 "everything uncommitted in the tree")
        actual = None
    if actual is None and not os.path.isdir(os.path.join(project, ".git")):
        report.blind("claims", "not a git repository — a stage's claim about changed files cannot be checked")
    if actual is not None and present.get("build.md"):
        claimed = set()
        for token in BACKTICKED.findall(present["build.md"]):
            candidate = re.sub(r"[:#][0-9,\-]+$", "", token).strip()
            # A path has no spaces in it, and its extension is short: `dotnet test tests/Foo.Bar`
            # is a command whose last segment merely looks like one, and reading it as a file
            # produces a finding about nothing.
            extension = os.path.splitext(candidate)[1]
            if (" " not in candidate and "/" in candidate
                    and re.fullmatch(r"\.[A-Za-z0-9]{1,6}", extension)):
                claimed.add(candidate)
        code_changes = {f for f in actual
                        if not f.startswith((tasks + "/", backlog + "/", ".agents/", ".claude/", ".codex/", ".opencode/"))
                        and not f.endswith(".md")}
        unclaimed = sorted(f for f in code_changes if f not in claimed)
        phantom = sorted(c for c in claimed
                         if c not in actual and not os.path.exists(os.path.join(project, c)))
        if unclaimed:
            report.finding("claims", f"changed but not named in build.md: {report.listing(unclaimed)}",
                           "a change the hand-over does not mention is a change nobody reviewed")
        else:
            report.ok("claims", f"every changed source file ({len(code_changes)}) is named in build.md")
        if phantom:
            report.finding("claims", f"build.md names files that do not exist: {report.listing(phantom)}")

    # --- 6. a surface, an element, that no plan named --------------------
    if actual is not None and present.get("plan.md"):
        planned = set()
        for token in BACKTICKED.findall(present["plan.md"]):
            planned.add(os.path.splitext(os.path.basename(re.sub(r"[:#][0-9,\-]+$", "", token)))[0])
        for word in re.findall(r"\b([A-Z][A-Za-z0-9]{3,})\b", present["plan.md"]):
            planned.add(word)
        surprises = []
        for path in actual:
            if path.startswith((tasks + "/", backlog + "/", ".agents/", ".claude/")) or path.endswith(".md"):
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem not in planned:
                surprises.append(path)
        if surprises:
            report.finding("plan-coverage", f"changed without appearing in the plan: {report.listing(surprises)}",
                           "an element the plan never named was not designed, reviewed or asked for")
        else:
            report.ok("plan-coverage", "every changed file was named in the plan")

    # --- 7. commands a stage claims vs. what the project declares --------
    profile = read(os.path.join(project, ".agents", "factory", "factory.profile.yaml")) or ""
    declared = {}
    for line in profile.splitlines():
        if ":" in line and not line.strip().startswith("#"):
            key, value = line.split(":", 1)
            declared[key.strip()] = value.strip()
    for name in ("build.md", "tidy.md"):
        text = present.get(name)
        if not text:
            continue
        section = text.split("## Checks", 1)[-1] if "## Checks" in text else ""
        for token in BACKTICKED.findall(section):
            head = token.split()[0] if token.split() else ""
            if head in ("./gradlew", "dotnet", "mvn", "./mvnw", "npm", "make"):
                if not any(token.strip() in v for v in declared.values()):
                    report.finding("commands", f"{name} reports running `{token}`, which the stack profile "
                                               f"does not declare",
                                   "a check nobody configured was either not run or ran outside the profile")

    # --- 8. carriers and knowledge: named vs. used -----------------------
    for key, value in declared.items():
        if not (key.startswith("carrier.") or key.startswith("review.") or key == "knowledge"):
            continue
        stage_file = {"carrier.plan": "plan.md", "carrier.test": "tests.md", "carrier.build": "build.md",
                      "carrier.tidy": "tidy.md"}.get(key)
        texts = [present[stage_file]] if stage_file and present.get(stage_file) else \
                [t for t in present.values() if t]
        if not any(value in (t or "") for t in texts):
            report.finding("carriers", f"the profile names {key}: {value}, and no stage file mentions it",
                           "a named carrier that no stage reports using was silently not used")
        else:
            report.ok("carriers", f"{key}: {value} appears in the stage's own account")

    # --- 9. fall-backs, rounds, escalations ------------------------------
    rounds = (read(os.path.join(run_dir, ".rounds")) or "").strip()
    if rounds and rounds != "0":
        report.blind("rounds", f"the build/judge loop ran {rounds} extra round(s) — read judge.md for why")
    for name, text in present.items():
        if not text:
            continue
        if "## needs-human" in text:
            report.finding("escalation", f"{name} ends with a needs-human section",
                           "the run stopped for a decision; it is not a delivered story")
        for line in text.splitlines():
            if "not available here" in line or "in-session" in line.lower():
                report.blind("fall-back", f"{name}: {line.strip()[:140]}")
    verdict = ""
    if present.get("judge.md"):
        match = re.search(r"^verdict:\s*(\S+)", present["judge.md"], re.M)
        verdict = match.group(1) if match else ""
        if not verdict:
            report.finding("verdict", "judge.md carries no verdict line")
        elif verdict != "pass":
            report.finding("verdict", f"the judge returned '{verdict}'",
                           "the story is not delivered while that stands")
        else:
            report.ok("verdict", "the judge returned pass")

    # --- 10. how long each stage took ------------------------------------
    journal = read(os.path.join(journal_dir, "journal.tsv"))
    if not journal:
        report.blind("timing", "no journal — stage durations were not observed")
    else:
        starts = {}
        for line in journal.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1] == "stage-start":
                starts[parts[2]] = parts[0]
            elif len(parts) >= 3 and parts[1] == "stage-end" and parts[2] in starts:
                report.ok("timing", f"{parts[2]}: {starts[parts[2]]} → {parts[0]}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="observe one real factory run")
    parser.add_argument("--story", required=True)
    parser.add_argument("--tasks", default="tasks")
    parser.add_argument("--backlog", default="backlog")
    parser.add_argument("--project", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = os.path.abspath(args.project)
    report = observe(project, args.tasks, args.backlog, args.story)

    if args.json:
        print(json.dumps({"story": args.story, "findings": report.findings,
                          "held": report.held, "not_observed": report.unseen}, indent=2))
    else:
        print(f"# Observation — {args.story}\n")
        if report.findings:
            print(f"## What did not hold ({len(report.findings)})\n")
            for item in report.findings:
                print(f"- **{item['kind']}** — {item['detail']}")
                if item["evidence"]:
                    print(f"  · {item['evidence']}")
            print()
        else:
            print("## What did not hold\n\nNothing that this observation can check.\n")
        print(f"## What held ({len(report.held)})\n")
        for item in report.held:
            print(f"- {item['kind']}: {item['detail']}")
        print(f"\n## Not observed ({len(report.unseen)})\n")
        for item in report.unseen:
            print(f"- {item['kind']}: {item['detail']}")
        print("\nA check that was not observed is not a check that passed.")
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
