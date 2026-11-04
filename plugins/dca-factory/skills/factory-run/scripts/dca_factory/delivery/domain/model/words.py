"""What a person typed (WP-184): a request's words — what they may carry, so what is read is what was shown."""

from __future__ import annotations

import re

from ....building_blocks import Value

#: A control character other than a line break, a return and a tab (NUL among them) — never in a person's text.
CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
#: The direction marks that show a text in another order than it is read: bidi overrides and isolates.
DIRECTION = re.compile("[\u202a-\u202e\u2066-\u2069]")
#: The most characters a request's words take.
MAX_LENGTH = 20000


class WordsRefused(ValueError):
    """Words a person may not hand the factory: too long, or carrying what is not read as it is shown."""


class Words(Value):
    """A person's words as a request carries them: at most `MAX_LENGTH` characters, no control character but a line
    break, a return and a tab, no direction mark."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > MAX_LENGTH:
            raise WordsRefused("the words are too long")
        if CONTROL.search(self.value) or DIRECTION.search(self.value):
            raise WordsRefused("the words carry a control character or a direction mark — a line break and a tab are "
                               "all a person types")
