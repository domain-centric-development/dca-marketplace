"""Delivery's use cases, wired to the project's files — relative to the project <cwd>, the run folder <runs>."""

from __future__ import annotations

from ..delivery.adapter.incoming.requests.settle import Settlement
from ..delivery.adapter.outgoing.files.decision_record_files import DecisionInboxFiles, DecisionRecordFiles
from ..delivery.adapter.outgoing.discovery.reports import DiscoveryReportFiles
from ..delivery.adapter.outgoing.files.epic_files import EpicFiles
from ..delivery.adapter.outgoing.files.journal_files import StoryJournalFiles
from ..delivery.adapter.outgoing.files.request_files import RequestFiles
from ..delivery.adapter.outgoing.files.status_facts import StatusFactFiles
from ..delivery.adapter.outgoing.files.story_files import StoryFiles
from ..delivery.adapter.outgoing.pipeline.stage_table import ContractStages
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
from ..delivery.application.status.show_status import ShowStatusUseCase


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
    return ShowStatusUseCase(StatusFactFiles(cwd, epics, runs), RequestFiles(cwd))


def list_decisions(cwd: str) -> ListDecisionsUseCase:
    return ListDecisionsUseCase(DecisionInboxFiles(cwd), RequestFiles(cwd), StoryFiles(cwd))
