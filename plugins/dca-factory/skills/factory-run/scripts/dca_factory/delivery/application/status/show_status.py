"""Show where the factory stands: what waits for a person, what runs, the backlog by epic, what comes next."""

from __future__ import annotations

import dataclasses
import re
import typing

from ....building_blocks import UseCase
from ...domain.model.story_state import RUNNABLE
from ...domain.model.usage import USAGE_FIELDS
from ..requests.list_requests import ListRequestsQuery, ListRequestsUseCase
from ..requests.pending import mark_pending
from ..shared.requests import PENDING, RequestStore
from ..description.parts import parts_as_they_stand
from ..shared.description_store import DescriptionStore
from ..shared.status_facts import StatusFacts
from .actions import Action, entry_actions, make_action, offered, RUNNER
from .texts import claim_age, figures, newest_first, parse_time, signal_totals, stamp_text, took_text, worker_text
from ...domain.model.decision_record import WAITING_WORDS
from ...domain.model.story_state import ENDED_WORDS

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowStatusQuery:
    """`live`: with what only a look now can say — the worker, the activity inside a running stage, how long ago."""

    live: bool = False


class ShowStatusInputPort(UseCase[ShowStatusQuery, Model], typing.Protocol):
    """Where the factory stands."""


class ShowStatusUseCase:
    """The status every view draws — the terminal, the page, the cockpit, a session's start: the order, the marks,
    the words, the figures and every action are decided here, a view composes none of its own."""

    def __init__(self, facts: StatusFacts, requests: RequestStore, description: DescriptionStore) -> None:
        self._facts = facts
        self._requests = requests
        self._description = description

    def execute(self, query: ShowStatusQuery) -> Model:
        facts, live = self._facts, query.live
        profile = facts.profile()
        data = facts.schedule()
        stories, order = data["stories"], data["order"]
        now = facts.now()
        running_stages = facts.running_stages()
        rows: typing.List[Model] = []
        waiting: typing.List[Model] = []
        attention: typing.Dict[str, Action] = {}
        for story_id in order:
            story = stories[story_id]
            told = facts.story_facts(story_id, story.get("front"))
            mark, words, action = self._attention(story_id, story, profile)
            attention[story_id] = action
            done = story["state"] == "delivered"
            stage = "" if done else next((st for sid, st, _t in running_stages if sid == story_id),
                                         story.get("start") or "")
            # the tests a gate of this story ran again alone and saw green: red in the whole suite, not the story's
            flaky = sorted(facts.flaky_tests(story_id))
            signals = facts.story_signals(story_id, facts.story_records(story_id, story.get("path")),
                                          story.get("body") or "")
            rows.append(dict(journal=facts.has_journal(story_id), done=done, epic=story.get("epic", ""), story=story_id,
                             flaky=flaky, signals=signals,
                             title=story.get("title", ""), mark=mark, created=created_of(story.get("front") or {}),
                             state=words, stage=stage or "—", passes=len(told["passes"]) or 0,
                             started=told["started"], delivered=told["delivered"], seconds=told["seconds"],
                             tokens=told["tokens"], measured=told["measured"], runs=told["runs"],
                             **{k: sum(e.get(k, 0) for e in told["stages"].values()) for k in USAGE_FIELDS},
                             cost=told["cost"], priced=told["priced"]))
            if mark in ("look", "question", "stopped"):
                waiting.append(dict(mark=mark, story=story_id, what=words, action=action,
                                    draft=story["state"] == "unreleased",
                                    record=self._open_record(story_id, story) if mark != "stopped" else ""))
        for name, front, _body, state, error, path in facts.decision_files():
            story_id = str(front.get("story", "")).strip() if not error else ""
            if story_id in stories:
                continue                                  # its story's row already says so
            if error or state in WAITING_WORDS:
                waiting.append(dict(mark="question", story=story_id or name, what="an open question",
                                    record=facts.shown(path), draft=False,
                                    action=self._action(skill="/factory-decisions",
                                                        shell=f"write the answer into {facts.shown(path)} under "
                                                              "`## Answer`",
                                                        label="answer", primary=True)))
        running: typing.List[Model] = []
        held = facts.claim() if live else None
        windows = facts.shared_windows()
        for story_id, stage, started in running_stages:
            if story_id in stories and stories[story_id]["state"] in ENDED_WORDS:
                continue
            interrupted = story_id in stories and stories[story_id]["state"] != "running"
            entry: Model = dict(story=story_id, stage=stage, since=parse_time(started), interrupted=interrupted,
                                round=facts.story_round(story_id))
            if stage in windows and not interrupted:
                entry["part"] = facts.window_part(story_id, stage)
            if live:
                since = parse_time(started)
                entry["ago"] = took_text((now - since).total_seconds()) + " ago" if since else ""
                entry["activity"] = facts.activity((held or {}).get("owner", ""), started, now,
                                                   story_id).split(": ", 1)[-1]
            running.append(entry)
        epics: typing.List[Model] = []
        for row in rows:
            if not epics or epics[-1]["epic"] != row["epic"]:
                found = next((e for e in epics if e["epic"] == row["epic"]), None)
                if found is None:
                    epics.append(dict(epic=row["epic"], rows=[]))
                else:
                    epics.append(epics.pop(epics.index(found)))
            epics[-1]["rows"].append(row)
        for epic in epics:
            epic["rows"].sort(key=lambda r: order.index(r["story"]))
            epic.update(delivered=sum(r["done"] for r in epic["rows"]), total=len(epic["rows"]),
                        tokens=sum(r["tokens"] for r in epic["rows"]),
                        measured=sum(r["measured"] for r in epic["rows"]),
                        seconds=sum(r["seconds"] for r in epic["rows"]), signals=signal_totals(epic["rows"]))
        epics.sort(key=lambda e: min(order.index(r["story"]) for r in e["rows"]))
        journeys = self._journey_hints(stories, epics)
        blank = dict(title="", goal="", metric="", discovery="", intent="", domain_contact="", created="", path="")
        files = facts.epic_files()
        for epic in epics:
            own = next((f for f in files if epic["epic"] in (f["epic"], f["folder"])), None)
            epic.update({k: (own or blank)[k] for k in blank})
        named = {e["epic"] for e in epics}
        # an epic whose folder holds no story yet: listed after the others, its next step is cutting them
        for own in files:
            if own["epic"] not in named and own["folder"] not in named:
                epics.append(dict(epic=own["epic"], rows=[], delivered=0, total=0, tokens=0, measured=0, seconds=0,
                                  signals=signal_totals([]),
                                  **{k: own[k] for k in blank}))
        empty = [e["epic"] for e in epics if not e["rows"]]
        # The backlog newest first (WP-146): the epics by `created:`, the stories within an epic by theirs — the
        # factory orders, every view shows the order as given. An item without the field comes after the dated ones,
        # in the schedule's order, as does every tie.
        for epic in epics:
            epic["rows"] = newest_first(epic["rows"])
        epics[:] = newest_first(epics)
        # what comes next, in the schedule's order: the stories that can run, and how many cannot yet
        queue: Model = dict(ready=[r["story"] for r in rows if stories[r["story"]]["state"] in RUNNABLE
                            and r["story"] not in {x["story"] for x in running}],
                     blocked=sum(1 for r in rows if stories[r["story"]]["state"] == "blocked"),
                     drafts=sum(1 for r in rows if stories[r["story"]]["state"] == "unreleased"))
        # what a person can do with each story and each epic — every view draws these, none composes its own
        for row in rows:
            story_id = row["story"]
            row["actions"] = offered(attention[story_id], self._action(
                text=f"run {story_id} now, before the schedule's next", skill=f"/factory-run {story_id}",
                shell=f"{RUNNER} run --story {story_id}", label="run now") if story_id in queue["ready"] else None)
            row.update(figures(row))
        guards = {hint["epic"]: hint for hint in journeys}
        # a story whose release is asked for already is no draft the epic's button still has to release
        every_request = self._requests.all()
        pending = [r for r in every_request if r["state"] in PENDING]
        asked = {r.get("story") for r in pending if r["kind"] == "release" and r.get("story")}
        for epic in epics:
            drafts = sum(1 for r in epic["rows"] if stories[r["story"]]["state"] == "unreleased")
            to_release = sum(1 for r in epic["rows"]
                             if stories[r["story"]]["state"] == "unreleased" and r["story"] not in asked)
            epic["actions"] = offered(
                self._action(text="the epic's next stories, written as drafts for you to release",
                             skill=f"/factory-backlog stories {epic['epic']}", label="suggest stories",
                             primary=not epic["total"]),
                self._action(text="every draft of the epic, released where its question pass leaves nothing open",
                             skill=f"/factory-backlog release {epic['epic']}",
                             label=f"release {to_release} draft" + ("s" if to_release > 1 else ""))
                if to_release else None,
                guards[epic["epic"]]["action"] if epic["epic"] in guards else None)
            epic.update(figures(epic), drafts=drafts)
        # the delivered stories, the newest delivery first; one without a time (delivered before the field) last
        delivered_order = [r["story"] for r in newest_first([r for r in rows if r["done"]], key="delivered")]
        next_line = self._next_line(data, stories, rows, empty, attention)
        extra = []
        requests = ListRequestsUseCase(self._requests).execute(ListRequestsQuery())["counts"]
        if any(requests.values()):
            extra.append("requests: " + ", ".join(f"{n} {state}" for state, n in requests.items() if n)
                         + " — `factory.sh requests`")
        worker = facts.worker() if live else None
        if worker:
            worker["since_text"] = stamp_text(worker.get("since")) + " UTC"
        # a factory that ended on its own says why, where a person looks — not only in its log
        gone = facts.ended() if live and not (worker or {}).get("alive") else None
        if gone:
            gone["text"] = f"the factory ended on its own: {gone['why']}"
            extra.append(f"{gone['text']} — its log: {gone['log']}")
        if live:
            if held:
                how = {"up": ", started by `factory.sh up`", "session": ", a session's run"}.get(
                    str((worker or {}).get("how")), "")
                extra.append(f"worker: {held.get('owner')} since {stamp_text(held.get('since'))} UTC{how}"
                             + (" — stopping after its stage" if (worker or {}).get("stopping") else ""))
            listening = facts.listener()
            extra.append(listening or "listening: no session has looked at the backlog")
            note = facts.duplicate_pipeline_note()
            if note:
                extra.append(note)
        # the project description as it stands — the foundation a person writes once and changes when things move
        description = parts_as_they_stand(self._description)
        for part in description:
            part["mark"] = "done" if part["present"] and not part["missing"] and not part["empty"] else "question"
        findings = self._findings()
        # the review perspectives the profile asks for now — a view shows a story's `review:<name>` processes for
        # these alone, never a reviewer a profile named before (an old `reviews/dca.md`, a `review:dca` in the journal)
        perspectives = [dict(name=name, carrier=carrier) for name, carrier in facts.perspectives(profile)]
        # an action whose request is written already says so instead of offering it twice
        mark_pending([a for row in rows for a in row["actions"]] + [a for epic in epics for a in epic["actions"]]
                     + [w["action"] for w in waiting] + [next_line["action"]] + [f["action"] for f in findings],
                     pending)
        totals = dict(tokens=sum(r["tokens"] for r in rows), measured=sum(r["measured"] for r in rows),
                      seconds=sum(r["seconds"] for r in rows), cost=sum(r["cost"] or 0 for r in rows),
                      priced=any(r["priced"] for r in rows))
        return dict(project=facts.project_name(), waiting=waiting, running=running, epics=epics,
                    worker=worker, ended=gone, requests=requests, findings=findings, claims=self._foreign_claims(),
                    holder=(facts.claim() or {}).get("owner"), listening=facts.listener(),
                    dangling=facts.dangling_skill_links(), findings_name=facts.findings_name(),
                    perspectives=perspectives, description=description, queue=queue, delivered_order=delivered_order,
                    rows=rows, next=next_line, journeys=journeys,
                    priced=any(r["priced"] for r in rows), extra=extra, hint=data["hint"],
                    delivered=sum(r["done"] for r in rows), total=len(rows),
                    tokens=totals["tokens"], measured=totals["measured"],
                    seconds=totals["seconds"], signals=signal_totals(rows),
                    entries=entry_actions(facts.names_story),
                    worker_text=worker_text(worker) if live else "",
                    **figures(totals))

    def _action(self, text: str = "", skill: str = "", shell: str = "", look: str = "", label: str = "",
                primary: bool = False) -> Action:
        return make_action(self._facts.names_story, text=text, skill=skill, shell=shell, look=look, label=label,
                           primary=primary)

    def _attention(self, story_id: str, story: Model,
                   profile: typing.Dict[str, str]) -> typing.Tuple[str, str, Action]:
        """(mark, state words, action) for one story — the words a person uses."""
        state, detail = story["state"], story.get("detail", "")
        records = self._facts.story_records(story_id, story.get("path"))
        open_records = [(path, front) for path, front, _body, st, _a in records if st in WAITING_WORDS]
        shown = self._facts.shown
        record = shown(open_records[0][0]) if open_records else ""
        by_hand = f"write the answer into {record} under `## Answer`" if record else ""
        if state == "waiting" and any(is_acceptance(f) for _p, f in open_records):
            record = next(shown(p) for p, f in open_records if is_acceptance(f))
            return "look", "waiting for your acceptance", self._action(
                skill="/factory-decisions", look=str(profile.get("run", "")).strip() or "start the application",
                shell=f"write accepted or your correction into {record} under `## Answer`", label="look at it",
                primary=True)
        if state == "waiting":
            return "question", "waiting for your answer", self._action(skill="/factory-decisions", shell=by_hand,
                                                                       label="answer", primary=True)
        if state == "unreleased":
            return "question", "draft — waits for your release", self._action(
                text="release it", skill=f"/factory-backlog release {story_id}",
                shell=f"set `status: approved` in {str(story.get('path', 'the story')).replace(chr(92), '/')}",
                label="release", primary=True)
        if state == "stopped":
            return "stopped", "stopped", self._action(text=detail, skill=f"/factory-status {story_id}",
                                                      shell=f"{RUNNER} status --story {story_id}")
        if "possibly interrupted" in detail:
            return "stopped", "interrupted?", self._action(text=detail, skill=f"/factory-run {story_id}",
                                                           shell=f"{RUNNER} run --story {story_id}",
                                                           label="run it again")
        if state == "running":
            return "running", "running", self._action()
        if state == "delivered":
            return "done", f"delivered, {detail}" if detail else "delivered", self._action()
        if state == "published":
            return "look", "published — waits for its merge", self._action(
                text="open the merge request from its branch; once merged, any factory's next look releases the claim",
                shell=f"{RUNNER} integrate {story_id}  (only after another merge request landed first)")
        if state == "claimed":
            return "none", "claimed elsewhere", self._action(text=detail, shell=f"{RUNNER} release {story_id} --force")
        if str(story.get("kind", "")) == "adopt" and state in ("ready", "in-progress", "resumable"):
            return "none", "to adopt", self._action(text=detail)
        if state == "blocked":
            return "none", "blocked", self._action(text=detail)
        if state in ("ready", "in-progress", "resumable"):
            words = {"ready": "ready", "in-progress": "in progress", "resumable": "can continue"}[state]
            return "none", words, self._action(text=detail)
        return "none", state, self._action(text=detail)

    def _open_record(self, story_id: str, story: Model) -> str:
        """The open record a waiting story waits on, as a path a person reads — '' where none is open."""
        records = self._facts.story_records(story_id, story.get("path"))
        opened = [(path, front) for path, front, _b, st, _a in records if st in WAITING_WORDS]
        chosen = next((p for p, f in opened if is_acceptance(f)), opened[0][0] if opened else "")
        return self._facts.shown(chosen) if chosen else ""

    def _next_line(self, data: Model, stories: Model, rows: typing.List[Model], empty: typing.List[str],
                   attention: typing.Dict[str, Action]) -> Model:
        """What comes next, in one sentence, with the action that does it."""
        nxt = data["next"]
        if nxt:
            return dict(text=f"{nxt} can start from {stories[nxt]['start'] or 'plan'} — run it.",
                        action=self._action(skill=f"/factory-run {nxt}", shell=f"{RUNNER} run --story {nxt}",
                                            label="run it", primary=True))
        if empty and all(r["state"] in ENDED_WORDS for r in rows):
            return dict(text=f"The epic {empty[0]} has no story yet — cut its stories.",
                        action=self._action(skill=f"/factory-backlog stories {empty[0]}", shell="",
                                            label="suggest stories", primary=True))
        if not rows:
            return dict(text="The backlog is empty — write the first story.",
                        action=self._action(skill="/factory-backlog", shell="", label="write a wish", primary=True))
        if all(r["state"] in ENDED_WORDS for r in rows):
            return dict(text="Every story is delivered — write the next one.",
                        action=self._action(skill="/factory-backlog", shell="", label="write a wish", primary=True))
        holder = next((r for r in rows if r["mark"] in ("look", "question", "stopped")), None)
        busy = next((r for r in rows if r["mark"] == "running"), None)
        action = self._action()
        if holder and stories[holder["story"]]["state"] == "unreleased":
            text, action = f"{holder['story']} is a draft — release it, and it runs.", attention[holder["story"]]
        elif holder:
            until = {"look": "is accepted", "question": "has its answer", "stopped": "is unblocked"}[holder["mark"]]
            text = f"Nothing else starts until {holder['story']} {until} — see Waiting for you."
            action = attention[holder["story"]]
        elif busy:
            text = f"{busy['story']} is running — one story at a time; nothing to do but wait."
        else:
            text = data["reason"] + "."
        return dict(text=text, action=action)

    def _journey_hints(self, stories: Model, epics: typing.List[Model]) -> typing.List[Model]:
        """An epic whose stories are all delivered and that has no `kind: journey` item: delivered, unguarded — the
        way to its outcome event has no test. A hint, never a stop. An epic decides against a journey with
        `- none: <why>` under `## Journey`; without the section it has decided nothing."""
        hints = []
        for epic in epics:
            paths = [stories[r["story"]].get("path", "") for r in epic["rows"]]
            kinds = [self._facts.story_kind(path) if path else "story" for path in paths]
            built = [r for r, k in zip(epic["rows"], kinds) if k == "story"]
            if not built or any(r["state"] != "delivered" for r in built) or "journey" in kinds or not paths[0]:
                continue
            text = self._facts.epic_text(paths[0])
            heading = re.search(r"^## Journey\s*$", text, re.M)
            section = text[heading.end():].split("\n## ", 1)[0] if heading else None
            if section is not None and re.search(r"^\s*-\s*none:", section, re.M):
                continue
            said = "the epic names no journey" if section is None \
                else "its journey is still open" if re.search(r"^\s*-\s*open:", section, re.M) or not section.strip() \
                else "its journey has no journey test yet"
            hints.append(dict(epic=epic["epic"], text=f"delivered, unguarded — {said}",
                              action=self._action(skill=f"/factory-backlog journey {epic['epic']}", shell="",
                                                  label="add guard")))
        return hints

    def _findings(self) -> typing.List[Model]:
        """What else waits for a person: the judge's open minors, a story's or the project's."""
        findings = []
        for found in self._facts.finding_records():
            story, plain, defect, kept = found["owner"], found["plain"], found["defect"], self._facts.shown(found["path"])
            # `plain` leads: the finding in one sentence a person understands at once (contract 23; '' in an older
            # row). A project finding (`<product>/findings/<name>.md`, WP-146) belongs to no story: the backlog skill
            # is handed its row, which a task's `closes:` names.
            findings.append(dict(story=story, row=found["row"], project=found["project"], plain=plain,
                                 where=found["where"], severity=found["severity"], defect=defect,
                                 perspective=found["perspective"], fix=found["fix"], file=kept,
                                 action=self._action(text=f"fix it in a story, or set its Status to done or wont-fix "
                                                          f"in {kept}",
                                                     skill=f"/factory-backlog {found['row'] if found['project'] else story}: "
                                                           f"{plain or defect}", label="to the backlog")))
        return findings

    def _foreign_claims(self) -> typing.List[Model]:
        """The claims other factories hold, as the last fetch saw them: `held` — who holds which story and for how
        long, `stale` past three days; `orphan` — a claim whose story this checkout does not have; `collision` — a
        claim on an id this checkout uses for another story. Each with what a person does about it."""
        found = []
        now = self._facts.now()
        for c in self._facts.foreign_claims():
            story = c["story"]
            age, stale = claim_age(c["since"], now)
            entry = dict(story=story, who=c["who"], host=c["host"], since=c["since"], age=age, stale=stale,
                         title=c["title"])
            if not c["here"]:
                found.append(dict(entry, kind="orphan", action=self._action(
                    text="this checkout has no such story — take the claim away",
                    shell=f"{RUNNER} release {story} --force")))
                continue
            if (c["epic"] and c["epic"] != c["own_epic"]) or (c["title"] and c["title"] != c["own_title"]):
                found.append(dict(entry, kind="collision", action=self._action(
                    text=f"another factory claimed {story} for \"{c['title']}\" — give yours another id",
                    skill="/factory-backlog",
                    shell=f"python3 .agents/factory/factory-cli.py --free-id {re.sub(r'[-_]?[0-9]+$', '', story)}")))
                continue
            found.append(dict(entry, kind="held", action=self._action(
                text="not built here" + ("; a stale claim may be forgotten — ask its holder, or take it away" if stale
                                         else ""),
                shell=f"{RUNNER} release {story} --force" if stale else "")))
        return found


def is_acceptance(front: Model) -> bool:
    """A record that asks for a person's look at a delivered story (`kind: acceptance`)."""
    return str(front.get("kind", "")).strip().lower() == "acceptance"


def created_of(front: Model) -> str:
    """The story's `created:`, as written — '' where it has none."""
    value = front.get("created")
    return str(value).strip() if value and not isinstance(value, list) else ""
