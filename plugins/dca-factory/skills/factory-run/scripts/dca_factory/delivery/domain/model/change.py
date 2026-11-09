"""The same checks outside a story: a direct edit, a commit and CI get one verdict for one tree. The profile declares
the commands; its `required:` line declares which of them must hold."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .story_words import Count, Place
from .suite_run import CommandKey, Requirement
from .story_state import Detail
from .verdict import CheckName, Finding, Findings, Said

POLICY = CheckName("policy")
SNAPSHOT = CheckName("snapshot")
SCOPE = CheckName("scope")
TEST = CheckName("test")
CONTRACT = CheckName("contract")
IMPLEMENTATIONS = CheckName("implementations")

#: The checks a change runs, by their profile keys; the test commands go by their own keys.
CHANGE_CHECKS = ("compile", "test", "architecture", "format")

#: Nothing runs over the working tree: what else is changed there cannot reach a check of this commit.
BACKLOG_ALONE = SNAPSHOT.note(Said("the backlog alone, and `checks.backlog` names no check — what else the working tree "
                                  "holds is not this commit's"))
NO_TEST = TEST.skip(Said("no test command in the stack profile"))


class Snapshot(Value):
    """The commit's index against the working tree: why no tree could be written, the tree, what differs from it
    outside the pipeline's own and the tools' folders, and how many files the pipeline wrote itself."""

    refused: typing.Optional[Detail]
    tree: Detail
    drift: typing.Tuple[Detail, ...]
    left: Count

    def finding(self) -> Finding:
        """Refuse on drift rather than materialise the index: a check that runs the tests against an unstaged fix
        certifies a commit that does not contain it."""
        if self.refused is not None:
            return SNAPSHOT.fail(Said(self.refused.value))
        if self.drift:
            drift = [d.value for d in self.drift]
            shown = "\n".join("  " + line for line in drift[:10])
            more = f"\n  … and {len(drift) - 10} more" if len(drift) > 10 else ""
            return SNAPSHOT.fail(Said(
                f"the working tree is not what the commit contains — the checks would run against these, and the "
                f"commit would not:\n{shown}{more}\nStage them, or set them aside "
                f"(`git stash push --keep-index --include-untracked`), then commit again."))
        left = self.left.value
        return SNAPSHOT.ok(Said(f"index tree {self.tree.value[:12]} — the working tree matches it"
                                + (f" ({left} file(s) the pipeline writes itself left out)" if left else "")))


class ParityScenario(Value):
    """A scenario of a parity contract: its id, its title — what binds it to a test — and whether every
    configuration has to prove it."""

    id: Detail
    title: Detail
    _always: bool

    @property
    def always(self) -> bool:
        """Whether every configuration has to prove the scenario."""
        return self._always


class ImplementationReports(Value):
    """One implementation's reports: its name, the glob, how many reports match, the newest, and the outcome each
    test name has in them."""

    name: Detail
    glob: Detail
    reports: Count
    newest: Detail
    outcomes: typing.Tuple[typing.Tuple[Detail, Detail], ...]


class ParityFacts(Value):
    """A parity config: its file, the contract's file and digest, its scenarios, and each implementation's
    reports."""

    config: Place
    scenarios_file: Detail
    digest: Detail
    scenarios: typing.Tuple[ParityScenario, ...]
    implementations: typing.Tuple[ImplementationReports, ...]

    def findings(self) -> Findings:
        """Every implementation's reports against one scenario contract: a mandatory scenario passes in each, one
        bound to another configuration is named, not proven here."""
        found: typing.List[Finding] = []
        untitled = [s.id.value for s in self.scenarios if not s.title.value]
        scenarios = [s for s in self.scenarios if s.title.value]
        if untitled:
            # A scenario without its `Title:` line binds to no test: dropped, it would leave parity silently.
            found.append(CONTRACT.fail(Said(f"{', '.join(untitled)} in {self.scenarios_file.value} carry no `Title:` "
                                            f"line — the title is what binds a scenario to a test")))
        found.append(CONTRACT.ok(Said(f"{len(scenarios)} scenario(s) in {self.scenarios_file.value} (sha256 "
                                      f"{self.digest.value})")))
        if not self.implementations:
            found.append(IMPLEMENTATIONS.fail(Said(f"{self.config.value} declares no `implementation.<name>: <report "
                                                   f"glob>`")))
        for implementation in self.implementations:
            name, count = CheckName(implementation.name.value), implementation.reports.value
            if not count:
                found.append(name.fail(Said(f"no report matches {implementation.glob.value} — run its suite first")))
                continue
            names = {title.value: outcome.value for title, outcome in implementation.outcomes}
            if not any(s.title.value in names for s in scenarios):
                found.append(name.fail(Said(f"{count} report(s) name no scenario of the contract — the binding (the "
                                            f"title as the test's name) is gone")))
                continue
            problems, unproven = [], []
            for scenario in scenarios:
                outcome = names.get(scenario.title.value)
                if outcome == "passed":
                    continue
                if not scenario.always and outcome in (None, "skipped"):
                    unproven.append(scenario.id.value)
                    continue
                problems.append(f"{scenario.id.value} {outcome or 'missing'} — {scenario.title.value!r}")
            if problems:
                found.append(name.fail(Said(f"{len(problems)} scenario(s) not proven by {count} report(s):\n"
                                            + "\n".join("  " + p for p in problems))))
            else:
                found.append(name.ok(Said(f"{len(scenarios) - len(unproven)} scenario(s) passed in {count} report(s), "
                                          f"newest {implementation.newest.value}")))
            if unproven:
                found.append(name.note(Said(f"not proven here (bound to another configuration): "
                                            f"{', '.join(unproven)}")))
        return tuple(found)


class CheckKeys(Value):
    """The profile keys a policy names — `required:`, or `checks.backlog:` for a commit of the backlog alone."""

    keys: typing.Tuple[CommandKey, ...]

    def policy_findings(self) -> Findings:
        """`required:` names profile keys: compile, architecture, format, and each test command by its own key — an
        end-user suite that needs a running system can be declared without making every commit wait for one."""
        found = []
        unknown = sorted(k.value for k in self.keys if k.value not in CHANGE_CHECKS and k.value != "e2eTest"
                         and not k.value.startswith("test."))
        if unknown:
            found.append(POLICY.fail(Said(f"`required:` names {', '.join(unknown)} — it takes compile, architecture, "
                                          f"format and test-command keys (test, e2eTest, test.<name>)")))
        if self.keys:
            found.append(POLICY.ok(Said("required: " + " ".join(sorted(k.value for k in self.keys)))))
        else:
            found.append(POLICY.note(Said("the profile declares no `required:` — nothing is mandatory: what is "
                                          "declared runs and fails when red, what is not is named")))
        return tuple(found)

    def backlog_findings(self, test_keys: typing.Tuple[CommandKey, ...], paths: Count) -> Findings:
        """A commit of the backlog alone changes no code: it runs what `checks.backlog` names, and nothing more."""
        found = []
        unknown = sorted(n.value for n in self.keys if n.value not in CHANGE_CHECKS and n not in test_keys)
        if unknown:
            found.append(POLICY.fail(Said(f"`checks.backlog:` names {', '.join(unknown)} — it takes compile, "
                                          f"architecture, format and the profile's test-command keys (test, e2eTest, "
                                          f"test.<name>)")))
        found.append(SCOPE.note(Said(f"the commit changes only the backlog and the pipeline's own files ({paths.value} "
                                     f"path(s)) — `checks.backlog` runs "
                                     + (", ".join(n.value for n in self.keys) if self.keys else "no check"))))
        return tuple(found)


# --- what a change's checks say where there is only a sentence to say


def pipeline_alone(paths: Count) -> Finding:
    """An update of the installed pipeline changes nothing the project builds, runs or tests; the pipeline was
    verified where it is built. Running the project's suites over it costs minutes and proves nothing."""
    return SCOPE.note(Said(f"the commit changes only the installed pipeline and its skill copies ({paths.value} "
                           f"path(s)) — no project check runs; the pipeline is verified where it is built"))


def working_tree(head: typing.Optional[Detail]) -> Finding:
    return SNAPSHOT.note(Said("the working tree as it is" + (f", on top of {head.value}" if head else "")))


def out_of_scope(check: CheckName, required: typing.Tuple[CommandKey, ...]) -> Finding:
    """A check this scope does not run — and a required one a later scope (CI) has to run."""
    return check.skip(Said("not run in this scope" + (
        f" — {', '.join(k.value for k in required)} required, so a later scope (CI) has to run it"
        if required else "")))


def test_out_of_scope(key: CommandKey, requirement: Requirement) -> Finding:
    return CheckName(key.value).skip(Said("not run in this scope" + (
        " — it is required, so a later scope (CI) has to run it" if requirement is Requirement.REQUIRED else "")))


def missing_test(key: CommandKey) -> Finding:
    return TEST.fail(Said(f"no `{key.value}:` command in the stack profile — and `{key.value}` is required"))


def missing(check: CheckName, key: CommandKey, requirement: Requirement) -> Finding:
    required = requirement is Requirement.REQUIRED
    said = Said(f"no `{key.value}:` command in the stack profile"
                + (f" — and `{check.value}` is required" if required else ""))
    return check.fail(said) if required else check.skip(said)


def index_changed(before: Detail, after: Detail) -> Finding:
    return SNAPSHOT.fail(Said(f"the index changed while the checks ran ({before.value[:12]} → {after.value[:12]}) "
                              f"— what was checked is not what would be committed"))
