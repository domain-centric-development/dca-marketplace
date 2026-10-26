"""The building blocks (WP-152): a value compares by its attributes and cannot change — a frozen dataclass by its base,
without a decorator —, an entity by its id, an aggregate collects its events until they are cleared, and the failures
of the domain and of a use case stay apart."""

import dataclasses
import typing
import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory import building_blocks as bb


class ThingId(bb.Id):
    value: str


class Colour(bb.Value):
    value: str

    def __post_init__(self) -> None:
        if not self.value.isalpha():
            raise ValueError(f"{self.value!r} is no colour")


class Painted(bb.DomainEvent):
    thing: ThingId
    colour: Colour


class Thing(bb.AggregateRoot[ThingId]):
    def __init__(self, thing_id: ThingId, colour: Colour) -> None:
        super().__init__()
        self._id, self.colour = thing_id, colour

    @property
    def id(self) -> ThingId:
        return self._id

    def paint(self, colour: Colour) -> None:
        self.colour = colour
        self.register_event(Painted(self._id, colour))


class Things(bb.Repository[Thing, ThingId], typing.Protocol):
    """A port: a repository of things."""


class InMemoryThings:
    def __init__(self) -> None:
        self.kept: typing.Dict[ThingId, Thing] = {}

    def find_by_id(self, aggregate_id: ThingId) -> typing.Optional[Thing]:
        return self.kept.get(aggregate_id)

    def save(self, aggregate: Thing) -> Thing:
        self.kept[aggregate.id] = aggregate
        return aggregate

    def delete_by_id(self, aggregate_id: ThingId) -> None:
        self.kept.pop(aggregate_id, None)


class BuildingBlocksTest(unittest.TestCase):

    def test_a_value_is_its_attributes_and_cannot_change(self):
        self.assertEqual(Colour("red"), Colour("red"))
        self.assertNotEqual(Colour("red"), Colour("blue"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            Colour("red").value = "blue"  # type: ignore[misc]
        self.assertIsInstance(ThingId("t"), bb.Value)

    def test_the_base_makes_a_value_and_an_event_a_frozen_dataclass(self):
        for cls in (ThingId, Colour, Painted):
            self.assertTrue(dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen, cls)  # type: ignore[attr-defined]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            Painted(ThingId("t"), Colour("red")).colour = Colour("blue")  # type: ignore[misc]
        with self.assertRaises(ValueError):
            Colour("red!")
        for marker in (bb.Value, bb.Id, bb.DomainEvent):
            self.assertFalse(dataclasses.is_dataclass(marker), marker)

    def test_a_decorator_of_its_own_fails_at_definition(self):
        with self.assertRaises(TypeError):
            @dataclasses.dataclass(frozen=True)
            class Twice(bb.Value):
                value: str

    def test_an_entity_is_its_identity(self):
        one, same = Thing(ThingId("t"), Colour("red")), Thing(ThingId("t"), Colour("blue"))
        self.assertTrue(one.same_identity_as(same))
        self.assertFalse(one.same_identity_as(Thing(ThingId("u"), Colour("red"))))
        self.assertFalse(one.same_identity_as(None))

    def test_an_aggregate_collects_its_events_until_cleared(self):
        thing = Thing(ThingId("t"), Colour("red"))
        thing.paint(Colour("blue"))
        self.assertEqual((Painted(ThingId("t"), Colour("blue")),), thing.domain_events())
        thing.clear_domain_events()
        self.assertEqual((), thing.domain_events())
        with self.assertRaises(ValueError):
            thing.register_event(None)  # type: ignore[arg-type]

    def test_a_repository_is_a_port_any_class_can_carry(self):
        things: Things = InMemoryThings()
        saved = things.save(Thing(ThingId("t"), Colour("red")))
        self.assertIs(saved, things.find_by_id(ThingId("t")))
        things.delete_by_id(ThingId("t"))
        self.assertIsNone(things.find_by_id(ThingId("t")))

    def test_the_failures_stay_apart(self):
        class Refused(bb.DomainException):
            pass

        class Missing(bb.UseCaseException):
            pass

        self.assertFalse(issubclass(Refused, bb.UseCaseException))
        self.assertFalse(issubclass(Missing, bb.DomainException))

    def test_every_marker_of_the_java_library_is_here(self):
        for name in ("Value", "Id", "Entity", "AggregateRoot", "DomainEvent", "DomainService", "DomainGateway",
                     "DomainException", "Repository", "Store", "InputPort", "OutputPort", "UseCase", "UseCaseException"):
            self.assertTrue(hasattr(bb, name), name)


if __name__ == "__main__":
    unittest.main()
