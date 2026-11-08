"""The delivery feature's commands of the cli: a story taken back, delivered by hand, proven, claimed, its claims and the skeletons of its hand-overs."""

from __future__ import annotations

import time
import typing
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    shown)
from ....application.delivery.claim_story import ClaimStoryCommand
from ....application.delivery.confirm_owned import ConfirmOwnedCommand, NothingToConfirm
from ....application.shared.story_claims import Claim
from ....application.delivery.deliver_by_hand import ChangesWhatHolds, ClaimedElsewhere, DeliverByHandCommand
from ....application.delivery.prove_delivery import ProveDeliveryCommand
from ....application.delivery.reopen_story import CheckoutHeld, NewWish, NoCorrection, NotCited, ReopenStoryCommand
from ....domain.model.moment import Moment
from ....domain.model.person import Person
from ....domain.model.story import AlreadyDelivered, NotDelivered, NothingToDeliver, NothingToProve, StoryId
from ....application.delivery.take_back_delivery import TakeBackDeliveryCommand
from ....application.delivery.write_skeleton import Skeleton, WriteSkeletonCommand
from ....application.delivery.refresh_claims import RefreshClaimsCommand
from ....application.delivery.release_story_claim import ReleaseStoryClaimCommand
from ....domain.model.story import StoryId
from . import root
from .common import story_command


def owned_confirm(runs: str, story_id: str, cwd: str = ".") -> int:
    """The person's word that the story and its answers are as they want them after a stage changed them
    (`ConfirmOwnedUseCase`): the mark goes, what changed is journaled, and the story runs on from its files."""
    result = root.wiring.confirm_owned(cwd, runs).execute(ConfirmOwnedCommand(StoryId(story_id)))
    if isinstance(result, NothingToConfirm):
        print(f"owned: nothing to confirm for {story_id} — no stage changed its story or an answer")
    else:
        print(f"owned: {story_id} — {', '.join(result.parts)} confirmed as the person's; the story runs on")
    return 0


def reopen(cwd: str, runs: str, epics: str, story_id: str) -> int:
    """Take a delivered story back for a correction a human gave on looking at it (`ReopenStoryUseCase`)."""
    try:
        result = story_command(lambda: root.wiring.reopen_story(cwd, epics, runs).execute(
            ReopenStoryCommand(StoryId(story_id), Moment(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))))
    except NotDelivered:
        print(f"reopen: {story_id} is not delivered — a correction before delivery goes into the story, "
              f"and the schedule runs it from plan")
        return 1
    if isinstance(result, NoCorrection):
        print(f"reopen: {story_id} has no answered correction — /factory-decisions records the human's "
              f"correction as an acceptance record first")
    elif isinstance(result, CheckoutHeld):
        print(f"reopen: {', '.join(h.value for h in result.holders)} holds the checkout with unfinished code — one "
              f"story at a time; reopen {story_id} once it is delivered")
    elif isinstance(result, NotCited):
        rid = result.record.value
        print(f"reopen: the story does not cite {rid} — write the correction into it first (criteria and "
              f"an `answered:` line naming {rid})")
    elif isinstance(result, NewWish):
        print(f"reopen: after its acceptance the correction changes {', '.join(result.changed)} — that is a new "
              f"wish: a new story with `## Changed expectations`, not this one reopened")
    else:
        print(f"reopen: {story_id} taken back for {result.record.value} — it runs again from plan; the delivered pass "
              f"is kept as {shown(result.kept) if result.kept else 'nothing (no run folder)'}, and the story no "
              f"longer says delivered")
        return 0
    return 1


def deliver_by_hand(cwd: str, runs: str, epics: str, story_id: str, who: typing.Optional[str], force: bool = False) -> int:
    """A story a person built: `status: delivered`, `delivered:` (UTC), `delivered_by: hand:<who>`
    (`DeliverByHandUseCase`). Works where the factory never ran; `--prove` checks it later."""
    who = " ".join(str(who or "").split())
    if not who:
        print("deliver-by-hand: `--by <who>` names the person who delivers — the line is their claim")
        return 1
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        result = story_command(lambda: root.wiring.deliver_by_hand(cwd, epics, runs).execute(
            DeliverByHandCommand(StoryId(story_id), Person(who), Moment(stamp), force)))
    except AlreadyDelivered as error:
        print(f"deliver-by-hand: {story_id} is delivered already ({error.by.value or 'before delivered_by'}) — "
              f"a change of its behaviour is a new story with `## Changed expectations`")
        return 1
    except NothingToDeliver:
        print(f"deliver-by-hand: {story_id} is superseded — nothing to deliver")
        return 1
    if isinstance(result, ClaimedElsewhere):
        held = result.claim
        print(f"deliver-by-hand: {story_id} is claimed by {held.who} ({held.host}) since {held.since} — "
              f"another factory builds it; `--force` delivers it anyway")
        return 1
    if isinstance(result, ChangesWhatHolds):
        print(f"deliver-by-hand: {story_id} changes what holds ({', '.join(result.change.keys)} in "
              f"{shown(result.change.where)}) — the delta of a change is planned: `factory-cli.py --prove {story_id}` "
              f"once it is delivered, or run it through the factory")
        return 1
    if result.unproven.keys:
        print(f"deliver-by-hand: {len(result.unproven.keys)} criterion(s) into {shown(result.unproven.where)}, without "
              f"a test line — unproven until `--prove`")
    print(f"deliver-by-hand: {shown(result.where)} carries `status: delivered`, `delivered: {stamp}`, "
          f"`delivered_by: hand:{who}` — delivered, claimed. Commit it with the trailer `Story: {story_id}`; "
          f"`factory-cli.py --prove {story_id}` turns the claim into proof.")
    return 0


#: A claim's exit codes, as the runner reads them.
CLAIM_EXIT = {Claim.OWN: 0, Claim.NO_REMOTE: 0, Claim.ELSEWHERE: 3, Claim.NEEDS_PERSON: 4}


def claim_command(cwd: str, runs: str, epics: str, story_id: str) -> int:
    """`--claim-story`: claim one story on the remote (WP-93, `ClaimStoryUseCase`). 0 claimed or own, 3 another
    factory has it, 4 needs a person; 0 and nothing pushed where the profile names no `claim_remote:`."""
    outcome = root.wiring.claim_story(cwd, epics, runs).execute(ClaimStoryCommand(StoryId(story_id)))
    for line in outcome.said:
        print(line)
    return CLAIM_EXIT[outcome.claim]


def undeliver_branch(cwd: str, runs: str, epics: str, story_id: str) -> int:
    """WP-93 F: a published branch whose merge request lost the race goes back to before its delivery
    (`TakeBackDeliveryUseCase`), so the integrate step merges the remote main line and the delivering function merges
    again under the new rules."""
    taken = root.wiring.take_back_delivery(cwd, runs, epics).execute(TakeBackDeliveryCommand(story_id))
    if taken is None:
        print(f"integrate: {story_id} has no published branch in this checkout")
        return 1
    print(f"integrate: {story_id}'s delivery taken back on its branch ({len(taken.spec_files)} spec file(s) as "
          f"{taken.main} has them) — the integrate step merges {taken.main} and delivers it again")
    return 0


def prove(cwd: str, runs: str, epics: str, story_id: str) -> int:
    """A claimed delivery checked through the adopt path (`ProveDeliveryUseCase`): the story becomes
    `status: adopted`, its claim kept as one line of the evidence; the adopt gate then proves it and delivers it."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        result = story_command(lambda: root.wiring.prove_delivery(cwd, epics, runs).execute(
            ProveDeliveryCommand(StoryId(story_id), Moment(stamp))))
    except NotDelivered:
        print(f"prove: {story_id} is not delivered — `--prove` checks a claimed delivery; an open story runs as it is")
        return 1
    except NothingToProve:
        print(f"prove: {story_id} is delivered by the gate with its pass on record — nothing to prove")
        return 1
    if isinstance(result, CheckoutHeld):
        print(f"prove: {', '.join(h.value for h in result.holders)} holds the checkout with unfinished code — one "
              f"story at a time; prove {story_id} once it is delivered")
        return 1
    by = result.claim.by.value or "unknown"
    print(f"prove: {story_id} is `status: adopted` — the adopt path checks it (`factory.sh run --story {story_id}`); "
          f"the claim ({by}) is kept in {shown(result.claim_kept)}"
          + (f", the earlier pass as {shown(result.kept)}" if result.kept else ""))
    return 0


def skeleton(cwd: str, runs: str, kind: Skeleton, *names: str) -> int:
    """The skeleton of a hand-over written for a stage to fill."""
    return root.wiring.write_skeleton(cwd, runs).execute(WriteSkeletonCommand(kind, *names))


def refresh_claims(cwd: str, epics: str, runs: str) -> int:
    return root.wiring.refresh_claims(cwd, epics, runs).execute(RefreshClaimsCommand())


def release_claim(cwd: str, epics: str, runs: str, story: str, force: bool) -> int:
    return root.wiring.release_story_claim(cwd, epics, runs).execute(ReleaseStoryClaimCommand(StoryId(story), force))
