"""Delivery's use cases, wired to the project's files — relative to the project <cwd>, the run folder <runs>."""

from __future__ import annotations

from ..delivery.adapter.incoming.requests.settle import Settlement
from ..delivery.adapter.outgoing.claims.story_claims import RemoteStoryClaims
from ..delivery.adapter.outgoing.files.acceptance_files import AcceptanceFiles
from ..delivery.adapter.outgoing.files.created_files import CreatedFiles
from ..delivery.adapter.outgoing.files.description_files import DescriptionFiles
from ..delivery.adapter.outgoing.files.detail_files import DetailFactFiles
from ..delivery.adapter.outgoing.files.decision_record_files import DecisionInboxFiles, DecisionRecordFiles
from ..delivery.adapter.outgoing.discovery.reports import DiscoveryReportFiles
from ..delivery.adapter.outgoing.files.epic_files import EpicFiles
from ..delivery.adapter.outgoing.files.journal_files import StoryJournalFiles
from ..delivery.adapter.outgoing.files.owned_files import OwnedChangeFiles
from ..delivery.adapter.outgoing.files.project_files import ProjectFiles
from ..delivery.adapter.outgoing.files.request_files import RequestFiles
from ..delivery.adapter.outgoing.files.status_facts import StatusFactFiles
from ..delivery.adapter.outgoing.files.story_files import StoryFiles
from ..delivery.adapter.outgoing.files.story_runs import StoryRunFiles
from ..delivery.adapter.outgoing.spec.story_spec_files import StorySpecFiles
from ..delivery.adapter.outgoing.spec.delivered_spec_files import DeliveredSpecFiles
from ..delivery.adapter.outgoing.spec.spec_delta_files import SpecDeltaFiles
from ..delivery.adapter.outgoing.git.published_branches import PublishedBranchFiles
from ..delivery.application.delivery.check_spec import CheckSpecUseCase
from ..delivery.application.delivery.show_spec_delta import ShowSpecDeltaUseCase
from ..delivery.application.delivery.take_back_delivery import TakeBackDeliveryUseCase
from ..delivery.adapter.outgoing.pipeline.stage_table import ContractStages
from ..delivery.application.backlog.backfill_created import BackfillCreatedUseCase
from ..delivery.application.backlog.release_stories import ReleaseStoriesUseCase
from ..delivery.application.cost.book_request_cost import BookRequestCostUseCase
from ..delivery.application.decisions.accept_delivery import AcceptDeliveryUseCase
from ..delivery.application.decisions.answer_question import AnswerQuestionUseCase
from ..delivery.application.decisions.list_decisions import ListDecisionsUseCase
from ..delivery.application.requests.check_request import CheckRequestUseCase
from ..delivery.application.requests.list_requests import ListRequestsUseCase
from ..delivery.application.requests.pending_requests import PendingRequestsUseCase
from ..delivery.application.requests.retry_request import RetryRequestUseCase
from ..delivery.application.requests.take_back_request import TakeBackRequestUseCase
from ..delivery.application.requests.write_request import WriteRequestUseCase
from ..delivery.application.shared.request_check import RequestCheck
from ..delivery.application.status.show_epic import ShowEpicUseCase
from ..delivery.application.delivery.claim_story import ClaimStoryUseCase
from ..delivery.application.delivery.confirm_owned import ConfirmOwnedUseCase
from ..delivery.application.delivery.deliver_by_hand import DeliverByHandUseCase
from ..delivery.application.delivery.prove_delivery import ProveDeliveryUseCase
from ..delivery.application.delivery.reopen_story import ReopenStoryUseCase
from ..delivery.application.status.show_help import ShowHelpUseCase
from ..delivery.application.status.show_status import ShowStatusUseCase
from ..delivery.application.status.show_story import ShowStoryUseCase


def request_check(cwd: str) -> RequestCheck:
    return RequestCheck(StoryFiles(cwd), EpicFiles(cwd), DecisionRecordFiles(cwd), DiscoveryReportFiles(cwd),
                        ContractStages())


def write_request(cwd: str) -> WriteRequestUseCase:
    return WriteRequestUseCase(request_check(cwd), RequestFiles(cwd))


def check_request(cwd: str) -> CheckRequestUseCase:
    return CheckRequestUseCase(request_check(cwd), RequestFiles(cwd))


def take_back_request(cwd: str) -> TakeBackRequestUseCase:
    return TakeBackRequestUseCase(RequestFiles(cwd))


def retry_request(cwd: str) -> RetryRequestUseCase:
    return RetryRequestUseCase(RequestFiles(cwd))


def list_requests(cwd: str) -> ListRequestsUseCase:
    return ListRequestsUseCase(RequestFiles(cwd))


def pending_requests(cwd: str) -> PendingRequestsUseCase:
    return PendingRequestsUseCase(RequestFiles(cwd))


def settlement(cwd: str, runs: str) -> Settlement:
    stories, records = StoryFiles(cwd), DecisionRecordFiles(cwd)
    return Settlement(AcceptDeliveryUseCase(stories, records), AnswerQuestionUseCase(records),
                      ReleaseStoriesUseCase(stories, records, StoryJournalFiles(cwd, runs)))


def book_request_cost(cwd: str, runs: str) -> BookRequestCostUseCase:
    return BookRequestCostUseCase(StoryJournalFiles(cwd, runs))


def show_status(cwd: str, epics: str, runs: str) -> ShowStatusUseCase:
    return ShowStatusUseCase(StatusFactFiles(cwd, epics, runs), RequestFiles(cwd), DescriptionFiles.of_project(cwd))


def list_decisions(cwd: str) -> ListDecisionsUseCase:
    return ListDecisionsUseCase(DecisionInboxFiles(cwd), RequestFiles(cwd), StoryFiles(cwd))


def show_story(cwd: str, epics: str, runs: str) -> ShowStoryUseCase:
    return ShowStoryUseCase(show_status(cwd, epics, runs), StatusFactFiles(cwd, epics, runs), DetailFactFiles(epics, runs),
                            pending_requests(cwd))


def show_epic(cwd: str, epics: str, runs: str) -> ShowEpicUseCase:
    return ShowEpicUseCase(show_status(cwd, epics, runs), DetailFactFiles(epics, runs))


def show_help(cwd: str, epics: str, runs: str) -> ShowHelpUseCase:
    return ShowHelpUseCase(show_status(cwd, epics, runs), ProjectFiles(cwd, epics, runs), StatusFactFiles(cwd, epics, runs))


def reopen_story(cwd: str, epics: str, runs: str) -> ReopenStoryUseCase:
    return ReopenStoryUseCase(StoryFiles(cwd, epics), AcceptanceFiles(cwd, epics), StoryRunFiles(cwd, epics, runs))


def prove_delivery(cwd: str, epics: str, runs: str) -> ProveDeliveryUseCase:
    return ProveDeliveryUseCase(StoryFiles(cwd, epics), StoryRunFiles(cwd, epics, runs))


def deliver_by_hand(cwd: str, epics: str, runs: str) -> DeliverByHandUseCase:
    return DeliverByHandUseCase(StoryFiles(cwd, epics), RemoteStoryClaims(cwd, runs), StorySpecFiles(epics),
                                StoryJournalFiles(cwd, runs))


def confirm_owned(cwd: str, runs: str) -> ConfirmOwnedUseCase:
    return ConfirmOwnedUseCase(OwnedChangeFiles(runs), StoryJournalFiles(cwd, runs))


def claim_story(cwd: str, epics: str, runs: str) -> ClaimStoryUseCase:
    return ClaimStoryUseCase(RemoteStoryClaims(cwd, runs, epics), StoryJournalFiles(cwd, runs))


def backfill_created(cwd: str, epics: str) -> BackfillCreatedUseCase:
    return BackfillCreatedUseCase(CreatedFiles(cwd, epics))


def check_spec(runs: str, epics: str) -> CheckSpecUseCase:
    return CheckSpecUseCase(DeliveredSpecFiles(runs, epics))


def show_spec_delta(runs: str, epics: str) -> ShowSpecDeltaUseCase:
    return ShowSpecDeltaUseCase(SpecDeltaFiles(runs, epics))


def take_back_delivery(cwd: str, runs: str, epics: str) -> TakeBackDeliveryUseCase:
    return TakeBackDeliveryUseCase(PublishedBranchFiles(cwd, runs, epics))
