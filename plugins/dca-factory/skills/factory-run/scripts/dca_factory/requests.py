"""A request: one file per thing a person wants the factory to do — written from a browser page, a terminal or a
session's view, worked by the factory between stories (WP-91).

A request is protocol, not state: `<factory folder>/requests/<stamp>-<kind>.md` (the stamp UTC to the millisecond), front matter and the person's words
as its body. What it does lands in the project's own files — a story, an answer, the description — and the request is
deleted once done. While it lives, its `state:` says where it is:

    queued    written, nobody took it yet
    running   a factory works it (`worker:`, `started:`)
    waiting   the skill it ran asked a person: a decision record names it (`request: <id>`), `record:` says which;
              answered, the request runs again with the answer
    failed    refused when it was read, or its skill ended without a result (`error:`); a person drops or retries it

Every kind names what it is about in its own key — `story:`, `epic:`, `record:`, `topic:` with `proposal:` — and the
person's words, where it takes any, are the body. `option:` carries an option key (an answer's, a correction's code).
"""

import contextlib
import getpass
import json
import os
import re
import time
import typing

from .contract import (
    decision_files, decision_options, find_story, GateError, is_delivered, location,
    place, project_decisions_dir, read_front_matter, read_profile, read_text, resolve_profile, shown, split_front,
    STAGES, story_files, story_folder, story_id_of, git)
from .state import acceptance_records, is_acceptance
from .gate import discovery_items, REASON_CODES


REQUESTS = "requests"
REQUEST_JOURNAL = "journal.tsv"
REQUEST_OUT = "out"
STATES = ("queued", "running", "waiting", "failed")


class Kind(typing.NamedTuple):
    """One kind of request: what it must name, whether it takes words, and the skill a session would run for it —
    none for the two the runner works itself (`run`, `stop`)."""
    name: str
    keys: tuple = ()          #: the keys it must name — `story`, `epic`, `record`, `topic`, `proposal`
    words: str = "none"       #: the person's words: "required", "optional" or "none"
    option: bool = False      #: it takes `option:` — an answer's option key, a correction's reason code
    skill: str = ""           #: the skill a session would run; "" — the runner works it itself
    about: str = ""


KINDS = (
    Kind("wish", words="required", skill="factory-backlog",
         about="the person's words become a backlog item — a story, a task, a finding settled — kept as a draft"),
    Kind("release", keys=("story|epic",), skill="factory-backlog",
         about="release drafts — stories by id, or every draft of an epic — where the question pass leaves nothing open"),
    Kind("stories", keys=("epic",), skill="factory-backlog", about="cut the next stories of an epic, as drafts"),
    Kind("journey", keys=("epic",), skill="factory-backlog", about="propose the journey of a delivered epic"),
    Kind("describe", words="required", skill="description",
         about="a change to the project description, in the person's words (`<part>: <change>`)"),
    Kind("discover", words="required", skill="factory-discover",
         about="a problem or a wished deliverable — the discovery report and the epics it proposes"),
    Kind("epic-from", keys=("topic", "proposal"), skill="factory-backlog",
         about="a discovery's proposed epic, released as an epic"),
    Kind("answer", keys=("record",), words="optional", option=True, skill="factory-decisions",
         about="the answer to an open question — an option key or the person's words"),
    Kind("accept", keys=("story",), skill="factory-decisions", about="accept a story that waits for a person's look"),
    Kind("correct", keys=("story",), words="required", option=True, skill="factory-decisions",
         about="a correction of a story at its acceptance or after its delivery — `option:` the reason code"),
    Kind("run", keys=("story",), about="run a story now — from where its files say, or `from:` a stage"),
    Kind("stop", about="the factory ends after the running stage"),
)


KIND = {kind.name: kind for kind in KINDS}


#: A story, an epic, a record, a topic or a proposal as a request names it: one word, no path.
ID_WORD = re.compile(r"^[A-Za-z0-9][\w.#-]*$")


#: The keys a request's front matter may carry, in the order they are written.
FRONT_KEYS = ("kind", "story", "epic", "record", "topic", "proposal", "report", "option", "from", "by", "asked",
              "state", "worker", "started", "attempts", "record_file", "error", "answered")


class RequestError(Exception):
    """A request that cannot be written or read, with the reason a person reads."""


class Duplicate(RequestError):
    """The same request is queued already — a second press, not a second wish."""

    def __init__(self, existing):
        super().__init__(f"the same request is queued already: {existing}")
        self.existing = existing


# --- places ----------------------------------------------------------------------------------------------------------
def factory_dir():
    """The factory's own folder, the run folder's parent: `.dca-factory` by default."""
    runs = place("runs").rstrip("/")
    return os.path.dirname(runs) or ".dca-factory"


def requests_dir():
    return os.path.join(factory_dir(), REQUESTS)


def request_path(request_id):
    return os.path.join(requests_dir(), f"{request_id}.md")


def out_path(request_id):
    """Where the tool's raw output of a request's run is kept: beside the requests, pruned with the run folders."""
    return os.path.join(requests_dir(), REQUEST_OUT, f"{request_id}.out")


def stamp_utc(moment=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))


def default_by(cwd):
    """Who asks, where nobody said: the repository's `user.name`, else the account's name."""
    code, name = git(cwd, "config", "user.name")
    if code == 0 and name.strip():
        return name.strip()
    with contextlib.suppress(Exception):
        return getpass.getuser()
    return "unknown"


# --- what a request names ------------------------------------------------------------------------------------------
def epic_dir(epics, epic_id):
    """The folder of the epic with this id — its folder's name or its `id:` — or None."""
    if not os.path.isdir(epics):
        return None
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, "epic.md")
        if not os.path.isfile(path):
            continue
        if name.lower() == epic_id.lower():
            return os.path.dirname(path)
        with contextlib.suppress(GateError):
            if str(read_front_matter(path)[0].get("id", "")).strip().lower() == epic_id.lower():
                return os.path.dirname(path)
    return None


def story_of(cwd, story_id):
    """(path, front) of the story with this id; RequestError naming the backlog when there is none."""
    epics = os.path.join(cwd, place("epics"))
    try:
        path = find_story(epics, story_id)
    except GateError as error:
        raise RequestError(f"no story {story_id} under {place('epics')}/ — {error}") from None
    return path, read_front_matter(path)[0]


def record_of(cwd, record_id):
    """(path, front, body, state) of the decision record with this id — beside its story, or the project's own."""
    for name, front, body, state, error, path in decision_files(cwd):
        rid = str(front.get("id", name)).strip() if not error else name
        if rid.lower() == record_id.lower():
            if error:
                raise RequestError(f"{shown(path)} cannot be read — {error}")
            return path, front, body, state
    raise RequestError(f"no decision record {record_id} — `factory.sh decisions` lists them")


def discovery_report(cwd, topic):
    folder = location(read_profile(resolve_profile(None, cwd)), "discovery")
    report = f"{folder}/{topic}/discovery.md".replace(os.sep, "/")
    return report if os.path.isfile(os.path.join(cwd, report)) else None


def open_acceptance(cwd, story_id, story_path):
    found = [rid for rid, front, state, _a, _b in acceptance_records(cwd, story_id, story_path)
             if state in ("open", "draft")]
    return found[-1] if found else None


def validate(cwd, kind_name, fields, words):
    """The request as it will be written: its fields checked against the project's files and completed where the
    files name what the person meant (an answer's story, an acceptance's record, a proposal's report). RequestError
    with the reason otherwise — a malformed request never reaches the factory."""
    kind = KIND.get(kind_name)
    if kind is None:
        raise RequestError(f"no request kind {kind_name!r} — one of: {', '.join(KIND)}")
    fields = {k: str(v).strip() for k, v in (fields or {}).items() if v is not None and str(v).strip()}
    words = (words or "").strip()
    allowed = written_keys(kind)
    stray = sorted(set(fields) - allowed)
    if stray:
        raise RequestError(f"a {kind.name} request takes no {', '.join(stray)}")
    for spec in kind.keys:
        given = [key for key in spec.split("|") if key in fields]
        if not given:
            raise RequestError(f"a {kind.name} request names its {' or '.join(spec.split('|'))}")
        if len(given) > 1:
            raise RequestError(f"a {kind.name} request names its {' or its '.join(spec.split('|'))}, not both")
    for key, value in fields.items():
        for word in (value.split() if key == "story" and kind.name == "release" else [value]):
            if not ID_WORD.match(word):
                raise RequestError(f"{key}: {word!r} is no id — one word, letters, digits, `.`, `_`, `-`, `#`")
    if kind.words == "required" and not words:
        raise RequestError(f"a {kind.name} request carries the person's words")
    if kind.words == "none" and words:
        raise RequestError(f"a {kind.name} request takes no words")
    if "\0" in words or len(words) > 20000:
        raise RequestError("the words are too long or carry a NUL")
    epics = os.path.join(cwd, place("epics"))
    if kind.name == "release" and "story" in fields and len(fields["story"].split()) == 1 \
            and epic_dir(epics, fields["story"]):
        fields["epic"] = fields.pop("story")          # `release <id>`: an id that names an epic's folder is the epic
    if "story" in fields:
        for story_id in fields["story"].split():
            story_of(cwd, story_id)
    if "epic" in fields and not epic_dir(epics, fields["epic"]):
        raise RequestError(f"no epic {fields['epic']} under {place('epics')}/")
    name = kind.name
    if name == "answer":
        path, front, body, state = record_of(cwd, fields["record"])
        if is_acceptance(front):
            raise RequestError(f"{fields['record']} asks for an acceptance — accept or correct the story instead")
        if state in ("answered", "applied"):
            raise RequestError(f"{fields['record']} is {state} already — an answer is never overwritten; a change of "
                               "mind is a new question")
        options = decision_options(body)
        named = next((o["key"] for o in options if o["key"].lower() == words.lower()), None)
        if not fields.get("option") and named:
            fields["option"], words = named, ""            # the words name one of the record's options: that option
        if not fields.get("option") and re.fullmatch(r"[A-Za-z0-9]{1,2}", words or "-"):
            raise RequestError(f"{fields['record']} has no option {words!r}"
                               + (f" — its options: {', '.join(o['key'] for o in options)}" if options else
                                  " — it lists none; answer in words"))
        if not fields.get("option") and not words:
            raise RequestError(f"an answer names an option{' (' + ', '.join(o['key'] for o in options) + ')' if options else ''} "
                               "or carries the person's words")
        if fields.get("option") and fields["option"].lower() not in {o["key"].lower() for o in options}:
            raise RequestError(f"{fields['record']} has no option {fields['option']!r}"
                               + (f" — its options: {', '.join(o['key'] for o in options)}" if options else
                                  " — it lists none; answer in words"))
        fields["record"] = str(front.get("id", fields["record"])).strip()
        story = str(front.get("story", "")).strip()
        if story:
            fields["story"] = story
    if name in ("accept", "correct"):
        path, front = story_of(cwd, fields["story"])
        fields["story"] = story_id_of(path, front)
        record = open_acceptance(cwd, fields["story"], path)
        if record:
            fields["record"] = record
        elif name == "accept":
            raise RequestError(f"{fields['story']} waits for no acceptance — nothing to accept")
        elif not is_delivered(front):
            raise RequestError(f"{fields['story']} neither waits for an acceptance nor is delivered — a change before "
                               "is the backlog's: a wish")
        if name == "correct" and fields.get("option") and fields["option"].lower() not in REASON_CODES:
            raise RequestError(f"a correction's code is one of {', '.join(REASON_CODES)} — not {fields['option']!r}")
    if name == "epic-from":
        report = discovery_report(cwd, fields["topic"])
        if not report:
            raise RequestError(f"no discovery report for topic {fields['topic']} — `factory.sh discover --list`")
        proposals = [pid for pid, _f in discovery_items(read_text(os.path.join(cwd, report)), "Proposed work")]
        if fields["proposal"] not in proposals:
            raise RequestError(f"{report} proposes no {fields['proposal']}"
                               + (f" — it proposes {', '.join(proposals)}" if proposals else ""))
        if epic_dir(epics, fields["proposal"]):
            raise RequestError(f"{fields['proposal']} is an epic already")
        fields["report"] = report
    if name == "run":
        path, front = story_of(cwd, fields["story"])
        fields["story"] = story_id_of(path, front)
        names = [stage.name for stage in STAGES]
        if fields.get("from") and fields["from"] not in names:
            raise RequestError(f"from: {fields['from']} names no stage ({' '.join(names)})")
    return fields, words


# --- a session's command as a request ----------------------------------------------------------------------------------
def names_story(word):
    """Whether one word is the id of a story under the epics, as the profile places them."""
    if not ID_WORD.match(word):
        return False
    wanted = word.lower()
    with contextlib.suppress(GateError, OSError):
        return any(os.path.basename(story_folder(path)).lower() == wanted or story_id_of(path).lower() == wanted
                   for path in story_files(place("epics")))
    return False


def request_of(skill):
    """The request that does what a view's action does in a session — `/factory-run <story>`, `/factory-backlog …`,
    `/factory-decisions <story> <record>: answer <key>`, `/dca-describe <change>`, `/factory-discover <words>` — as
    {kind, fields, words, open}: `open` names what the person still has to give (words, an option). None for an
    action no request does (setting the factory up, updating it, a verification)."""
    text = " ".join(str(skill or "").split())
    head, _, rest = text.partition(" ")
    if head == "/factory-run":
        # as the skill reads it: a story's id runs that story, every other word is a wish
        if not rest:
            return None
        return dict(kind="run", fields=dict(story=rest), words="", open="") if names_story(rest) \
            else dict(kind="wish", fields={}, words=rest, open="")
    if head == "/factory-backlog":
        verb, _, tail = rest.partition(" ")
        if verb == "release" and tail:
            return dict(kind="release", fields=dict(story=tail), words="", open="")
        if verb in ("stories", "journey") and ID_WORD.match(tail or "-"):
            return dict(kind=verb, fields=dict(epic=tail), words="", open="")
        match = re.match(r"^epic (\S+) --from (\S+)$", rest)
        if match:
            topic = os.path.basename(os.path.dirname(match.group(2)))
            return dict(kind="epic-from", fields=dict(topic=topic, proposal=match.group(1)), words="", open="")
        return dict(kind="wish", fields={}, words=rest, open="" if rest else "words")
    if head == "/factory-decisions":
        match = re.match(r"^(?:(\S+) )?(\S+): answer (.+)$", rest)
        if match:
            return dict(kind="answer", fields=dict(record=match.group(2)), words=match.group(3), open="")
        story = rest.split()[0] if rest else ""
        return dict(kind="answer", fields=dict(story=story) if story else {}, words="", open="record")
    if head == "/dca-describe":
        return dict(kind="describe", fields={}, words=rest, open="" if rest else "words")
    if head == "/factory-discover":
        return dict(kind="discover", fields={}, words=rest, open="" if rest else "words")
    return None


def written_keys(kind):
    """The keys a person gives a request of this kind — what `validate` takes; the rest it adds from the files."""
    return {key for spec in kind.keys for key in spec.split("|")} | ({"option"} if kind.option else set()) \
        | ({"from"} if kind.name == "run" else set())


# --- the file ------------------------------------------------------------------------------------------------------------
def request_front_text(front):
    lines = ["---"]
    for key in FRONT_KEYS:
        value = front.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {' '.join(str(value).split())}")
    return "\n".join(lines + ["---", ""])


def write_atomic(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)


def same_request(one, other):
    keys = ("kind", "story", "epic", "record", "topic", "proposal", "option", "from")
    return all(str(one.get(k) or "") == str(other.get(k) or "") for k in keys) and one["words"] == other["words"]


def write_request(cwd, kind_name, fields=None, words="", by=""):
    """Write one request after `validate`: (id, path). Duplicate when the same request waits already."""
    fields, words = validate(cwd, kind_name, fields, words)
    folder = requests_dir()
    wanted = dict(fields, kind=kind_name, words=words)
    for existing in list_requests():
        if existing["state"] in ("queued", "running", "waiting") and same_request(existing, wanted):
            raise Duplicate(existing["id"])
    # to the millisecond, and later than every request there: the files sort in the order they were written,
    # whatever their kind — two in one millisecond included
    millis = int(time.time() * 1000)
    newest = max((n[:19] for n in os.listdir(folder) if re.match(r"^\d{8}T\d{9}Z", n)), default="") \
        if os.path.isdir(folder) else ""
    stamp_of = lambda ms: time.strftime("%Y%m%dT%H%M%S", time.gmtime(ms // 1000)) + f"{ms % 1000:03d}Z"
    while stamp_of(millis) <= newest:
        millis += 1
    stamp = stamp_of(millis)
    request_id, n = f"{stamp}-{kind_name}", 1
    os.makedirs(folder, exist_ok=True)
    while True:
        path = os.path.join(folder, f"{request_id}.md")
        try:
            # created exclusively: two presses in one second get two names, never one file
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            n += 1
            request_id = f"{stamp}.{n}-{kind_name}"     # `.` sorts after `-`: the second of a second stays second
    front = dict(fields, kind=kind_name, by=" ".join((by or default_by(cwd)).split()), asked=stamp_utc(), state="queued")
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(request_front_text(front) + (f"\n{words}\n" if words else ""))
    return request_id, path


def read_request(path):
    """The request as a dict — its id, path, front keys, `words` (the body) and `state`; a file that cannot be read
    is `failed` with the reason, so a broken request shows and is never worked."""
    request_id = os.path.basename(path)[:-3]
    try:
        front, body = read_front_matter(path)
    except (GateError, OSError, UnicodeDecodeError) as error:
        return dict(id=request_id, path=path, kind="?", words="", state="failed", error=f"unreadable — {error}")
    request = {k: (" ".join(v) if isinstance(v, list) else str(v)).strip() for k, v in front.items()}
    request.update(id=request_id, path=path, words=body.strip())
    if request.get("kind") not in KIND:
        request.update(state="failed", error=request.get("error") or f"no request kind {request.get('kind')!r}")
    elif request.get("state") not in STATES:
        request["state"] = "queued"
    return request


def list_requests():
    """Every request, oldest first — the order the factory works them in."""
    folder = requests_dir()
    if not os.path.isdir(folder):
        return []
    return [read_request(os.path.join(folder, name)) for name in sorted(os.listdir(folder))
            if name.endswith(".md") and not name.startswith(".")]


def find_request(request_id):
    path = request_path(request_id)
    if not ID_WORD.match(request_id) or not os.path.isfile(path):
        raise RequestError(f"no request {request_id} — `factory.sh requests` lists them")
    return read_request(path)


def update_request(request, **fields):
    """Set — or with None remove — front keys of a request, its words kept."""
    path = request["path"]
    try:
        if split_front(read_text(path)) is None:
            return
    except (GateError, OSError, UnicodeDecodeError):
        return                                       # dropped meanwhile: nothing left to update
    front = {k: v for k, v in request.items() if k in FRONT_KEYS}
    for key, value in fields.items():
        if value is None:
            front.pop(key, None)
        else:
            front[key] = value
        request[key] = value
    write_atomic(path, request_front_text(front) + (f"\n{request['words']}\n" if request.get("words") else ""))


def drop_request(request_id):
    """A person's request taken back — one that runs now is the factory's until it ends."""
    request = find_request(request_id)
    if request["state"] == "running":
        raise RequestError(f"{request_id} runs now — it can be dropped once it ended")
    os.remove(request["path"])
    return request


def retry_request(request_id):
    """A failed request queued again, as it was written."""
    request = find_request(request_id)
    if request["state"] != "failed":
        raise RequestError(f"{request_id} is {request['state']} — only a failed request is retried")
    if request.get("kind") not in KIND:
        raise RequestError(f"{request_id} cannot be read as a request — drop it")
    update_request(request, state="queued", error=None, worker=None, started=None)
    return request


# --- what a request is about --------------------------------------------------------------------------------------------
def stories_of(request):
    """The stories a request changes or runs — what must not run while it is worked, and the reverse."""
    return set((request.get("story") or "").split())


def request_records(cwd, request_id):
    """Every decision record a request's skill wrote to ask a person — `request: <id>` in its front matter, beside a
    story or the project's own: [(path, id, state)]."""
    found = []
    for name, front, _body, state, error, path in decision_files(cwd):
        if not error and str(front.get("request", "")).strip() == request_id:
            found.append((path, str(front.get("id", name)).strip(), state))
    return found


def project_record_path(request_id, topic):
    """Where a request's question with no story is kept: `<product>/decisions/<stamp>-<topic>.md`."""
    word = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40] or "question"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return os.path.join(project_decisions_dir(), f"{stamp}-{word}.md")


def target_text(request):
    """What a request is about, as one short phrase."""
    for key in ("record", "story", "epic"):
        if request.get(key):
            return request[key]
    if request.get("proposal"):
        return f"{request.get('topic')}/{request['proposal']}"
    words = " ".join(request.get("words", "").split())
    return (words[:60] + "…") if len(words) > 60 else words


def counts():
    found = {state: 0 for state in STATES}
    for request in list_requests():
        found[request["state"]] = found.get(request["state"], 0) + 1
    return found


# --- the journal ---------------------------------------------------------------------------------------------------------
def journal(*fields):
    """One line of the factory's request journal — `<at>\\t<event>\\t…` — beside the requests."""
    os.makedirs(requests_dir(), exist_ok=True)
    with contextlib.suppress(OSError):
        with open(os.path.join(requests_dir(), REQUEST_JOURNAL), "a", encoding="utf-8", newline="\n") as handle:
            handle.write("\t".join([stamp_utc(), *(" ".join(str(f).split()) for f in fields)]) + "\n")


def journal_lines(limit=50):
    path = os.path.join(requests_dir(), REQUEST_JOURNAL)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n").split("\t") for line in handle.readlines()[-limit:]]


def prune_outputs(days=7, now=None):
    """The raw outputs of requests that ended more than <days> ago — protocol, kept for a look, not forever."""
    folder = os.path.join(requests_dir(), REQUEST_OUT)
    if not os.path.isdir(folder):
        return
    limit = (now or time.time()) - days * 86400
    live = {r["id"] for r in list_requests()}
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        with contextlib.suppress(OSError):
            if name.rsplit(".", 1)[0] not in live and os.path.getmtime(path) < limit:
                os.remove(path)


# --- the view ------------------------------------------------------------------------------------------------------------
def view(fmt="text"):
    """`factory.sh requests`: every request with its state, oldest first."""
    rows = []
    for request in list_requests():
        rows.append(dict(id=request["id"], kind=request.get("kind", "?"), state=request["state"],
                         target=target_text(request), by=request.get("by", ""), asked=request.get("asked", ""),
                         worker=request.get("worker", ""), started=request.get("started", ""),
                         record=request.get("record_file", ""), error=request.get("error", ""),
                         words=request.get("words", ""), option=request.get("option", ""),
                         story=request.get("story", ""), epic=request.get("epic", ""), path=shown(request["path"])))
    model = dict(requests=rows, counts={s: sum(r["state"] == s for r in rows) for s in STATES},
                 kinds=[dict(kind=k.name, keys=list(k.keys), words=k.words, option=k.option, about=k.about)
                        for k in KINDS],
                 store=shown(requests_dir()) + "/")
    if fmt == "json":
        print(json.dumps(model, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print(f"requests: none — `factory.sh request <kind> …` writes one ({model['store']})")
        return 0
    for row in rows:
        extra = row["error"] or (f"asks: {row['record']}" if row["record"] else "") or \
            (f"{row['worker']} since {row['started']}" if row["state"] == "running" else "")
        print(f"{row['id']}  {row['state']:<8} {row['kind']:<9} {row['target']}  ({row['by']})"
              + (f" — {extra}" if extra else ""))
    print("requests: " + ", ".join(f"{n} {s}" for s, n in model["counts"].items() if n))
    return 0
