"""Whether a scenario's `Then` names something only an incoming adapter produces (`adapter-shape`)."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.model.story_words import Clause, Count, ScenarioClauses, ScenarioKey
from dca_factory.delivery.domain.service.then_checks import adapter_produced


def scenario(when, *thens):
    return ScenarioClauses(ScenarioKey("k"), tuple(Clause(Count(n), Detail(t)) for n, t in enumerate(thens, 1)),
                           (Detail(when),))


class AdapterProducedTest(unittest.TestCase):

    def test_a_value_entered_with_spaces_and_shown_trimmed_is_the_use_cases(self):
        self.assertFalse(adapter_produced(scenario("the person records „  Alpha  “", "the list shows „Alpha“")))

    def test_a_value_shown_as_entered_is_the_use_cases(self):
        self.assertFalse(adapter_produced(scenario("the person records „A  B“", "the list shows „A  B“")))

    def test_a_then_without_a_quote_a_status_or_a_surface_is_the_use_cases(self):
        self.assertFalse(adapter_produced(scenario("the person records 200 letters", "the list shows one entry")))

    def test_a_text_the_when_did_not_enter_is_the_adapters(self):
        self.assertTrue(adapter_produced(scenario("the person records „Alpha“", "„1 entry, 1 open“ is shown")))

    def test_a_status_is_the_adapters(self):
        self.assertTrue(adapter_produced(scenario("the person opens entry 7", "the answer has status 404")))

    def test_a_number_the_when_named_is_no_status(self):
        self.assertFalse(adapter_produced(scenario("the person records 200 letters", "the list shows 200 letters")))

    def test_a_control_or_a_message_is_the_adapters(self):
        self.assertTrue(adapter_produced(scenario("the person presses „Done“", "„Alpha“ carries no button „Done“")))
        self.assertTrue(adapter_produced(scenario("the person records „Alpha“", "no message is shown")))
        self.assertTrue(adapter_produced(scenario("the person records „Alpha“", "das Feld Titel ist leer")))


if __name__ == "__main__":
    unittest.main()
