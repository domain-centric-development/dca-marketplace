"""Show the factory explained: the flow with where this project stands in it, the commands, the marks, the files."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.project_facts import ProjectFacts
from ..shared.status_facts import StatusFacts
from .actions import make_action, RUNNER
from .show_status import ShowStatusInputPort, ShowStatusQuery
from ...domain.model.story_state import ENDED_WORDS

Model = typing.Dict[str, typing.Any]

HELP_COMMANDS = (
    ("deliver a wish", "your words become a backlog story — which epic, the criteria — and it runs at once",
     "/factory-run <your words>", ""),
    ("where it stands", "what runs, what waits for you, what comes next, the totals — short",
     "/factory-status", "status"),
    ("every story", "the backlog by epic, newest first, with times and tokens", "/factory-status all", "status --all"),
    ("one story", "its words, criteria, stages, passes and tokens", "/factory-status <story>", "status --story <story>"),
    ("one epic", "what it is for, its text, its stories with their state", "/factory-status <epic>",
     "status --epic <epic>"),
    ("follow a stage", "what the running stage reads, edits and runs, as it happens — whoever started it", "",
     "follow"),
    ("start the factory", "a process of its own in the background: your requests and the backlog, until it is "
                          "ended — --serve the page too", "", "up [--serve]"),
    ("end the factory", "after its running stage; --now interrupts that stage too", "", "down"),
    ("the page", "the factory in the browser, on this machine alone — every press a request", "", "serve"),
    ("ask the factory", "one request it works before its next story: a wish, a release, an answer, an acceptance, …",
     "", "request <kind> …"),
    ("the requests", "what you asked and where each stands — retry or drop one", "", "requests"),
    ("find the problem", "a problem or a wished deliverable → a report with sources and proposed epics, each with "
                         "its outcome event", "/factory-discover <topic>", "discover --check <topic>"),
    ("the discoveries", "every topic, its proposed epics and which are epics already, its proposed description changes",
     "/factory-discover", "discover --list"),
    ("release a proposal", "a discovery's proposed epic becomes an epic in the backlog",
     "/factory-backlog epic <id> --from <report>", ""),
    ("cut stories", "the next stories of an epic, each a draft", "/factory-backlog stories <epic>", ""),
    ("release stories", "drafts become approved after the question pass — open questions keep them drafts",
     "/factory-backlog release <story> …", ""),
    ("guard an epic", "a delivered, unguarded epic gets its journey — the timeline to its outcome event and its "
                      "journey item as a draft", "/factory-backlog journey <epic>", ""),
    ("change the description", "one statement of the product, the stack or the domain, in your words",
     "/dca-describe <change>", ""),
    ("the backlog", "the epics and stories, their state, the next one", "/factory-backlog", "backlog"),
    ("check the backlog", "the plan gate's checks over every open story, writing nothing", "/factory-backlog",
     "backlog --check"),
    ("the inbox", "the open questions and acceptances, and how to answer them", "/factory-decisions", "decisions"),
    ("give up a claim", "with `claim_remote:` — a story's claim on the remote taken back (another's with --force)", "",
     "release <story>"),
    ("deliver again", "with `claim_remote:` — a published story whose merge request lost the race, merged again",
     "", "integrate <story>"),
    ("the profile", "what detection finds against the stack profile", "/factory-setup", "setup --check"),
    ("observe a story", "what a delivered story changed, measured from its files", "/factory-verify <story>",
     "verify --story <story>"),
    ("the machinery", "the pipeline's own suite against fixtures — for whoever changes the pipeline",
     "/factory-verify --fixtures", "verify --fixtures"),
    ("one stage by hand", "stage-plan … stage-document are the six stages the run calls; by hand only to redo one "
                          "stage of a story that has the ones before", "/stage-<stage> <story>", ""),
    ("update the pipeline", "the newest pipeline found, same tools", "/factory-update", "update"),
    ("this help", "the flow, the commands, the marks, the files", "/factory-help", "help"),
)

HELP_MARKS = (("look", "waits for your look — an acceptance"), ("question", "waits for your answer"),
              ("stopped", "stopped — read why before it runs again"), ("running", "running"),
              ("done", "done — a story, an epic, a decision"), ("none", "nothing to do there now"))


@dataclasses.dataclass(frozen=True)
class ShowHelpQuery:
    pass


class ShowHelpInputPort(UseCase[ShowHelpQuery, Model], typing.Protocol):
    """The factory explained."""


class ShowHelpUseCase:
    """The factory explained in one fixed view: the text is the same everywhere; only the marks in the flow and the
    Next line come from the project."""

    def __init__(self, status: ShowStatusInputPort, project: ProjectFacts, facts: StatusFacts) -> None:
        self._status, self._project, self._facts = status, project, facts

    def execute(self, query: ShowHelpQuery) -> Model:
        project = self._project
        profile_file = project.profile_file()
        status_view = self._status.execute(ShowStatusQuery())
        described = project.described()
        has_build = project.has_build()
        marks = {m["mark"] for m in status_view["waiting"]}
        rows = status_view["rows"]
        delivered = bool(rows) and all(r["state"] in ENDED_WORDS for r in rows)
        has_stories = bool(rows) and not delivered
        waiting_mark = "look" if "look" in marks else ("question" if "question" in marks else "")
        started = described and has_build
        # what waits for a person comes first: nothing of theirs moves until it is answered
        if waiting_mark:
            here = "decide"
        elif not started:
            here = "describe"
        elif not profile_file:
            here = "set up"
        elif not has_stories:
            here = "backlog"
        else:
            here = "run"
        # A foundation, done once and changed when the product or the stack moves, and a cycle that recurs with
        # every body of work. The foundation's steps can be done; the cycle's never are — there the flow marks
        # only where the project is now (waiting, running, next).
        flow: typing.List[Model] = [
            dict(step="describe", part="foundation",
                 what="product, technical decisions, designed domain — a new project with its skeleton: /dca-new project",
                 skill="/dca-describe", shell="", done=started),
            dict(step="set up", part="foundation",
                 what="the stack profile: build, test, format and browser commands, the carriers",
                 skill="/factory-setup", shell="setup --check" if profile_file else "setup", done=bool(profile_file)),
            dict(step="discover", part="cycle", what="optional: which problem is worth solving — a report with sources "
                                                     "and proposed epics, each with its outcome event",
                 skill="/factory-discover <topic>", shell="discover --list"),
            dict(step="backlog", part="cycle",
                 what="epics and stories with acceptance criteria; a story runs once released",
                 skill="/factory-backlog", shell="backlog"),
            dict(step="run", part="cycle", what="plan → test → build → tidy → judge → document, a gate between the stages",
                 skill="/factory-run [<story>]", shell="run [--story <story>]"),
            dict(step="decide", part="cycle", what="a question a stage may not decide alone, or a result to look at: "
                                                   "accepted delivers it, a correction goes back into the story",
                 skill="/factory-decisions", shell="decisions"),
            dict(step="delivered", part="cycle", what="what is delivered — stories, epics and their outcome events; an "
                                                      "epic without a journey test shows as unguarded",
                 skill="/factory-status", shell="status"),
        ]
        for n, f in enumerate(flow, 1):
            f["number"] = n
            if f["step"] == here:
                f["mark"] = waiting_mark if here == "decide" else \
                    "running" if here == "run" and status_view["running"] else "next"
            else:
                f["mark"] = "done" if f.pop("done", False) else "none"
            f.pop("done", None)
        if waiting_mark:
            nxt = status_view["next"]
        elif not described and has_build:
            nxt = dict(text="Describe the project — drafted from its code, confirmed by you.",
                       action=self._action(skill="/dca-describe"))
        elif not has_build:
            nxt = dict(text="Start the project — the description and a skeleton from a generator, in one pass.",
                       action=self._action(skill="/dca-new project"))
        elif not profile_file:
            nxt = dict(text="Set the factory up — the stack profile is missing.",
                       action=self._action(skill="/factory-setup", shell=f"{RUNNER} setup"))
        else:
            nxt = status_view["next"]
        place = project.place
        epics = place("epics")
        files = [("description", ", ".join(place(k) for k in ("product", "tech", "domain")),
                  "what is built, on which stack, in which contexts"),
                 ("spec", place("spec").rstrip("/") + "/",
                  "what holds: per context scenarios.md with a test line each, and its glossary.md; journeys.md"),
                 ("epics", epics + "/", "the changes: an epic.md per epic, a folder per story with its story.md; a "
                                        "delivered story says so itself"),
                 ("stack profile", profile_file or project.profile_name(),
                  "the project's commands and the skills each stage uses"),
                 ("decisions", f"{epics}/<epic>/<story>/{place('decisions')}/",
                  "one record per question or acceptance, in its story's folder"),
                 ("a story's run", f"{place('runs')}/<story>/", "hand-overs, marks, the journal — protocol, disposable")]
        return dict(project=status_view["project"],
                    flow=flow, commands=[dict(zip(("name", "what", "skill", "shell"), c)) for c in HELP_COMMANDS],
                    marks=[dict(mark=m, meaning=t) for m, t in HELP_MARKS],
                    files=[dict(name=n, where=w, holds=h) for n, w, h in files],
                    runner=RUNNER, next=nxt)

    def _action(self, skill: str = "", shell: str = "") -> typing.Any:
        return make_action(self._facts.names_story, skill=skill, shell=shell)
