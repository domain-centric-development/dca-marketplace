"""Delivery's use cases, wired to the project's files — relative to the project <cwd>, the run folder <runs>."""

from __future__ import annotations

from ..delivery.adapter.incoming.requests.settle import Settlement
from ..delivery.adapter.outgoing.discovery.discovery_list_files import DiscoveryListFiles
from ..delivery.adapter.outgoing.process.factory_process_files import FactoryProcessFiles
from ..delivery.adapter.outgoing.tools.runner_table_files import RunnerTableFiles
from ..delivery.adapter.outgoing.tools.tool_binary_files import ToolBinaryFiles
from ..delivery.adapter.outgoing.claims.checkout_files import CheckoutFiles
from ..delivery.adapter.outgoing.files.project_upkeep_files import ProjectUpkeepFiles
from ..delivery.adapter.outgoing.files.hand_over_skeleton_files import HandOverSkeletonFiles
from ..delivery.adapter.outgoing.files.session_mark_files import SessionMarkFiles
from ..delivery.adapter.outgoing.claims.story_claims import RemoteStoryClaims
from ..delivery.adapter.outgoing.files.stage_output_files import StageOutputFiles
from ..delivery.adapter.outgoing.files.usage_ledger_files import UsageLedgerFiles
from ..delivery.adapter.outgoing.files.refusal_files import GateRefusalFiles
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
from .schedule import schedule_data
from ..delivery.adapter.outgoing.files.story_files import StoryFiles
from ..delivery.adapter.outgoing.files.story_runs import StoryRunFiles
from ..delivery.adapter.outgoing.spec.story_spec_files import StorySpecFiles
from ..delivery.adapter.outgoing.spec.delivered_spec_files import DeliveredSpecFiles
from ..delivery.adapter.outgoing.spec.spec_delta_files import SpecDeltaFiles
from ..delivery.adapter.outgoing.git.published_branches import PublishedBranchFiles
from ..delivery.application.status.show_discovery import ShowDiscoveryUseCase
from ..delivery.application.lifecycle.show_running_page import ShowRunningPageUseCase
from ..delivery.application.lifecycle.show_worker import ShowWorkerUseCase
from ..delivery.application.lifecycle.start_factory import StartFactoryUseCase
from ..delivery.application.lifecycle.start_page import StartPageUseCase
from ..delivery.application.lifecycle.stop_factory import StopFactoryUseCase
from ..delivery.application.upkeep.let_journals_into_git import LetJournalsIntoGitUseCase
from ..delivery.application.upkeep.migrate_layout import MigrateLayoutUseCase
from ..delivery.application.delivery.next_free_story_id import NextFreeStoryIdUseCase
from ..delivery.application.delivery.refresh_claims import RefreshClaimsUseCase
from ..delivery.application.delivery.release_story_claim import ReleaseStoryClaimUseCase
from ..delivery.application.delivery.show_stage_table import ShowStageTableUseCase
from ..delivery.application.cost.read_tool_usage import ReadToolUsageUseCase
from ..delivery.application.delivery.probe_tool import ProbeToolUseCase
from ..delivery.application.delivery.show_hand_over_contract import ShowHandOverContractUseCase
from ..delivery.application.delivery.write_skeleton import WriteSkeletonUseCase
from ..delivery.application.delivery.show_story_kind import ShowStoryKindUseCase
from ..delivery.application.session.open_work_window import OpenWorkWindowUseCase
from ..delivery.application.session.close_work_window import CloseWorkWindowUseCase
from ..delivery.application.session.start_session_stage import StartSessionStageUseCase
from ..delivery.application.session.end_session_stage import EndSessionStageUseCase
from ..delivery.application.session.append_journal import AppendJournalUseCase
from ..delivery.application.checkout.take_checkout import TakeCheckoutUseCase
from ..delivery.application.checkout.give_checkout_back import GiveCheckoutBackUseCase
from ..delivery.application.checkout.mark_listening import MarkListeningUseCase
from ..delivery.application.status.list_findings import ListFindingsUseCase
from ..delivery.application.status.follow_output import FollowOutputUseCase
from ..delivery.application.status.show_stage_outputs import ShowStageOutputsUseCase
from ..delivery.application.cost.show_spent import ShowSpentUseCase
from ..delivery.application.status.show_journal_story import ShowJournalStoryUseCase
from ..delivery.application.status.show_refusals import ShowRefusalsUseCase
from ..delivery.application.run.resolve_run_argument import ResolveRunArgumentUseCase
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


def status_facts(cwd: str, epics: str, runs: str) -> StatusFactFiles:
    return StatusFactFiles(cwd, epics, runs, lambda: schedule_data(cwd, epics, runs))


def show_status(cwd: str, epics: str, runs: str) -> ShowStatusUseCase:
    return ShowStatusUseCase(status_facts(cwd, epics, runs), RequestFiles(cwd), DescriptionFiles.of_project(cwd))


def list_decisions(cwd: str) -> ListDecisionsUseCase:
    return ListDecisionsUseCase(DecisionInboxFiles(cwd), RequestFiles(cwd), StoryFiles(cwd))


def show_story(cwd: str, epics: str, runs: str) -> ShowStoryUseCase:
    return ShowStoryUseCase(show_status(cwd, epics, runs), status_facts(cwd, epics, runs), DetailFactFiles(epics, runs),
                            pending_requests(cwd))


def show_epic(cwd: str, epics: str, runs: str) -> ShowEpicUseCase:
    return ShowEpicUseCase(show_status(cwd, epics, runs), DetailFactFiles(epics, runs))


def show_help(cwd: str, epics: str, runs: str) -> ShowHelpUseCase:
    return ShowHelpUseCase(show_status(cwd, epics, runs), ProjectFiles(cwd, epics, runs), status_facts(cwd, epics, runs))


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


def resolve_run_argument(cwd: str) -> ResolveRunArgumentUseCase:
    return ResolveRunArgumentUseCase(StoryFiles(cwd))


def show_refusals(runs: str) -> ShowRefusalsUseCase:
    return ShowRefusalsUseCase(GateRefusalFiles(runs))


def show_spent(runs: str) -> ShowSpentUseCase:
    return ShowSpentUseCase(UsageLedgerFiles(runs))


def show_journal_story(cwd: str, epics: str, runs: str) -> ShowJournalStoryUseCase:
    return ShowJournalStoryUseCase(status_facts(cwd, epics, runs))


def show_stage_outputs(runs: str) -> ShowStageOutputsUseCase:
    return ShowStageOutputsUseCase(StageOutputFiles(runs))


def follow_output(runs: str) -> FollowOutputUseCase:
    return FollowOutputUseCase(StageOutputFiles(runs))


def list_findings(cwd: str, epics: str, runs: str) -> ListFindingsUseCase:
    return ListFindingsUseCase(status_facts(cwd, epics, runs))


def open_work_window(cwd: str, runs: str) -> OpenWorkWindowUseCase:
    return OpenWorkWindowUseCase(SessionMarkFiles(cwd, runs))



def close_work_window(cwd: str, runs: str) -> CloseWorkWindowUseCase:
    return CloseWorkWindowUseCase(SessionMarkFiles(cwd, runs))



def start_session_stage(cwd: str, runs: str) -> StartSessionStageUseCase:
    return StartSessionStageUseCase(SessionMarkFiles(cwd, runs))



def end_session_stage(cwd: str, runs: str) -> EndSessionStageUseCase:
    return EndSessionStageUseCase(SessionMarkFiles(cwd, runs))



def append_journal(cwd: str, runs: str) -> AppendJournalUseCase:
    return AppendJournalUseCase(SessionMarkFiles(cwd, runs))



def take_checkout(cwd: str, runs: str) -> TakeCheckoutUseCase:
    return TakeCheckoutUseCase(CheckoutFiles(cwd, runs))



def give_checkout_back(cwd: str, runs: str) -> GiveCheckoutBackUseCase:
    return GiveCheckoutBackUseCase(CheckoutFiles(cwd, runs))



def mark_listening(cwd: str, runs: str) -> MarkListeningUseCase:
    return MarkListeningUseCase(CheckoutFiles(cwd, runs))


def show_story_kind(cwd: str) -> ShowStoryKindUseCase:
    return ShowStoryKindUseCase(StoryFiles(cwd))


def write_skeleton(cwd: str, runs: str) -> WriteSkeletonUseCase:
    return WriteSkeletonUseCase(HandOverSkeletonFiles(cwd, runs))


def show_hand_over_contract(cwd: str, runs: str) -> ShowHandOverContractUseCase:
    return ShowHandOverContractUseCase(HandOverSkeletonFiles(cwd, runs))


def probe_tool() -> ProbeToolUseCase:
    return ProbeToolUseCase(ToolBinaryFiles())


def read_tool_usage() -> ReadToolUsageUseCase:
    return ReadToolUsageUseCase(ToolBinaryFiles())


def show_stage_table() -> ShowStageTableUseCase:
    return ShowStageTableUseCase(RunnerTableFiles())


def release_story_claim(cwd: str, epics: str, runs: str) -> ReleaseStoryClaimUseCase:
    return ReleaseStoryClaimUseCase(RemoteStoryClaims(cwd, runs, epics))


def refresh_claims(cwd: str, epics: str, runs: str) -> RefreshClaimsUseCase:
    return RefreshClaimsUseCase(RemoteStoryClaims(cwd, runs, epics))


def next_free_story_id(cwd: str, epics: str, runs: str) -> NextFreeStoryIdUseCase:
    return NextFreeStoryIdUseCase(RemoteStoryClaims(cwd, runs, epics))


def migrate_layout(cwd: str) -> MigrateLayoutUseCase:
    return MigrateLayoutUseCase(ProjectUpkeepFiles(cwd))


def let_journals_into_git(cwd: str) -> LetJournalsIntoGitUseCase:
    return LetJournalsIntoGitUseCase(ProjectUpkeepFiles(cwd))


def start_factory() -> StartFactoryUseCase:
    return StartFactoryUseCase(FactoryProcessFiles())


def stop_factory() -> StopFactoryUseCase:
    return StopFactoryUseCase(FactoryProcessFiles())


def start_page() -> StartPageUseCase:
    return StartPageUseCase(FactoryProcessFiles())


def show_worker() -> ShowWorkerUseCase:
    return ShowWorkerUseCase(FactoryProcessFiles())


def show_running_page() -> ShowRunningPageUseCase:
    return ShowRunningPageUseCase(FactoryProcessFiles())


def show_discovery(cwd: str) -> ShowDiscoveryUseCase:
    return ShowDiscoveryUseCase(DiscoveryListFiles(cwd), RequestFiles(cwd), StoryFiles(cwd))
