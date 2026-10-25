"""The figures and words every view writes the same way: a time, a duration, an age, tokens and cost, the order of
the backlog, the worker in a few words, the signals the bench rates."""

from __future__ import annotations

import datetime
import typing

#: How a story's named rules can end at its test gate (WP-148 B).
RULE_VERDICTS = ("red", "killed", "survived", "no-break", "unchecked")

#: A claim older than this many days is stale: it may be forgotten.
STALE_CLAIM_DAYS = 3

Entry = typing.Dict[str, typing.Any]


def parse_time(text: typing.Any) -> typing.Optional[datetime.datetime]:
    """A stamp as the project's files write it — ISO 8601, `Z` for UTC — as a time; None for none or a broken one."""
    text = str(text or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=datetime.timezone.utc)


def stamp_text(value: typing.Any) -> str:
    """`2026-09-25 14:31` in UTC, or `—`."""
    moment = parse_time(value) if isinstance(value, str) else value
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M") if moment else "—"


def took_text(seconds: typing.Optional[float]) -> str:
    if not seconds:
        return "—"
    whole = int(round(seconds))
    if whole < 60:
        return f"{whole} s"
    minutes = whole // 60
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def figures(entry: Entry) -> Entry:
    """An entry's figures as every view writes them — tokens, time worked, cost, when it was delivered (a story's;
    an epic's `delivered` is a count) — beside the numbers."""
    tokens, delivered = entry.get("tokens") or 0, entry.get("delivered")
    return dict(tokens_text=f"{tokens:,}" if tokens else "",
                seconds_text=took_text(entry.get("seconds")) if entry.get("seconds") else "",
                cost_text=f"${entry['cost']:.2f}" if entry.get("priced") and entry.get("cost") else "",
                delivered_text=stamp_text(delivered) if delivered and not isinstance(delivered, int) else "")


def signals_line(totals: Entry) -> str:
    """The figures in one line — `kill rate 0.04 · guarded 1.00 · domain findings 2 concept · 1 term · corrections
    1 term` —, '' where nothing was measured or found."""
    parts = []
    if totals.get("named"):
        parts.append(f"kill rate {totals['kill_rate']:.2f} · guarded {totals['guarded_rate']:.2f} "
                     f"({totals['named']} rules named)")
    elif totals.get("measured") is not None and totals.get("stories") and not totals.get("measured"):
        parts.append("rules not measured")
    if totals.get("domain"):
        parts.append("domain findings " + " · ".join(f"{n} {c.replace('domain-', '', 1)}"
                                                     for c, n in sorted(totals["domain"].items())))
    if totals.get("corrections"):
        parts.append("corrections " + " · ".join(f"{n} {c.replace('domain-', '', 1)}"
                                                 for c, n in sorted(totals["corrections"].items())))
    return " · ".join(parts)


def signal_totals(rows: typing.Sequence[Entry]) -> Entry:
    """The signals of several stories summed (WP-150 E) — the figures the bench rates: the rules named and each
    verdict, the kill rate (killed / named) and the guarded rate ((red + killed) / named) — None where no rule was
    named —, questions, assumptions, what plans left open, the judges' findings by perspective and domain code, the
    corrections by code. A story whose gate recorded no rules (one built before 0.88.0) is counted as not measured,
    never as zero."""
    total: Entry = dict(stories=len(rows), measured=0, not_measured=0, named=0, **{v: 0 for v in RULE_VERDICTS},
                        asked=0, answered=0, assumptions_open=0, assumptions_answered=0, plan_open=0,
                        findings={}, domain={}, corrections={})
    for row in rows:
        signals = row.get("signals") or {}
        if signals.get("rules") is None:
            total["not_measured"] += 1
        else:
            total["measured"] += 1
            for verdict, n in signals["rules"].items():
                total[verdict] = total.get(verdict, 0) + n
                total["named"] += n
        for key in ("asked", "answered", "assumptions_open", "assumptions_answered", "plan_open"):
            total[key] += signals.get(key) or 0
        for key in ("findings", "domain", "corrections"):
            for name, n in (signals.get(key) or {}).items():
                total[key][name] = total[key].get(name, 0) + n
    named = total["named"]
    total["kill_rate"] = round(total["killed"] / named, 2) if named else None
    total["guarded_rate"] = round((total["red"] + total["killed"]) / named, 2) if named else None
    total["line"] = signals_line(total)
    return total


def created_moment(value: typing.Any) -> typing.Optional[datetime.datetime]:
    """A `created:` (or `delivered:`) value as a UTC time to order by — a date alone at its midnight; None for none."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        moment = datetime.datetime.fromisoformat(text.replace("Z", "+00:00") if "T" in text
                                                 else text + "T00:00:00+00:00")
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


ITEM = typing.TypeVar("ITEM", bound=Entry)


def newest_first(items: typing.Sequence[ITEM], key: str = "created") -> typing.List[ITEM]:
    """The items newest first by their `key` (a `created:` or a delivery time); the undated after them. Stable: the
    order the items come in decides a tie and among the undated."""
    def moment(item: Entry) -> typing.Optional[datetime.datetime]:
        value = item.get(key)
        return value if isinstance(value, datetime.datetime) else created_moment(value)

    def utc(item: Entry) -> datetime.datetime:
        found = moment(item)
        assert found is not None
        return found.astimezone(datetime.timezone.utc)
    dated = sorted((i for i in items if moment(i)), key=utc, reverse=True)
    # sorted(reverse=True) keeps equal items in their order, so a tie stays in the schedule's
    return dated + [i for i in items if not moment(i)]


def claim_age(since: typing.Optional[str], now: datetime.datetime) -> typing.Tuple[str, bool]:
    """`3 h`, `6 d`, and whether it is stale — from the claim's UTC stamp; the stamp itself where it is unreadable."""
    try:
        began = datetime.datetime.strptime(str(since), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return since or "?", False
    hours = max(0, int((now - began).total_seconds() // 3600))
    return (f"{hours} h" if hours < 48 else f"{hours // 24} d"), hours >= STALE_CLAIM_DAYS * 24


def worker_text(info: typing.Optional[Entry]) -> str:
    """The worker in a few words, as a view's header shows it."""
    if not info:
        return "down"
    if not info["alive"]:
        return f"{info['how']} — no sign of life"
    if info["stopping"]:
        return "stopping after its stage"
    return str({"up": "up", "runner": "up — a runner from a terminal", "session": "up — a session's run"}[info["how"]])
