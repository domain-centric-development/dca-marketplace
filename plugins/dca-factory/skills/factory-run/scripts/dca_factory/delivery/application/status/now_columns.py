"""Where it stands: the cycle as four columns — backlog, run, decide, delivered —, each its count, one line under it,
the one item that matters most there and the one action at its foot, as the start page draws them (WP-179). Which
item a column names is the factory's order; a view picks nothing."""

from __future__ import annotations

import typing

from .texts import stamp_text

Model = typing.Dict[str, typing.Any]


def places_of(profile: typing.Mapping[str, str]) -> int:
    """How many stories run at once by the profile's `parallel:`, 1 where it names none or no number."""
    words = str(profile.get("parallel") or "").split()
    return int(words[0]) if words and words[0].isdigit() and int(words[0]) > 0 else 1


def now_columns(rows: typing.List[Model], queue: Model, next_story: str, next_line: Model, running: typing.List[Model],
                waiting: typing.List[Model], journeys: typing.List[Model], backlog_on: bool, places: int,
                delivered_order: typing.List[str]) -> typing.List[Model]:
    """The four columns in the cycle's order: `column`, `count`, `line`, `title`, `sub`, `action` (a view draws it as
    the column's foot; None where there is nothing to press), `hot` (something waits for the person there)."""
    titles = {r["story"]: r["title"] or r["story"] for r in rows}
    ready, blocked = len(queue.get("ready", [])), int(queue.get("blocked") or 0)
    first = next_story or ""
    backlog = dict(column="backlog", count=ready, line="released" + (f" — {blocked} more blocked" if blocked else ""),
                   title=titles.get(first, "") if first else next_line["text"], sub="next" if first else "", story=first,
                   action=next_line.get("action") if next_line.get("action", {}).get("request") else None, hot=False)
    run_now = running[0] if running else None
    run = dict(column="run", count=len(running), line=f"of {places} place" + ("s" if places != 1 else ""),
               title=titles.get(run_now["story"], run_now["story"]) if run_now else "Nothing runs.",
               sub=(f"{run_now.get('part') or run_now['stage']}" + (f" · and {len(running) - 1} more"
                                                                    if len(running) > 1 else ""))
               if run_now else ("the backlog runs" if backlog_on else "the backlog is off"),
               action=None if run_now or backlog_on else dict(call="up", label="▶ start the backlog"), hot=False,
               story=run_now["story"] if run_now else "")
    asks = [w for w in waiting if (w.get("place") or "decide") == "decide"]
    ask = asks[0] if asks else None
    decide = dict(column="decide", count=len(asks), line="waits for you" if asks else "nothing waits",
                  title=titles.get(ask["story"], ask["story"]) if ask else "", sub=ask["what"] if ask else "",
                  action=ask["action"] if ask and ask["action"].get("request") else None, hot=bool(asks),
                  story=ask["story"] if ask else "")
    done, total = sum(r["done"] for r in rows), len(rows)
    last = next((r for r in rows if delivered_order and r["story"] == delivered_order[0]), None)
    guard = journeys[0] if journeys else None
    delivered = dict(column="delivered", count=done, total=total, percent=round(100 * done / total) if total else 0,
                     line="", last=(last or {}).get("delivered") or "",
                     last_text=stamp_text((last or {}).get("delivered")) if (last or {}).get("delivered") else "",
                     title=f"{guard['epic']} is unguarded" if guard else "",
                     sub=(f"{len(journeys) - 1} more epic" + ("s" if len(journeys) != 2 else "") + " without a journey test")
                     if len(journeys) > 1 else ("no journey test yet" if guard else ""),
                     action=guard["action"] if guard else None, hot=False)
    delivered["line"] = f"{delivered['percent']} %"
    return [backlog, run, decide, delivered]
