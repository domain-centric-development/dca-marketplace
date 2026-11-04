"""Canned views for `factory.sh serve --fixture <name>` (WP-180): the real page against views that hold every state.

`all-states` holds each state a story, a wish, a request and a record can be in — draft, released, running, waiting for
an answer, waiting for acceptance, stopped, delivered, superseded, a failed request, a wish in each of its states —;
`empty` is a fresh project. The page reads them as it reads the factory's own views, so what it shows is drawn by the
code that runs; a person checks a theme against them, and the pattern library (`#components`) shows the components
beside. The words are a small lending library's, no project's. The rulebook and the parts of the cycle (`rules`,
`help`) are the factory's own and not canned: they do not depend on a project's state.
"""

import copy

#: The views a fixture answers from the factory itself.
LIVE_VIEWS = ("help", "rules")


def _action(label, kind, primary=False, creates=False, text="", open_=None, draft=None, choices=None, note=None, **fields):
    request = dict(kind=kind, fields=fields)
    if open_:
        request["open"] = open_
    if draft:
        request["draft"] = draft
    if choices:
        request["choices"] = choices
    action = dict(label=label, primary=primary, creates=creates, text=text, request=request, skill=f"/factory {kind}")
    if note:
        action["note"] = note
    return action


def _row(story, title, epic, state, lane, mark="none", stage="—", delivered="", tokens="", cost="", seconds="", actions=()):
    return dict(story=story, title=title, epic=epic, state=state, lane=lane, mark=mark, stage=stage, delivered_text=delivered,
                tokens_text=tokens, cost_text=cost, seconds_text=seconds, actions=list(actions))


COURSE = [dict(stage="plan", state="done"), dict(stage="test", state="done"), dict(stage="build", state="now"),
          dict(stage="tidy", state=""), dict(stage="judge", state=""), dict(stage="document", state="")]
STOPPED_COURSE = [dict(stage="plan", state="done"), dict(stage="test", state="stopped"), dict(stage="build", state=""),
                  dict(stage="tidy", state=""), dict(stage="judge", state=""), dict(stage="document", state="")]

ROWS = [
    _row("a-reader-borrows-a-book", "A reader borrows a book", "lending", "delivered", "delivered", "done",
         delivered="2026-10-30T10:12:00Z", tokens="4.1 M", cost="$3.10", seconds="14 min"),
    _row("a-loan-has-a-due-date", "A loan has a due date", "lending", "delivered", "delivered", "done",
         delivered="2026-10-31T09:40:00Z", tokens="3.2 M", cost="$2.40", seconds="11 min"),
    _row("a-reader-returns-a-book", "A reader returns a book", "lending", "running", "running", "running", stage="build",
         tokens="2.0 M"),
    _row("a-late-return-is-fined", "A late return is fined", "lending", "waiting for your answer", "running", "question",
         stage="plan"),
    _row("a-reader-renews-a-loan", "A reader renews a loan", "lending", "ready", "approved",
         actions=[_action("run it", "run", primary=True, story="a-reader-renews-a-loan")]),
    _row("the-loan-list-is-paged", "The loan list is paged", "lending", "superseded", "superseded"),
    _row("a-reader-reserves-a-copy", "A reader reserves a copy", "reservations", "draft", "draft", "look",
         actions=[_action("release", "release", primary=True, story="a-reader-reserves-a-copy"),
                  _action("change this", "change", open_="words", text="what should change", draft="change:reserve",
                          story="a-reader-reserves-a-copy")]),
    _row("a-reservation-expires", "A reservation expires", "reservations", "stopped", "running", "stopped", stage="test"),
    _row("the-desk-sees-the-queue", "The desk sees the queue", "reservations", "waiting for your acceptance", "delivered",
         "look", delivered="2026-11-01T15:02:00Z", tokens="5.6 M", cost="$4.20", seconds="19 min"),
]

SIGNALS = dict(stories=6, answered=3, asked=4, assumptions_answered=5, assumptions_open=1, plan_open=2,
               domain={"domain-model": 2, "domain-language": 1}, corrections={"domain-model": 1},
               findings={"ddd": 4, "hexagonal": 2, "clean-code": 1}, killed=9, red=11, survived=1, **{"no-break": 1},
               named=12, measured=5, not_measured=1, without_test=0, open=3)

WISH_ENTRY = _action("wish", "wish", primary=True, creates=True, open_="words", text="What should exist? Your words.",
                     draft="wish")


def _status_all():
    lending = [r for r in ROWS if r["epic"] == "lending"]
    reservations = [r for r in ROWS if r["epic"] == "reservations"]
    stopped = dict(story="a-reservation-expires", mark="stopped", what="the tests did not turn red", place="decide",
                   course=STOPPED_COURSE, action=_action("run it again", "run", primary=True, text="the gate refused the test stage",
                                                         story="a-reservation-expires"))
    return dict(
        project="lending-library",
        worker=dict(alive=True, how="up", backlog=True, stopping=False, owner="Ann on desk-1", since_text="09:02",
                    log=".dca-factory/worker.log"),
        worker_text="the backlog is on", ended=None,
        rows=ROWS,
        now=[dict(column="backlog", count=1, line="released — 2 more blocked", title="A reader renews a loan",
                  story="a-reader-renews-a-loan", action=_action("run it", "run", primary=True)),
             dict(column="run", count=1, line="of 2 places", title="A reader returns a book", story="a-reader-returns-a-book",
                  sub="build · round 2", action=dict(label="■ stop the backlog", call="down")),
             dict(column="decide", count=3, line="waits for you", title="A late return is fined",
                  story="a-late-return-is-fined", hot=True, action=dict(label="answer", request=dict(kind="answer", open="record"))),
             dict(column="delivered", count=3, total=9, percent=33, line="33 %", last_text="2026-11-01T15:02:00Z")],
        waiting=[dict(story="a-late-return-is-fined", mark="question", what="a question", record="q-1", place="decide"),
                 dict(story="the-desk-sees-the-queue", mark="look", what="a result to look at", record="a-1", place="decide"),
                 dict(story="a-reader-reserves-a-copy", mark="look", what="a draft waits for your release", place="decide",
                      action=_action("release", "release", primary=True, story="a-reader-reserves-a-copy")),
                 stopped],
        running=[dict(story="a-reader-returns-a-book", stage="build", part="build", round=2, course=COURSE,
                      activity="writing the return's adapter", ago="3 min")],
        queue=dict(ready=["a-reader-renews-a-loan"], blocked=2),
        delivered_order=["the-desk-sees-the-queue", "a-loan-has-a-due-date", "a-reader-borrows-a-book"],
        delivered=3, total=9, cost_text="$9.70", seconds_text="44 min", tokens_text="12.9 M",
        findings=[dict(severity="minor", plain="The loan's due date is a bare string", row="F-1", where="lending/Loan",
                       action=_action("to the backlog", "finding", creates=True, row="F-1"))],
        entries=dict(wish=WISH_ENTRY,
                     describe=_action("change it", "describe", primary=True, creates=True, open_="words",
                                      text="<part>: <change>", draft="describe"),
                     discover=_action("discover", "discover", primary=True, creates=True, open_="words",
                                      text="a problem worth solving", draft="discover")),
        description=[dict(part="product", path="product/overview.md", mark="done", present=True,
                          sections=["what", "for whom", "surfaces"], missing=[], empty=[]),
                     dict(part="tech", path="product/tech.md", mark="look", present=True, sections=["stack", "runtime"],
                          missing=["integrations"], empty=["version policy"]),
                     dict(part="domain", path="product/domain.md", mark="none", present=False, sections=[], missing=[], empty=[])],
        epics=[dict(epic="lending", title="Lending", metric="BookLent", goal="A reader leaves with the book they came for.",
                    rows=lending, total=len(lending), delivered=2, signals=SIGNALS,
                    actions=[_action("add guard", "guard", creates=True, epic="lending")]),
               dict(epic="reservations", title="Reservations", metric="CopyReserved", goal="", rows=reservations,
                    total=len(reservations), delivered=1, signals=None, actions=[])],
        journeys=[dict(epic="lending", text="lending is unguarded — no journey test yet")],
        delivered_curve=[dict(at="2026-10-30T10:12:00Z", story="a-reader-borrows-a-book", title="A reader borrows a book",
                              cost_total=3.1, tokens_total=4.1e6, cost=3.1, tokens=4.1e6, priced_total=1),
                         dict(at="2026-10-31T09:40:00Z", story="a-loan-has-a-due-date", title="A loan has a due date",
                              cost_total=5.5, tokens_total=7.3e6, cost=2.4, tokens=3.2e6, priced_total=2),
                         dict(at="2026-11-01T15:02:00Z", story="the-desk-sees-the-queue", title="The desk sees the queue",
                              cost_total=9.7, tokens_total=12.9e6, cost=4.2, tokens=5.6e6, priced_total=3)],
        signals=SIGNALS,
    )


def _requests_all():
    take_back = [dict(name="drop", label="take back")]
    return dict(
        requests=[dict(id="r-1", kind="release", target="a-reader-renews-a-loan", state="queued", by="Ann", operations=take_back),
                  dict(id="r-2", kind="wish", target="", state="running", by="Ben", operations=[]),
                  dict(id="r-3", kind="discover", target="empty-shelves", state="waiting", by="Ann", record="q-2", operations=[]),
                  dict(id="r-4", kind="guard", target="lending", state="failed", by="Ann", error="the agent ended without a test",
                       operations=[dict(name="retry", label="retry"), dict(name="drop", label="drop")])],
        wishes=[dict(id="w-1", words="readers may reserve a copy", state="running", tone="wait", text="writing",
                     started="2026-11-03T09:00:00Z", by="Ben", operations=[dict(name="drop", label="take back")]),
                dict(id="w-2", words="a reminder before the due date", state="waiting", tone="ask", text="asks back",
                     place="decide", by="Ann", operations=[]),
                dict(id="w-3", words="the desk sees who waits", state="done", tone="ok",
                     text="became the draft story the-desk-sees-the-queue", by="Ann",
                     made=[dict(kind="story", id="the-desk-sees-the-queue", title="The desk sees the queue")],
                     actions=[_action("release", "release", primary=True, story="the-desk-sees-the-queue")],
                     operations=[dict(name="hide", label="✕")]),
                dict(id="w-4", words="fines in another currency", state="failed", tone="bad", text="failed", by="Ben",
                     operations=[dict(name="retry", label="retry"), dict(name="drop", label="drop")])],
        counts=dict(failed=1), counts_text="4 requests")


def _decisions_all():
    return dict(records=[
        dict(id="q-1", kind="question", story="a-late-return-is-fined", stage="plan", path="product/epics/lending/q-1.md",
             place="decide", text="Is a fine charged **per day** or once per late return?",
             sections=[dict(heading="Why it asks", text="The story says *fined*, the glossary knows no `Fine` yet.")],
             actions=[_action("a", "answer", primary=True, text="per day, from the first day late", note="the desk's practice", option="a"),
                      _action("b", "answer", text="once per late return", option="b"),
                      _action("answer", "answer", open_="words", text="in your words", draft="answer:q-1",
                              choices=["neither", "it depends"])]),
        dict(id="a-1", kind="acceptance", story="the-desk-sees-the-queue", stage="document", place="decide",
             path="product/epics/reservations/a-1.md", text="Look at the desk's queue page.",
             sections=[dict(heading="What to look at", text="- the queue, oldest first\n- a reservation that expired")],
             actions=[_action("accept", "accept", primary=True), _action("correct it", "correct", open_="words",
                                                                         text="what is wrong", draft="correct:a-1")]),
        dict(id="q-2", kind="question", place="discover", path=".dca-factory/discovery/empty-shelves/q-2.md",
             text="Which readers find the shelves empty?", sections=[],
             actions=[_action("answer", "answer", open_="words", text="in your words", draft="answer:q-2")])])


def _discover_all():
    return dict(store="product/discovery", working=[dict(id="r-3", topic="empty-shelves", state="waiting", words="readers find no copy", record=".dca-factory/discovery/empty-shelves/q-2.md")],
                topics=[dict(topic="empty-shelves", title="Readers find the shelves empty", report="product/discovery/empty-shelves.md",
                             sections=[dict(heading="The problem", text="A reader comes for a book and finds **no copy**.")],
                             proposals=[dict(id="p-1", goal="Readers find a free copy", intent="fewer empty shelves",
                                             metric="CopyFound", domain_contact="the desk", epic=None,
                                             actions=[_action("make it an epic", "epic", creates=True, proposal="p-1")]),
                                        dict(id="p-2", goal="Readers reserve a copy", metric="CopyReserved", epic="reservations")],
                             description_changes=[dict(target="product", change="a reservation is a surface", why="the report's second finding",
                                                       actions=[_action("apply", "describe", primary=True)])],
                             actions=[_action("continue", "discover", open_="words", text="a question, a document, a wish",
                                              draft="discover:empty-shelves")])])


def _spec_all():
    criterion = dict(key="a-reader-borrows-a-free-copy", form="scenario", tests=["LendingTest.borrows"],
                     lines=["- a-reader-borrows-a-free-copy:", "- Given a free copy", "- When a reader borrows it", "- Then it is lent to them"],
                     changed_by=[], health=dict(proof="tested", missing=[], delivered_by=dict(story="a-reader-borrows-a-book")))
    changed = dict(key="a-loan-is-due-in-three-weeks", form="line", tests=[], lines=["- a-loan-is-due-in-three-weeks: a loan is due in three weeks"],
                   changed_by=[dict(verdict="changes", story="a-reader-renews-a-loan", title="A reader renews a loan", status="ready")],
                   health=dict(proof="untested", missing=[], delivered_by=None))
    return dict(shared_kernel=dict(model=[dict(kind="value object", terms=[dict(name="Money", shared=True, meaning="an amount in a currency", used_by=["lending"])])]),
                contexts=[dict(context="lending", subdomain="Core", purpose="who has which book until when", criteria=2,
                               model=[dict(kind="aggregate", terms=[dict(name="Loan", meaning="a book lent to a reader")]),
                                      dict(kind="value object", terms=[dict(name="Due date"), dict(name="Money", shared=True)]),
                                      dict(kind="concept", terms=[dict(name="Shelf")])],
                               features=[dict(feature="borrowing", rules=[dict(rule="A reader holds three loans at most.", criteria=[criterion, changed])],
                                              add=_action("add a criterion", "describe", open_="words", text="the criterion", draft="add:borrowing"))],
                               coming=[dict(status="ready", story="a-reader-renews-a-loan", keys=[dict(key="a-loan-renews-once")])],
                               health=dict(orphaned=0, untested=1, undelivered=1),
                               add=_action("add a feature", "describe", open_="words", text="the feature", draft="add:lending")),
                          dict(context="catalogue", subdomain="Supporting", purpose="which books the library has", criteria=0,
                               model=[], features=[], coming=[], health=None, add=None)])


def _story_all():
    return dict(epic="lending", title="A reader returns a book", row=ROWS[2], context="lending",
                path="product/epics/lending/a-reader-returns-a-book/story.md",
                actions=[_action("change this", "change", open_="words", text="what should change", draft="change:return")],
                sections=[dict(heading="Intent", text="A reader brings a book back and **owes nothing** more."),
                          dict(heading="Why it is not built yet", kind="blocked", text="It waits for `a-loan-has-a-due-date`.")],
                criteria_at=1,
                scenarios=[dict(key="a-returned-book-is-free", title="A returned book is free again", rule="A copy is lent or free.",
                                steps=[dict(word="Given", text="a lent copy"), dict(word="When", text="the reader returns it"),
                                       dict(word="Then", text="the copy is free")])],
                stages=dict(plan=dict(runs=1, seconds_text="3 min", tokens_text="0.8 M", cost_text="$0.60", why=""),
                            test=dict(runs=1, seconds_text="4 min", tokens_text="1.2 M", cost_text="$0.90", why=""),
                            build=dict(runs=2, seconds_text="6 min", tokens_text="2.0 M", cost_text="$1.50", why="the gate refused once")))


def _part_all():
    # seven sections, some long — a part is read as a document beside its sections (WP-183)
    long = ("The desk lends books to readers and takes them back. A reader holds three loans at most; a loan runs three "
            "weeks and renews once. What the desk sees first is what waits: a return to book in, a reservation to hand "
            "out, a fine to settle. ")
    return dict(path="product/overview.md", sections=[
        dict(heading="What and for whom", text=long * 2 + "\n\n- the desk\n- the readers"),
        dict(heading="Surfaces", text="- the desk's screen, in the library\n- a reader's page, on a phone"),
        dict(heading="How it works", text=long * 3),
        dict(heading="Look and feel", text="Quiet, legible at arm's length; the desk's actions one press away."),
        dict(heading="Qualities", text="- a return books in within a second\n- nothing is lost when the network drops"),
        dict(heading="Not part of the product", text="Buying books, a catalogue search across libraries."),
        dict(heading="Open questions", text=long)])


def _empty():
    return dict(
        status=dict(project="a-new-project", worker=None, worker_text="nobody holds the checkout", ended=None, rows=[],
                    now=[dict(column="backlog", count=0, line="nothing released"), dict(column="run", count=0, line="of 1 place"),
                         dict(column="decide", count=0, line="nothing waits"), dict(column="delivered", count=0, total=0, percent=0, line="0 %")],
                    waiting=[], running=[], queue=dict(ready=[], blocked=0), delivered_order=[], delivered=0, total=0,
                    findings=[], entries=dict(wish=WISH_ENTRY), description=[], epics=[], journeys=[], delivered_curve=[], signals=None),
        requests=dict(requests=[], wishes=[], counts={}, counts_text=""),
        decisions=dict(records=[]),
        discover=dict(topics=[], working=[], store="product/discovery"),
        spec=dict(contexts=[], shared_kernel=None),
        story=dict(epic="", title="", row={}, path="", actions=[], sections=[], scenarios=[], stages={}),
        part=dict(path="product/overview.md", sections=[]))


FIXTURES = {
    "all-states": dict(status=_status_all(), requests=_requests_all(), decisions=_decisions_all(), discover=_discover_all(),
                       spec=_spec_all(), story=_story_all(), epic={}, part=_part_all(), output={}, **{"spec-delta": {}}),
    "empty": _empty(),
}


def view(fixture, name):
    """The canned view, a copy — or None where the fixture has none."""
    views = FIXTURES.get(fixture) or {}
    return copy.deepcopy(views[name]) if name in views else None
