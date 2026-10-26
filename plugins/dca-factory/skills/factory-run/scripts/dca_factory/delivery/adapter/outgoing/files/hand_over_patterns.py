"""The lines a hand-over and a story are read by: a criterion, the happy path's mark, a row of the tests table, a
test's selector."""

import re

from ....domain.model.stage_story import SELECTOR_FORM


CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*:\s*(\S.*)$")


#: The one scenario per story that shows its value, marked where the story is written: `#### <key> (happy path)`
#: or `- <key> (happy path): <criterion>`. It gets the end-to-end test; the others are integrated.
HAPPY_MARK = re.compile(r"^(?:####\s+|-\s+)([a-z0-9][a-z0-9-]*)\s*\(happy path\)\s*(?::.*)?$")


MAPPING_ROW = re.compile(r"^\|\s*([a-z0-9][a-z0-9-]*)\s*\|\s*([^|]+?)\s*\|")


SELECTOR = SELECTOR_FORM
