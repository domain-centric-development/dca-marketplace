"""One observation per window edge (WP-202): the working tree at a window's start and end, kept in one file per edge,
read back as written; a stage's changes and the story's record taken from the two edges alone."""

import os
import subprocess
import tempfile
import unittest

from support import write
from dca_factory.sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from dca_factory.delivery.adapter.outgoing.files import snapshots
from dca_factory.delivery.domain.model.tree_observation import Hashing

STORY = "S-1"


def git(cwd, *args):
    done = subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, capture_output=True,
                          text=True, check=True)
    return done.stdout.strip()


class TreeObservationTest(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.runs = os.path.join(self.root, ".dca-factory", "runs")
        self.folder = evidence_dir(self.runs, STORY)
        git(self.root, "init", "-q", "-b", "main")
        write(os.path.join(self.root, ".gitignore"), ".dca-factory/\n")
        write(os.path.join(self.root, "src", "A.txt"), "a\n")
        write(os.path.join(self.root, "src", "B.txt"), "b\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")

    def tearDown(self):
        self.scratch.cleanup()

    def edge(self, edge, window="build"):
        snapshots.observe_edge(self.root, self.folder, edge, window)
        return snapshots.read_observation(snapshots.observation_path(self.folder, edge, window))

    def record(self, window="build"):
        snapshots.record_changes(self.root, self.runs, STORY, window)
        with open(os.path.join(self.folder, f"changed-{window}.txt"), encoding="utf-8") as handle:
            return handle.read().splitlines()

    def test_an_observation_reads_back_as_it_was_taken(self):
        write(os.path.join(self.root, "src", "A.txt"), "a, changed\n")
        os.remove(os.path.join(self.root, "src", "B.txt"))
        write(os.path.join(self.root, "src", "new dir", "C D.txt"), "c\n")
        taken = snapshots.observe(self.root, snapshots.Take.WITH_TREE)
        path = os.path.join(self.folder, "tree-after-x.txt")
        snapshots.write_observation(path, taken)
        read = snapshots.read_observation(path)
        self.assertEqual(read, taken)
        self.assertEqual(taken.head.value, git(self.root, "rev-parse", "HEAD"))
        self.assertEqual({f.place.value: f.tracked for f in taken.files},
                         {"src/A.txt": True, "src/B.txt": True,
                          "src/new dir/C D.txt": False})
        self.assertEqual(snapshots.load_snapshot(path)["src/B.txt"], "deleted")
        # the tree is the one a commit of everything now would hold
        git(self.root, "add", "-A")
        self.assertEqual(taken.tree.value, git(self.root, "write-tree"))

    def test_a_start_takes_the_base_once_and_no_tree_after_it(self):
        start = self.edge(snapshots.Edge.START, "plan")
        with open(os.path.join(self.folder, snapshots.BASE_TREE), encoding="utf-8") as handle:
            self.assertEqual(handle.read().strip(), git(self.root, "rev-parse", "HEAD^{tree}"))
        self.assertEqual(start.tree.value, git(self.root, "rev-parse", "HEAD^{tree}"))
        self.assertIsNone(self.edge(snapshots.Edge.START, "test").tree)
        self.assertIsNotNone(self.edge(snapshots.Edge.END, "test").tree)

    def test_a_window_that_changed_nothing_records_nothing(self):
        write(os.path.join(self.root, "src", "A.txt"), "changed before the window\n")
        self.edge(snapshots.Edge.START)
        self.edge(snapshots.Edge.END)
        self.assertEqual(self.record(), [])
        with open(os.path.join(self.folder, "changed.txt"), encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), [])   # the base is the tree at the window's start

    def test_a_file_changed_and_changed_back_is_no_change(self):
        self.edge(snapshots.Edge.START)
        write(os.path.join(self.root, "src", "A.txt"), "a, for a moment\n")
        write(os.path.join(self.root, "src", "A.txt"), "a\n")
        self.edge(snapshots.Edge.END)
        self.assertEqual(self.record(), [])
        with open(os.path.join(self.folder, "story.diff"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "")

    def test_untracked_files_are_added_and_removed_by_the_window(self):
        write(os.path.join(self.root, "src", "Old.txt"), "made before\n")
        self.edge(snapshots.Edge.START)
        os.remove(os.path.join(self.root, "src", "Old.txt"))
        write(os.path.join(self.root, "src", "New.txt"), "made in the window\n")
        os.remove(os.path.join(self.root, "src", "B.txt"))
        self.edge(snapshots.Edge.END)
        self.assertEqual(self.record(), ["removed\tsrc/B.txt", "added\tsrc/New.txt", "removed\tsrc/Old.txt"])
        with open(os.path.join(self.folder, "changed.txt"), encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(),       # against the base: the tree at the window's start
                             ["removed\tsrc/B.txt", "added\tsrc/New.txt", "removed\tsrc/Old.txt"])
        with open(os.path.join(self.folder, "story.diff"), encoding="utf-8") as handle:
            diff = handle.read()
        self.assertIn("+made in the window", diff)
        self.assertIn("-b", diff)
        with open(os.path.join(self.folder, snapshots.STAGES_MADE), encoding="utf-8") as handle:
            self.assertIn("src/New.txt", handle.read().splitlines())

    def test_a_window_that_committed_keeps_what_it_committed(self):
        self.edge(snapshots.Edge.START)
        write(os.path.join(self.root, "src", "A.txt"), "a, committed in the window\n")
        git(self.root, "commit", "-qam", "a stage commits")
        self.edge(snapshots.Edge.END)
        self.assertEqual(self.record(), ["modified\tsrc/A.txt"])

    def test_an_observation_without_digests_says_so_and_the_record_does_not_read_it(self):
        snapshots.observe_edge(self.root, self.folder, snapshots.Edge.START, "build", Hashing.NAMES_ONLY)
        snapshots.observe_edge(self.root, self.folder, snapshots.Edge.END, "build", Hashing.NAMES_ONLY)
        path = snapshots.observation_path(self.folder, snapshots.Edge.START, "build")
        with open(path, encoding="utf-8") as handle:
            self.assertTrue(handle.readline().startswith("# no-sha256-command"))
        self.assertIsNone(snapshots.load_snapshot(path))
        self.assertTrue(self.record()[0].startswith(snapshots.NOT_OBSERVED))

    def test_an_older_releases_snapshot_is_read_with_the_index_for_tracking(self):
        self.edge(snapshots.Edge.START)
        with open(snapshots.observation_path(self.folder, snapshots.Edge.START, "build"), "w", encoding="utf-8") as h:
            h.write("")                                       # an older release: nothing changed, no header
        write(os.path.join(self.root, "src", "New.txt"), "new\n")
        write(os.path.join(self.root, "src", "A.txt"), "a, changed\n")
        self.edge(snapshots.Edge.END)
        self.assertEqual(self.record(), ["modified\tsrc/A.txt", "added\tsrc/New.txt"])

    def test_outside_a_repository_nothing_is_observed_and_the_record_says_why(self):
        with tempfile.TemporaryDirectory() as plain:
            runs = os.path.join(plain, ".dca-factory", "runs")
            folder = evidence_dir(runs, STORY)
            for edge in (snapshots.Edge.START, snapshots.Edge.END):
                snapshots.observe_edge(plain, folder, edge, "build")
            self.assertIsNone(snapshots.read_observation(snapshots.observation_path(folder, snapshots.Edge.END, "build")))
            snapshots.record_changes(plain, runs, STORY, "build")
            with open(os.path.join(folder, "changed-build.txt"), encoding="utf-8") as handle:
                self.assertTrue(handle.read().startswith(snapshots.NOT_OBSERVED))


if __name__ == "__main__":
    unittest.main()
