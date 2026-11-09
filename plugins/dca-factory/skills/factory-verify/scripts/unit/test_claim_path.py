"""Where a checkout's claim lies: in its own git folder, asked once per process — and a folder that is no repository
yet never keeps the git folder of one above it, or every project below that one would share a claim."""

import os
import shutil
import subprocess
import tempfile
import unittest

import support  # noqa: F401 — the package on the path

from dca_factory.delivery.adapter.outgoing.claims import checkout_claim


def init(folder):
    subprocess.run(["git", "init", "-q", folder], capture_output=True, check=True)


class ClaimPath(unittest.TestCase):

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        checkout_claim.OWN_GIT.clear()

    def test_a_project_below_a_repository_gets_its_own_claim_once_it_is_one(self):
        init(self.root)
        project = os.path.join(self.root, "project")
        os.makedirs(project)
        before = checkout_claim.claim_path(project)
        self.assertTrue(before.startswith(os.path.join(self.root, ".git")), before)
        init(project)
        self.assertEqual(os.path.realpath(checkout_claim.claim_path(project)),
                         os.path.join(project, ".git", "dca-factory-worker.lock"))

    def test_a_checkout_s_own_git_folder_is_asked_once(self):
        init(self.root)
        first = checkout_claim.claim_path(self.root)
        self.assertIn(os.path.abspath(self.root), checkout_claim.OWN_GIT)
        self.assertEqual(checkout_claim.claim_path(self.root), first)


if __name__ == "__main__":
    unittest.main()
