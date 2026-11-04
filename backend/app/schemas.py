from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MeetingCreate(Input):
    title: str = Field(min_length=3, max_length=160)
    meeting_date: date
    participants: list[str] = Field(min_length=1, max_length=30)
    reviewer_id: int = Field(gt=0)
    transcript: str = Field(default="", max_length=60000)
    external_processing_allowed: bool = False

    @field_validator("participants")
    @classmethod
    def participant_names(cls, names):
        result = list(dict.fromkeys(name.strip() for name in names))
        if any(not name or len(name) > 100 for name in result):
            raise ValueError("Teilnehmende benötigen Namen mit 1 bis 100 Zeichen.")
        return result


class Fact(Input):
    text: str = Field(min_length=3, max_length=1200)
    source_ids: list[int] = Field(min_length=1, max_length=5)
    quote: str = Field(min_length=5, max_length=1500)


class Task(Fact):
    owner: str | None = Field(max_length=100)
    due_text: str | None = Field(max_length=100)


class Report(Input):
    summary: list[Fact] = Field(min_length=1, max_length=12)
    decisions: list[Fact] = Field(max_length=20)
    tasks: list[Task] = Field(max_length=30)
    open_questions: list[Fact] = Field(max_length=20)


class VersionInput(Input):
    expected_revision: int = Field(ge=1)


class DraftEdit(VersionInput):
    report: Report


class Approval(VersionInput):
    acknowledge_warnings: bool = False


class ChangesRequested(VersionInput):
    note: str = Field(min_length=5, max_length=1000)


class SourceEdit(Input):
    expected_source_version: int = Field(ge=1)
    transcript: str = Field(min_length=30, max_length=60000)
    external_processing_allowed: bool


class TaskUpdate(Input):
    revision: int = Field(ge=1)
    status: Literal["open", "in_progress", "done"]


class Login(Input):
    account_id: int


class JobInput(Input):
    job_id: str = Field(min_length=36, max_length=36)


class StepInput(JobInput):
    claim: str = Field(min_length=64, max_length=64)


class FailureInput(JobInput):
    claim: str | None = Field(default=None, min_length=64, max_length=64)
