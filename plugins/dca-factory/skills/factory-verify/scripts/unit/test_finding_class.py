"""A finding's class (WP-221): the judge is told exactly the lists the gate and the lessons read — target, type,
qualifier —, and a cell is read case and back ticks aside."""

import os
import re
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.domain.model.finding_class import FindingClass, FindingQualifier, FindingTarget, FindingType
from dca_factory.delivery.domain.model.story_words import Detail

RULE = os.path.join(support.SCRIPTS, "workflow", "rules", "stage", "STAGE-JUDGE-6A.md")


def told(name, text):
    """The words the judge is told for one list: what follows `<name>`, up to its closing parenthesis, the
    explanation between dashes left out."""
    listed = re.search(rf"`{name}`:?\s*\(?:?\s*(.*?)\)", text, re.S).group(1)
    listed = re.sub(r"—.*?—", "", listed, flags=re.S)
    return [w.strip() for w in re.split(r",", " ".join(listed.split())) if w.strip()]


class FindingClassTest(unittest.TestCase):

    def test_the_judge_is_told_exactly_the_lists_the_gate_reads(self):
        with open(RULE, encoding="utf-8") as handle:
            text = " ".join(handle.read().split())
        self.assertEqual([t.value for t in FindingTarget], told("Target", text))
        self.assertEqual([t.value for t in FindingType], told("Type", text))
        self.assertEqual([q.value for q in FindingQualifier], told("Qualifier", text))

    def test_traceability_is_a_type(self):
        found = FindingClass.written(Detail("test"), Detail("`Traceability`"), Detail("missing"))
        self.assertIs(FindingType.TRACEABILITY, found.type)
        self.assertEqual((Detail("ddd/test/traceability/missing"), Detail("test/traceability")),
                         found.keys(Detail("ddd")))
        self.assertIsNone(FindingClass.written(Detail("test"), Detail("trace"), Detail("missing")))


if __name__ == "__main__":
    unittest.main()
