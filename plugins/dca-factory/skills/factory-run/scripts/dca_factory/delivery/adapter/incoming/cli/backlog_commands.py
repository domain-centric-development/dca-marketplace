"""The backlog feature's commands of the cli."""

from __future__ import annotations

from ....application.backlog.backfill_created import BackfillCreatedCommand
from . import root


def backfill_created(cwd: str, epics: str) -> int:
    """WP-146: `created:` into every story and every epic that has none (`BackfillCreatedUseCase`). Prints what it
    wrote."""
    done = root.wiring.backfill_created(cwd, epics).execute(BackfillCreatedCommand())
    if not done.stories and not done.epics:
        print("backfill: every story and epic has its created: — nothing written")
        return 0
    print(f"backfill: created: written into {done.stories} stor{'y' if done.stories == 1 else 'ies'} and "
          f"{done.epics} epic{'' if done.epics == 1 else 's'}, from the commit that added each"
          + (f" — {done.from_file} not in git yet, from the file's own time" if done.from_file else ""))
    return 0
