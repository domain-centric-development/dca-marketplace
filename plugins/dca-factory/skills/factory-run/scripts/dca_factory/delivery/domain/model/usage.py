"""What a process used: tokens on a model, and what they cost where they were priced."""

from __future__ import annotations

import typing

from ....building_blocks import Value

#: The token counts a usage carries, in the order the journal writes them.
USAGE_FIELDS = ("input", "cache_read", "cache_write", "output")


class TokenCount(Value):
    """A number of tokens, never negative."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"{self.value} tokens")


class ModelName(Value):
    """The model a process ran on, as its tool reports it — `unknown` where it did not."""

    value: str


class Cost(Value):
    """What tokens cost, in dollars, as priced by the price table."""

    value: float


class Shares(Value):
    """In how many even parts a usage is booked — at least one."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError(f"{self.value} shares")


class Tokens(Value):
    """Tokens read, read from the cache, written to the cache, and written."""

    input: TokenCount
    cache_read: TokenCount
    cache_write: TokenCount
    output: TokenCount


class Usage(Value):
    """What one process used: its tokens on a model, and their cost where it was priced."""

    model: ModelName
    tokens: Tokens
    cost: typing.Optional[Cost] = None

    def share(self, shares: Shares) -> Usage:
        """One of <shares> even parts — tokens rounded down, the cost divided exactly."""
        def part(count: TokenCount) -> TokenCount:
            return TokenCount(count.value // shares.value)
        tokens = Tokens(part(self.tokens.input), part(self.tokens.cache_read), part(self.tokens.cache_write),
                        part(self.tokens.output))
        cost = Cost(self.cost.value / shares.value) if self.cost is not None else None
        return Usage(self.model, tokens, cost)
