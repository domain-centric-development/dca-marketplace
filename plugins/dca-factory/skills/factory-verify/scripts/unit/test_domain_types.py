"""Which changed files are domain types (`invariants-cover`) and which places a round's question cites
(`minor-question`)."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.files.domain_types import changed_domain_types, is_test
from dca_factory.delivery.adapter.outgoing.files.round_questions import cited_places, place_key


def touched(paths, profile=None, method=False):
    with tempfile.TemporaryDirectory() as root:
        for path in paths:
            os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
            open(os.path.join(root, path), "w").close()
        if method:
            open(os.path.join(root, "dca.profile.yaml"), "w").close()
        return [name for name, _ in changed_domain_types(root, paths, profile or {})]


class DomainTypesTest(unittest.TestCase):

    def test_the_profiles_globs_place_the_layer(self):
        self.assertEqual(["Order"], touched(["src/core/model/Order.kt", "src/web/OrderPage.kt"],
                                            {"layer.domain": "src/core/model/*"}))

    def test_the_methods_layer_is_every_folder_named_domain(self):
        self.assertEqual(["Price", "Order"], touched(["src/Shop.Domain/Order.cs", "app/domain/model/price.py".replace(
            "price", "Price")], method=True))

    def test_without_either_no_type_is_known(self):
        self.assertEqual([], touched(["src/domain/Order.java"]))

    def test_tests_and_files_of_no_type_are_none(self):
        self.assertEqual([], touched(["src/test/java/x/domain/OrderTest.java", "src/main/java/x/domain/package-info.java",
                                      "app/domain/__init__.py"], method=True))
        self.assertTrue(is_test("tests/Shop.Tests/Domain/Order.cs"))


class CitedPlacesTest(unittest.TestCase):

    def test_a_place_by_file_name_and_line(self):
        self.assertEqual("Order.java:38", place_key("`src/main/java/x/Order.java:38`"))

    def test_every_place_once(self):
        self.assertEqual(["Order.java:38", "build.md:4"],
                         cited_places("see `src/Order.java:38`, `Order.java:38` and build.md:4"))


if __name__ == "__main__":
    unittest.main()
