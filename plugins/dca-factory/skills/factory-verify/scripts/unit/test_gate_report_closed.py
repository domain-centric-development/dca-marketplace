"""The gate's report outlives the call that wrote it: when the tee onto report and terminal is collected after the
report was closed, it says nothing — no "Exception ignored while finalizing" in the runner's log."""

import gc
import io
import os
import sys
import tempfile
import unittest

from dca_factory.delivery.adapter.outgoing.process.gate_process import _Both


class GateReportClosed(unittest.TestCase):

    def setUp(self):
        folder = tempfile.mkdtemp()
        self.report = os.path.join(folder, "gate-report.txt")

    def test_a_tee_collected_after_its_report_closed_raises_nothing(self):
        caught = []
        hook, sys.unraisablehook = sys.unraisablehook, caught.append
        try:
            with open(self.report, "w", encoding="utf-8") as kept:
                both = _Both(kept, io.StringIO())
                both.write("gate:pass story\n")
            del both
            gc.collect()
        finally:
            sys.unraisablehook = hook
        self.assertEqual([str(c.exc_value) for c in caught], [])

    def test_the_report_holds_what_the_tee_wrote(self):
        shown = io.StringIO()
        with open(self.report, "w", encoding="utf-8") as kept:
            _Both(kept, shown).write("gate:pass story\n")
        with open(self.report, encoding="utf-8") as read:
            self.assertEqual((read.read(), shown.getvalue()), ("gate:pass story\n", "gate:pass story\n"))


if __name__ == "__main__":
    unittest.main()
