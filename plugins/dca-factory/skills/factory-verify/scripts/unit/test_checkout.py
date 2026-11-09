"""One checkout per run (WP-202): where a folder sits in git — its top, its git folder, the one its worktrees share, its
prefix, its index — asked once for a run, a gate call or a cli call, never kept past it. A folder below a repository is
in that repository until it is one of its own; the first run after its `git init` gets its own checkout, never the one
above (the WP-197 trap: a cache with no lifetime gave every fixture below a repository one claim)."""

import argparse
import os
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import support  # noqa: F401 — the package on the path

from dca_factory.delivery.adapter.outgoing.claims import checkout_claim
from dca_factory.delivery.adapter.outgoing.git import checkout
from dca_factory.delivery.adapter.outgoing.git.checkout import Checkouts, checkout_of
from dca_factory.infrastructure import runner


def git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, capture_output=True,
                          text=True, check=True)
    return done.stdout.strip()


def commit(cwd, name, text):
    with open(os.path.join(cwd, name), "w", encoding="utf-8") as handle:
        handle.write(text)
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", name)


class CheckoutOfAFolder(unittest.TestCase):

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_a_repository_s_top_its_git_folder_and_its_index(self):
        git(self.root, "init", "-q", "-b", "main")
        found = checkout_of(self.root)
        self.assertEqual(found.top, self.root)
        self.assertEqual(found.git_dir, os.path.join(self.root, ".git"))
        self.assertEqual(found.common_dir, os.path.join(self.root, ".git"))
        self.assertEqual(found.prefix, "")
        self.assertEqual(found.index_file, os.path.join(self.root, ".git", "index"))

    def test_a_folder_below_the_top_is_entered_with_its_prefix(self):
        git(self.root, "init", "-q", "-b", "main")
        os.makedirs(os.path.join(self.root, "a", "b"))
        found = checkout_of(os.path.join(self.root, "a", "b"))
        self.assertEqual((found.top, found.prefix), (self.root, "a/b/"))

    def test_a_folder_outside_any_repository_has_none(self):
        self.assertIsNone(checkout_of(self.root))

    def test_head_is_read_now_from_the_files_never_kept(self):
        git(self.root, "init", "-q", "-b", "main")
        found = checkout_of(self.root)
        self.assertIsNone(found.head())                                  # no commit yet: the caller asks git
        commit(self.root, "a.txt", "a\n")
        self.assertEqual(found.head(), git(self.root, "rev-parse", "HEAD"))
        commit(self.root, "b.txt", "b\n")                                # HEAD moved: the same checkout says so
        self.assertEqual(found.head(), git(self.root, "rev-parse", "HEAD"))
        git(self.root, "pack-refs", "--all")                             # a packed ref reads as well
        self.assertEqual(found.head(), git(self.root, "rev-parse", "HEAD"))
        git(self.root, "checkout", "-q", "--detach")
        self.assertEqual(found.head(), git(self.root, "rev-parse", "HEAD"))

    def test_a_worktree_is_a_checkout_of_its_own_sharing_the_git_folder(self):
        git(self.root, "init", "-q", "-b", "main")
        commit(self.root, "a.txt", "a\n")
        tree = os.path.join(self.root, "wt")
        git(self.root, "worktree", "add", "-q", "-b", "story", tree)
        own = checkout_of(tree)
        self.assertEqual(own.top, tree)
        self.assertNotEqual(own.git_dir, os.path.join(self.root, ".git"))
        self.assertEqual(own.common_dir, os.path.join(self.root, ".git"))
        self.assertEqual(own.head(), git(tree, "rev-parse", "HEAD"))


class CheckoutsLifetime(unittest.TestCase):

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        git(self.root, "init", "-q", "-b", "main")

    def test_a_run_asks_git_once_per_checkout(self):
        checkouts = Checkouts()
        with mock.patch.object(checkout, "checkout_of", wraps=checkout_of) as asked:
            for _ in range(5):
                checkout_claim.claim_path(self.root, checkouts)
        self.assertEqual(asked.call_count, 1)

    def test_entering_a_folder_asks_again_and_leaving_it_forgets_it(self):
        checkouts = Checkouts()
        with mock.patch.object(checkout, "checkout_of", wraps=checkout_of) as asked:
            checkouts.at(self.root)
            checkouts.enter(self.root)
            checkouts.leave(self.root)
            checkouts.at(self.root)
        self.assertEqual(asked.call_count, 3)

    def test_without_a_run_s_checkouts_every_call_asks_for_itself(self):
        with mock.patch.object(checkout, "checkout_of", wraps=checkout_of) as asked:
            checkout_claim.claim_path(self.root)
            checkout_claim.claim_path(self.root)
        self.assertEqual(asked.call_count, 2)

    def test_nothing_is_kept_at_module_level(self):
        for module in (checkout, checkout_claim):
            kept = [name for name, value in vars(module).items()
                    if not name.startswith("__") and isinstance(value, (dict, set, list))]
            self.assertEqual(kept, [], module.__name__)

    def test_a_run_and_the_gate_it_calls_share_one_set_of_checkouts(self):
        options = argparse.Namespace(max_stages=None, story_budget=None, builder="", verifier="", parallel=1)
        with mock.patch.object(runner, "place", return_value=".dca-factory/runs"):
            run = runner.wired_run(options, self.root, "unit:host:1")
        self.assertIs(run.cases._checkouts, run.checkouts)


class FolderBelowARepository(unittest.TestCase):
    """The WP-197 trap: a fixture folder with no `.git` of its own lies below a repository (the Windows runner's temp
    folder does). It is in that repository while it is no repository itself; once it is one, the next run gets its own
    checkout and claim — the outer repository's git folder is never carried over."""

    def setUp(self):
        self.outer = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.outer, True)
        git(self.outer, "init", "-q", "-b", "main")
        self.project = os.path.join(self.outer, "fixture")
        os.makedirs(self.project)

    def test_the_next_run_after_git_init_gets_the_folder_s_own_checkout(self):
        first_run = Checkouts()
        before = first_run.at(self.project)
        self.assertEqual((before.top, before.prefix), (self.outer, "fixture/"))
        git(self.project, "init", "-q", "-b", "main")
        mine = Checkouts().at(self.project)                              # the next run, the next gate or cli call
        self.assertEqual((mine.top, mine.git_dir, mine.prefix), (self.project, os.path.join(self.project, ".git"), ""))
        self.assertEqual(checkout_claim.claim_path(self.project),
                         os.path.join(self.project, ".git", "dca-factory-worker.lock"))

    def test_two_fixtures_that_are_repositories_never_share_a_claim(self):
        other = os.path.join(self.outer, "other")
        os.makedirs(other)
        for folder in (self.project, other):
            git(folder, "init", "-q", "-b", "main")
        claims = {checkout_claim.claim_path(folder, Checkouts()) for folder in (self.project, other)}
        self.assertEqual(len(claims), 2)
        self.assertFalse(any(path.startswith(os.path.join(self.outer, ".git")) for path in claims), claims)

    def test_a_run_entering_a_folder_that_became_a_repository_asks_again(self):
        run = Checkouts()
        run.at(self.project)
        git(self.project, "init", "-q", "-b", "main")
        self.assertEqual(run.enter(self.project).top, self.project)


if __name__ == "__main__":
    unittest.main()
