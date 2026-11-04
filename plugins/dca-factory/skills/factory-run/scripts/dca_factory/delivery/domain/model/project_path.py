"""A path in the project (WP-184) — what a shown file, a handed file and a story's picture are named by."""

from __future__ import annotations

from ....building_blocks import Value


class ProjectPath(Value):
    """A path in the project, with `/` between its folders."""

    value: str
