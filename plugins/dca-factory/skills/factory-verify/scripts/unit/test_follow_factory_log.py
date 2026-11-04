"""The factory's log followed (WP-183): its last lines first, then each whole line as it is written, from its start
again once it was kept aside and begun anew."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.status.follow_factory_log import FollowFactoryLogQuery, FollowFactoryLogUseCase


class Log:
    def __init__(self, text=None):
        self.text = text

    def size(self):
        return None if self.text is None else len(self.text)

    def read(self, offset):
        return self.text[offset:], len(self.text)


class TheFactorysLogFollowed(unittest.TestCase):
    def test_none_written_yet(self):
        followed = FollowFactoryLogUseCase(Log()).execute(FollowFactoryLogQuery())
        self.assertEqual((False, []), (followed.written, followed.lines))

    def test_first_its_last_lines_then_each_whole_line_added(self):
        log = Log("".join(f"line {n}\n" for n in range(5)))
        follow = FollowFactoryLogUseCase(log)
        first = follow.execute(FollowFactoryLogQuery(tail=2))
        self.assertEqual(["line 3", "line 4"], first.lines)
        log.text += "line 5\r\nhalf"
        later = follow.execute(FollowFactoryLogQuery(first.offset, first.pending))
        self.assertEqual((["line 5"], "half"), (later.lines, later.pending))
        log.text += " done\n"
        self.assertEqual(["half done"], follow.execute(FollowFactoryLogQuery(later.offset, later.pending)).lines)

    def test_a_log_begun_anew_is_read_from_its_start(self):
        log = Log("a long first log\n")
        follow = FollowFactoryLogUseCase(log)
        first = follow.execute(FollowFactoryLogQuery())
        log.text = "new\n"
        self.assertEqual(["new"], follow.execute(FollowFactoryLogQuery(first.offset, first.pending)).lines)


if __name__ == "__main__":
    unittest.main()
