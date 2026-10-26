"""Several factories on one backlog (WP-93): a bare repository as the remote and two clones as two factories — the
claim, the lost race, an own claim, an id collision, a branch rule, the release, a free id, and a published story
merged by the code host."""

import contextlib
import io
import os
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

from support import evidence, gate_story, state, verdict, write
from dca_factory import cli
from dca_factory.delivery.domain.service.spec_checks import SpecChecks
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles
from dca_factory.delivery.adapter.outgoing.files import story_layout as layout
from dca_factory.sharedkernel.adapter.outgoing.markdown import front_matter as markdown
from dca_factory.delivery.adapter.outgoing.git import worktrees, worktree_steps
from dca_factory.delivery.adapter.outgoing.files import snapshots
from dca_factory.delivery.adapter.outgoing.claims import remote_claims
from dca_factory.delivery.adapter.outgoing.files import delivery_writes

PROFILE = "claim_remote: origin\n"
EPIC = "---\nintent: x\ngoal: y\nmetric: ThingShown\ndomain_contact: z\n---\n# sample\n"
STORY = """---
id: {id}
epic: sample
status: approved
context: Widgets
title: {title}
depends_on: []
---
# {title}

## Acceptance criteria

- shows-{id_lower}: The reader sees {title}.
"""


def sh(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
        return function(*args, **kwargs), out.getvalue()


class Remote:
    """A bare remote seeded with one epic and two stories, and clones as factories."""

    def __init__(self, root):
        self.root = root
        self.bare = os.path.join(root, "remote.git")
        sh(root, "init", "--quiet", "--bare", "-b", "main", self.bare)
        seed = os.path.join(root, "seed")
        sh(root, "clone", "--quiet", self.bare, seed)
        self.identity(seed, "seed@example.com")
        write(os.path.join(seed, profiles.PROFILE_FILE), PROFILE)
        write(os.path.join(seed, "product", "epics", "sample", "epic.md"), EPIC)
        for sid, title in (("S-01", "the first thing"), ("S-02", "the second thing")):
            write(os.path.join(seed, "product", "epics", "sample", sid, "story.md"),
                  STORY.format(id=sid, title=title, id_lower=sid.lower()))
        sh(seed, "add", "-A")
        sh(seed, "commit", "--quiet", "-m", "seed")
        sh(seed, "push", "--quiet", "origin", "HEAD:main")

    @staticmethod
    def identity(path, email):
        sh(path, "config", "user.email", email)
        sh(path, "config", "user.name", email.split("@")[0])

    def clone(self, name, email):
        path = os.path.join(self.root, name)
        sh(self.root, "clone", "--quiet", self.bare, path)
        self.identity(path, email)
        return os.path.realpath(path)


@contextlib.contextmanager
def remote():
    here = os.getcwd()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        try:
            yield Remote(os.path.realpath(root))
        finally:
            os.chdir(here)
            profiles.set_places({})


def at(path):
    """Work in one clone: its places, its run folder."""
    os.chdir(path)
    profiles.set_places(profiles.read_profile(profiles.PROFILE_FILE))
    return os.path.join(path, ".dca-factory", "runs"), os.path.join(path, "product", "epics")


CONFIG = {"remote": "origin", "prefix": "story/"}


class Claim(unittest.TestCase):

    def test_two_factories_one_story_the_second_skips_and_sees_who(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            runs_a, epics_a = at(a)
            self.assertEqual(quiet(cli.claim_command, a, runs_a, epics_a, "S-01")[0], 0)
            runs_b, epics_b = at(b)
            code, said = quiet(cli.claim_command, b, runs_b, epics_b, "S-01")
            self.assertEqual(code, 3, said)
            self.assertIn("claimed by ana@example.com", said)
            front = markdown.read_front_matter(layout.find_story(epics_b, "S-01"))[0]
            self.assertEqual(state.story_state(b, runs_b, "S-01", front)[0], "claimed")
            other = markdown.read_front_matter(layout.find_story(epics_b, "S-02"))[0]
            self.assertEqual(state.story_state(b, runs_b, "S-02", other)[0], "ready")

    def test_the_race_between_fetch_and_push_is_lost_by_the_second_push(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            runs_b, epics_b = at(b)
            sh(b, "fetch", "--quiet")                      # b looked before a claimed
            runs_a, epics_a = at(a)
            quiet(cli.claim_command, a, runs_a, epics_a, "S-01")
            runs_b, epics_b = at(b)
            real, calls = remote_claims.fetch_remote, []

            def stale_first(cwd, name):                    # the fetch before the push saw no claim yet
                calls.append(name)
                return (0, "") if len(calls) == 1 else real(cwd, name)
            with mock.patch.object(remote_claims, "fetch_remote", side_effect=stale_first):
                code, said = quiet(remote_claims.claim_story, b, runs_b, CONFIG, "main", "S-01", "sample", "the first thing")
            self.assertEqual(code, 3, said)

    def test_an_own_claim_resumes_and_the_same_person_on_another_host_is_foreign(self):
        with remote() as r:
            a = r.clone("a", "ana@example.com")
            runs, epics = at(a)
            quiet(cli.claim_command, a, runs, epics, "S-01")
            self.assertEqual(quiet(cli.claim_command, a, runs, epics, "S-01")[0], 0)
            elsewhere = r.clone("a2", "ana@example.com")
            runs2, epics2 = at(elsewhere)
            with mock.patch.object(socket, "gethostname", return_value="another-laptop"):
                self.assertEqual(quiet(cli.claim_command, elsewhere, runs2, epics2, "S-01")[0], 3)

    def test_an_id_collision_is_no_skip_and_a_branch_rule_is_no_lost_race(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            runs_a, epics_a = at(a)
            quiet(cli.claim_command, a, runs_a, epics_a, "S-01")
            runs_b, _e = at(b)
            code, said = quiet(remote_claims.claim_story, b, runs_b, CONFIG, "main", "S-01", "sample", "a different thing")
            self.assertEqual(code, 4, said)
            self.assertIn("id collision", said)
            hook = os.path.join(r.bare, "hooks", "pre-receive")
            write(hook, "#!/bin/sh\nwhile read old new ref; do case $ref in refs/heads/story/*) "
                        "echo 'branch names need a ticket key' >&2; exit 1;; esac; done\n")
            os.chmod(hook, 0o755)
            code, said = quiet(remote_claims.claim_story, b, runs_b, CONFIG, "main", "S-02", "sample", "the second thing")
            self.assertEqual(code, 4, said)
            self.assertIn("not a lost race", said)

    def test_release_is_the_owners_or_forced_and_without_the_key_nothing_is_pushed(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            runs_a, epics_a = at(a)
            quiet(cli.claim_command, a, runs_a, epics_a, "S-01")
            runs_b, _e = at(b)
            self.assertEqual(quiet(remote_claims.release_claim, b, runs_b, CONFIG, "S-01")[0], 1)
            self.assertEqual(quiet(remote_claims.release_claim, b, runs_b, CONFIG, "S-01", True)[0], 0)
            self.assertEqual(sh(r.root, "--git-dir", r.bare, "branch", "--list", "story/*"), "")
            plain = r.clone("plain", "pia@example.com")
            os.remove(os.path.join(plain, profiles.PROFILE_FILE))
            runs_p, epics_p = at(plain)
            self.assertEqual(quiet(cli.claim_command, plain, runs_p, epics_p, "S-02")[0], 0)
            self.assertEqual(sh(r.root, "--git-dir", r.bare, "branch", "--list", "story/*"), "")


class Ids(unittest.TestCase):

    def test_a_free_id_skips_local_remote_claimed_and_delivered_and_deleted_ids(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            runs_a, epics_a = at(a)
            quiet(remote_claims.claim_story, a, runs_a, CONFIG, "main", "S-05", "sample", "a claimed one")
            sh(a, "commit", "--quiet", "--allow-empty", "-m", "feat: gone\n\nStory: S-07")
            sh(a, "push", "--quiet", "origin", "HEAD:main")
            runs_b, epics_b = at(b)
            write(os.path.join(epics_b, "sample", "S-03", "story.md"), STORY.format(id="S-03", title="t", id_lower="s-03"))
            self.assertEqual(remote_claims.free_id(b, epics_b, CONFIG, "main", "S"), "S-08")


class Published(unittest.TestCase):

    def test_a_delivered_story_is_published_on_its_branch_and_released_when_the_host_merged_it(self):
        with remote() as r:
            a = r.clone("a", "ana@example.com")
            runs, epics = at(a)
            quiet(cli.claim_command, a, runs, epics, "S-01")
            os.makedirs(os.path.join(runs, "S-01"), exist_ok=True)
            write(os.path.join(profiles.evidence_dir(runs, "S-01"), "target"), "main\n")
            quiet(worktree_steps.worktree_prepare, a, runs, "S-01")
            wt = worktrees.worktree_of("S-01", a)
            write(os.path.join(wt, "src", "thing.txt"), "the first thing\n")
            write(os.path.join(profiles.evidence_dir(runs, "S-01"), snapshots.STAGES_MADE), "src/thing.txt\n")
            write(os.path.join(runs, "S-01", "tests.md"),
                  "<!-- gate:tests -->\n| criterion | test |\n|---|---|\n| shows-s-01 | a.ThingTest#shows |\n")
            self.assertEqual(quiet(worktree_steps.integrate_prepare, a, runs, epics, "S-01")[0], 0)
            result = verdict()
            front = markdown.read_front_matter(layout.find_story(epics, "S-01"))[0]
            with mock.patch.dict(os.environ, {profiles.HOME_VARIABLE: a}):
                os.chdir(wt)
                delivery_writes.publish_story(result, wt, layout.find_story(epics, "S-01"), "S-01", front, runs, CONFIG)
                os.chdir(a)
            self.assertFalse([e for e in result.entries if e[0] == "fail"], result.entries)
            published = sh(a, "show", "origin/story/S-01:product/epics/sample/S-01/story.md")
            self.assertIn("status: delivered", published)
            self.assertIn("delivered_by: gate", published)
            self.assertIn("Test: a.ThingTest#shows", sh(a, "show", "origin/story/S-01:product/spec/widgets/scenarios.md"))
            self.assertIn("Factory-Claim: ana@example.com", sh(a, "log", "-1", "--format=%B", "origin/story/S-01"))
            self.assertEqual(sh(a, "rev-parse", "main"), sh(a, "rev-parse", "origin/main"))   # main not moved
            self.assertEqual(state.story_state(a, runs, "S-01", front)[0], "published")
            # the code host squashes it under its own message
            host = r.clone("host", "host@example.com")
            sh(host, "merge", "--quiet", "--squash", "origin/story/S-01")
            sh(host, "commit", "--quiet", "-m", "Merge request !12")
            sh(host, "push", "--quiet", "origin", "HEAD:main")
            quiet(remote_claims.refresh_claims, a, runs, CONFIG, "main")
            self.assertEqual(sh(r.root, "--git-dir", r.bare, "branch", "--list", "story/*"), "")
            self.assertNotEqual(state.story_state(a, runs, "S-01", front)[0], "published")


    def publish(self, r, clone, story):
        runs, epics = at(clone)
        quiet(cli.claim_command, clone, runs, epics, story)
        os.makedirs(os.path.join(runs, story), exist_ok=True)
        write(os.path.join(profiles.evidence_dir(runs, story), "target"), "main\n")
        quiet(worktree_steps.worktree_prepare, clone, runs, story)
        wt = worktrees.worktree_of(story, clone)
        write(os.path.join(wt, "src", f"{story}.txt"), "x\n")
        write(os.path.join(profiles.evidence_dir(runs, story), snapshots.STAGES_MADE), f"src/{story}.txt\n")
        write(os.path.join(runs, story, "tests.md"), "<!-- gate:tests -->\n| criterion | test |\n|---|---|\n"
                                                    f"| shows-{story.lower()} | a.ThingTest#{story.replace('-', '')} |\n")
        quiet(worktree_steps.integrate_prepare, clone, runs, epics, story)
        result = verdict()
        front = markdown.read_front_matter(layout.find_story(epics, story))[0]
        with mock.patch.dict(os.environ, {profiles.HOME_VARIABLE: clone}):
            os.chdir(wt)
            delivery_writes.publish_story(result, wt, layout.find_story(epics, story), story, front, runs, CONFIG)
            os.chdir(clone)
        self.assertFalse([e for e in result.entries if e[0] == "fail"], result.entries)
        return runs, epics, wt

    def test_a_published_branch_whose_merge_request_lost_the_race_is_taken_back_not_resolved(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            self.publish(r, a, "S-01")
            runs_b, epics_b, wt_b = self.publish(r, b, "S-02")
            host = r.clone("host", "host@example.com")
            sh(host, "merge", "--quiet", "--squash", "origin/story/S-01")
            sh(host, "commit", "--quiet", "-m", "Merge request !1")
            sh(host, "push", "--quiet", "origin", "HEAD:main")
            at(b)
            code, said = quiet(cli.undeliver_branch, b, runs_b, epics_b, "S-02")
            self.assertEqual(code, 0, said)
            spec = read_file(os.path.join(wt_b, "product", "spec", "widgets", "scenarios.md"))
            self.assertIn("shows-s-01", spec)                  # the remote's spec, not this branch's merge
            self.assertNotIn("shows-s-02", spec)
            story = read_file(os.path.join(wt_b, "product", "epics", "sample", "S-02", "story.md"))
            self.assertIn("status: approved", story)
            self.assertNotIn("delivered_by", story)
            self.assertFalse(os.path.isfile(os.path.join(profiles.evidence_dir(runs_b, "S-02"), remote_claims.PUBLISHED)))

    def test_a_hand_delivery_of_a_story_another_factory_claimed_is_refused(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            runs_a, epics_a = at(a)
            quiet(cli.claim_command, a, runs_a, epics_a, "S-01")
            runs_b, epics_b = at(b)
            code, said = quiet(cli.deliver_by_hand, b, runs_b, epics_b, "S-01", "ben")
            self.assertEqual(code, 1, said)
            self.assertIn("claimed by ana@example.com", said)
            self.assertEqual(quiet(cli.deliver_by_hand, b, runs_b, epics_b, "S-01", "ben", True)[0], 0)


    def test_two_clones_adding_one_key_otherwise_the_second_is_stopped_at_integrate(self):
        with remote() as r:
            a, b = r.clone("a", "ana@example.com"), r.clone("b", "ben@example.com")
            same = "- shows-s-01: The reader sees the thing in bold.\n"
            path_b = os.path.join(b, "product", "epics", "sample", "S-02", "story.md")
            text = read_file(path_b).replace("- shows-s-02: The reader sees the second thing.\n", same)
            write(path_b, text)
            sh(b, "commit", "--quiet", "-am", "S-02 says it differently")
            self.publish(r, a, "S-01")
            host = r.clone("host", "host@example.com")
            sh(host, "merge", "--quiet", "--squash", "origin/story/S-01")
            sh(host, "commit", "--quiet", "-m", "Merge request !1")
            sh(host, "push", "--quiet", "origin", "HEAD:main")
            runs_b, epics_b = at(b)
            quiet(cli.claim_command, b, runs_b, epics_b, "S-02")
            os.makedirs(os.path.join(runs_b, "S-02"), exist_ok=True)
            write(os.path.join(profiles.evidence_dir(runs_b, "S-02"), "target"), "main\n")
            write(os.path.join(runs_b, "S-02", "plan.md"), "# Plan\n\n## Spec delta\n- adds shows-s-01\n")
            quiet(worktree_steps.worktree_prepare, b, runs_b, "S-02")
            wt = worktrees.worktree_of("S-02", b)
            quiet(worktree_steps.integrate_prepare, b, runs_b, epics_b, "S-02")
            story_path = layout.find_story(epics_b, "S-02")
            front, body = markdown.read_front_matter(story_path)
            with mock.patch.dict(os.environ, {profiles.HOME_VARIABLE: b}):
                with profiles.places_in(wt):
                    result = verdict(SpecChecks.delta(gate_story("S-02", story_path, front, body),
                                                      evidence(wt, runs_b)))
            self.assertTrue(any(e[0] == "fail" and e[1] == "spec-delta" for e in result.entries), result.entries)


def read_file(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


if __name__ == "__main__":
    unittest.main()
