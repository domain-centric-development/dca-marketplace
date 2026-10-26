"""Story claims across factories (WP-93): a story's branch on the remote as its lock, the claims read off the last fetch, a story id free on the remote."""

from __future__ import annotations

import contextlib
import os
import typing
from datetime import datetime, timezone
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..files.story_layout import STORY_FILE, story_files, story_folder
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home, place, read_profile, resolve_profile, STORY_BRANCH
from ..git.repository import git, git_blob
from ..files.journal_files import journal_append
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text, split_front
from ....domain.model.claim import ClaimedFor, ClaimTitle, Fate, IdPrefix, Meeting, Worker
from ....domain.model.epic import EpicId
from ....domain.model.stage_story import Presence
from ....domain.model.story import StoryId, StoryStatus
from ....domain.service.claim_rules import ClaimRules


CLAIMS_FILE = "claims.tsv"


PUBLISHED = "published"


CLAIM_TRAILERS = ".claim-trailers"


def claim_config(profile: typing.Mapping[str, typing.Any]) -> typing.Optional[typing.Dict[str, str]]:
    """{"remote", "prefix"} where the profile opts in with `claim_remote:`, else None."""
    remote = str(profile.get("claim_remote", "")).strip()
    if not remote:
        return None
    prefix = str(profile.get("claim_branch_prefix", "")).strip() or "story/"
    return {"remote": remote, "prefix": prefix}


def claim_config_here(cwd: typing.Optional[str] = None) -> typing.Optional[typing.Dict[str, str]]:
    return claim_config(read_profile(resolve_profile(None, cwd or os.getcwd())))


def identity(cwd: str) -> typing.Tuple[str, str]:
    """(email, host) — who claims: the same person on a second machine is another factory."""
    import socket
    email = git(cwd, "config", "user.email")[1].strip() or "unknown"
    return email, socket.gethostname()


def claims_path(runs: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(runs)), CLAIMS_FILE)


def remote_main(remote: str, target: str) -> str:
    return f"refs/remotes/{remote}/{target}"


def fetch_remote(cwd: str, remote: str) -> typing.Tuple[int, str]:
    return git(cwd, "fetch", "--quiet", "--prune", remote)


def trailers_of(text: str) -> typing.Dict[str, str]:
    found: typing.Dict[str, str] = {}
    for line in text.splitlines():
        for key in ("Factory-Claim", "Factory-Story", "Story"):
            if line.startswith(key + ":"):
                found.setdefault(key, line.split(":", 1)[1].strip())
    return found


def read_remote_claims(cwd: str, remote: str, prefix: str) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
    """{story: {"who", "host", "since", "epic", "title", "ref", "sha"}} for every `<prefix><story>` the remote has."""
    claims: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    base = f"refs/remotes/{remote}/{prefix}"
    _code, refs = git(cwd, "for-each-ref", "--format=%(refname) %(objectname)", base)
    for line in refs.splitlines():
        parts = line.split(" ")
        if len(parts) != 2 or not parts[0].startswith(base):
            continue
        ref, sha = parts
        story = ref[len(base):]
        _c, log = git(cwd, "log", "--format=%B%x1e", "-n", "50", ref)
        found: typing.Dict[str, str] = {}
        for message in log.split("\x1e"):
            trailers = trailers_of(message)
            if "Factory-Claim" in trailers:
                found = trailers
        claim = (found.get("Factory-Claim") or "").split()
        story_line = (found.get("Factory-Story") or "").split(" ", 2)
        claims[story] = {"who": claim[0] if claim else "?", "host": claim[1] if len(claim) > 1 else "?",
                         "since": claim[2] if len(claim) > 2 else "?",
                         "epic": story_line[1] if len(story_line) > 1 else "",
                         "title": story_line[2] if len(story_line) > 2 else "", "ref": ref, "sha": sha}
    return claims


def write_claims(runs: str, claims: typing.Mapping[str, typing.Mapping[str, typing.Any]],
                 me: typing.Tuple[str, str]) -> None:
    path = claims_path(runs)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for story, c in sorted(claims.items()):
            own = "1" if (c["who"], c["host"]) == me else "0"
            handle.write("\t".join((story, c["who"], c["host"], c["since"], own, c["epic"], c["title"])) + "\n")


def cached_claims(runs: str) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
    """{story: {"who", "host", "since", "own", "epic", "title"}} as the last fetch saw them — read by the schedule."""
    path = claims_path(runs)
    found: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    for line in read_text(path).splitlines() if os.path.isfile(path) else []:
        parts = line.split("\t")
        if len(parts) >= 5:
            found[parts[0]] = {"who": parts[1], "host": parts[2], "since": parts[3], "own": parts[4] == "1",
                               "epic": parts[5] if len(parts) > 5 else "", "title": parts[6] if len(parts) > 6 else ""}
    return found


def story_on_ref(cwd: str, ref: str, epics_rel: str, story_id: str) -> typing.Optional[typing.Dict[str, str]]:
    """The story's front matter as `ref` has it — None where the ref has no such story."""
    _c, names = git(cwd, "ls-tree", "-r", "--name-only", ref, "--", epics_rel.rstrip("/") + "/")
    for name in names.splitlines():
        if name.endswith(f"/{story_id}/{STORY_FILE}"):
            code, text = git_blob(cwd, f"{ref}:{name}")
            if code == 0:
                split = split_front(text + "\n")
                if split:
                    front: typing.Dict[str, str] = {}
                    for line in split[0]:
                        if ":" in line and not line.startswith((" ", "\t", "-")):
                            key, value = line.split(":", 1)
                            front[key.strip()] = value.strip()
                    return front
    return None


def refresh_claims(cwd: str, runs: str, config: typing.Mapping[str, str], target: str,
                   say: typing.Callable[..., typing.Any] = print) -> int:
    """Fetch; every claim the remote has into the cache the schedule reads; a claim whose story is delivered on the
    remote main line released — by any factory that sees it, idempotent; an own published story whose delivery reached
    the remote main line loses its local worktree mark. A claim whose story the remote main line no longer has is an
    orphan: shown, released by a person."""
    remote, prefix = config["remote"], config["prefix"]
    if fetch_remote(cwd, remote)[0] != 0:
        say(f"claims: {remote} could not be fetched — the claims shown are the last ones seen")
        return 1
    claims = read_remote_claims(cwd, remote, prefix)
    main = remote_main(remote, target)
    epics_rel = os.path.relpath(place("epics"), factory_home() or cwd).replace(os.sep, "/")
    for story, c in list(claims.items()):
        front = story_on_ref(cwd, main, epics_rel, story)
        published = os.path.isfile(os.path.join(evidence_dir(runs, story), PUBLISHED))
        branch = git(cwd, "rev-parse", "--verify", "--quiet", f"refs/heads/{STORY_BRANCH}{story}")[0] == 0
        fate = ClaimRules.fate(status_of(front), present(published), present(branch))
        if fate is Fate.RELEASED:
            if git(cwd, "push", "--quiet", remote, "--delete", f"{prefix}{story}")[0] == 0:
                say(f"claims: {story} is delivered on {remote}/{target} — its claim released")
            del claims[story]
            mark = os.path.join(evidence_dir(runs, story), PUBLISHED)
            if os.path.isfile(mark):
                os.remove(mark)
        elif fate is Fate.ORPHAN:
            c["orphan"] = True
    write_claims(runs, claims, identity(cwd))
    for story, c in sorted(claims.items()):
        if c.get("orphan"):
            say(f"claims: {story} is claimed by {c['who']} ({c['host']}) since {c['since']}, and {remote}/{target} has "
                f"no such story — an orphan; `factory.sh release {story} --force` takes it away")
    return 0


def claim_story(cwd: str, runs: str, config: typing.Mapping[str, str], target: str, story_id: str, epic: str,
                title: str, say: typing.Callable[..., typing.Any] = print) -> int:
    """Claim one story: 0 claimed now or already this factory's, 3 another factory has it, 4 a person has to look —
    an id collision (the remote claim names another story under this id) or the remote refused the push for a reason
    other than the race (a branch rule). The claim commit sits on the remote main line, empty, its trailers saying who
    and which story; the local story branch starts there."""
    remote, prefix = config["remote"], config["prefix"]
    fetch_remote(cwd, remote)
    me = identity(cwd)
    claims = read_remote_claims(cwd, remote, prefix)
    local = f"refs/heads/{STORY_BRANCH}{story_id}"
    if story_id in claims:
        c = claims[story_id]
        meeting = ClaimRules.meets(worker(c["who"], c["host"]), worker(*me),
                                   ClaimedFor(EpicId(c["epic"]), ClaimTitle(c["title"])),
                                   ClaimedFor(EpicId(epic), ClaimTitle(title)))
        if meeting is Meeting.OWN:
            say(f"claim: {story_id} is this factory's since {c['since']}")
            write_claims(runs, claims, me)
            return 0
        if meeting is Meeting.COLLISION:
            say(f"claim: id collision — {remote} has {prefix}{story_id} claimed by {c['who']} for "
                f"\"{c['title']}\" ({c['epic']}), this story is \"{title}\" ({epic}). needs-human: give this story another id")
            write_claims(runs, claims, me)
            return 4
        say(f"claim: [{story_id}] claimed by {c['who']} ({c['host']}) since {c['since']} — skipped")
        write_claims(runs, claims, me)
        return 3
    main = remote_main(remote, target)
    base = main if git(cwd, "rev-parse", "--verify", "--quiet", main)[0] == 0 else "HEAD"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trailers = f"Factory-Claim: {me[0]} {me[1]} {stamp}\nFactory-Story: {story_id} {epic} {title}"
    tree = git(cwd, "rev-parse", f"{base}^{{tree}}")[1].strip()
    parent = git(cwd, "rev-parse", base)[1].strip()
    env = dict(os.environ)
    if not git(cwd, "config", "user.email")[1].strip():
        env.update(GIT_AUTHOR_NAME="dca-factory", GIT_AUTHOR_EMAIL="dca-factory@localhost",
                   GIT_COMMITTER_NAME="dca-factory", GIT_COMMITTER_EMAIL="dca-factory@localhost")
    code, sha = git(cwd, "commit-tree", tree, "-p", parent, "-m", f"claim({story_id}): {title}\n\n{trailers}", env=env)
    if code != 0:
        say(f"claim: the claim commit for {story_id} could not be made — {sha}")
        return 4
    sha = sha.strip().splitlines()[-1]
    ref = f"refs/heads/{prefix}{story_id}"
    code, out = git(cwd, "push", "--porcelain", f"--force-with-lease={ref}:", remote, f"{sha}:{ref}")
    if code != 0:
        fetch_remote(cwd, remote)
        claims = read_remote_claims(cwd, remote, prefix)
        write_claims(runs, claims, me)
        if story_id in claims:
            c = claims[story_id]
            say(f"claim: [{story_id}] claimed by {c['who']} ({c['host']}) since {c['since']} — the other factory "
                f"pushed first; skipped")
            return 3
        reason = " ".join(out.split())[:300]
        say(f"claim: {remote} refused {prefix}{story_id} — not a lost race, the remote said: {reason}. needs-human: "
            f"a branch rule of the code host? `claim_branch_prefix:` in the profile names another prefix")
        return 4
    if git(cwd, "rev-parse", "--verify", "--quiet", local)[0] != 0:
        git(cwd, "branch", f"{STORY_BRANCH}{story_id}", sha)
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, CLAIM_TRAILERS), "w", encoding="utf-8") as handle:
        handle.write(trailers + "\n")
    fetch_remote(cwd, remote)
    write_claims(runs, read_remote_claims(cwd, remote, prefix), me)
    say(f"claim: {story_id} claimed on {remote} as {prefix}{story_id}")
    return 0


def release_claim(cwd: str, runs: str, config: typing.Mapping[str, str], story_id: str, force: bool = False,
                  say: typing.Callable[..., typing.Any] = print) -> int:
    """A story given up by hand: its remote branch deleted — this factory's claim, or with `force` another's."""
    remote, prefix = config["remote"], config["prefix"]
    fetch_remote(cwd, remote)
    claims = read_remote_claims(cwd, remote, prefix)
    if story_id not in claims:
        say(f"release: {remote} has no claim on {story_id}")
        return 0
    c = claims[story_id]
    if ClaimRules.releases(worker(c["who"], c["host"]), worker(*identity(cwd)), present(force)) is Presence.ABSENT:
        say(f"release: {story_id} is claimed by {c['who']} ({c['host']}) since {c['since']} — not this factory's; "
            f"`--force` takes it away")
        return 1
    if git(cwd, "push", "--quiet", remote, "--delete", f"{prefix}{story_id}")[0] != 0:
        say(f"release: {remote} refused to delete {prefix}{story_id}")
        return 1
    with contextlib.suppress(OSError):
        journal_append(runs, story_id, "note", "release", f"by={identity(cwd)[0]}",
                       f"claim={c['who']}" + (" forced=1" if force else ""))
    fetch_remote(cwd, remote)
    write_claims(runs, read_remote_claims(cwd, remote, prefix), identity(cwd))
    say(f"release: {story_id}'s claim ({c['who']}) released" + (" — forced" if force else ""))
    return 0


def free_id(cwd: str, epics: str, config: typing.Optional[typing.Mapping[str, str]], target: str, prefix: str) -> str:
    """The next `<prefix>-<n>` nobody uses: not a local story, not a story on the remote main line, not a `Story:`
    trailer in its history (a delivered story may be gone, its id is not free again), not a remote claim."""
    used = set()
    for path in story_files(epics):
        with contextlib.suppress(GateError):
            used.add(str(read_front_matter(path)[0].get("id") or os.path.basename(story_folder(path))).strip())
    if config:
        remote = config["remote"]
        fetch_remote(cwd, remote)
        main = remote_main(remote, target)
        epics_rel = os.path.relpath(epics, cwd).replace(os.sep, "/")
        _c, names = git(cwd, "ls-tree", "-r", "--name-only", main, "--", epics_rel.rstrip("/") + "/")
        used |= {n.split("/")[-2] for n in names.splitlines() if n.endswith("/" + STORY_FILE)}
        _c, log = git(cwd, "log", "--format=%B", main)
        used |= {line.split(":", 1)[1].strip() for line in log.splitlines() if line.startswith("Story:")}
        used |= set(read_remote_claims(cwd, remote, config["prefix"]))
    return ClaimRules.next_id(IdPrefix(prefix), {StoryId(u) for u in used}).value


def worker(who: str, host: str) -> Worker:
    return Worker(f"{who} ({host})")


def present(fact: bool) -> Presence:
    return Presence.PRESENT if fact else Presence.ABSENT


def status_of(front: typing.Optional[typing.Mapping[str, typing.Any]]) -> typing.Optional[StoryStatus]:
    """The story's status on a ref, None where the ref has no such story."""
    if front is None:
        return None
    word = str(front.get("status", "")).strip().lower()
    return next((status for status in StoryStatus if status.value == word), StoryStatus.OTHER)
