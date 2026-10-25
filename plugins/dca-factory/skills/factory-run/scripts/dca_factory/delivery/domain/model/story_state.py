"""Where a story stands in the schedule."""

from __future__ import annotations

#: The schedule's states of a story that can run now: not started, begun, or stopped where it can continue.
RUNNABLE = ("ready", "in-progress", "resumable")
