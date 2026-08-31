"""Pyyntö- ja vastausmallit AI-suunnittelupajalle."""

from pydantic import BaseModel
from config import DEFAULT_EDITOR_MODEL


class Msg(BaseModel):
    role: str            # "user" | "assistant"
    name: str            # "Käyttäjä" tai osallistujan nimi
    model: str | None = None  # mallin id tai osallistuja-avain
    content: str


class Participant(BaseModel):
    id: str
    name: str
    role: str
    model: str
    system_prompt: str | None = None


class RespondRequest(BaseModel):
    topic_id: str | None = "default"
    conversation: list[Msg] = []
    participants: list[Participant] | None = None
    document: str = ""
    auto_update_doc: bool = True
    editor_model: str | None = None
    max_history: int | None = None


class DocumentRequest(BaseModel):
    topic_id: str | None = "default"
    conversation: list[Msg] = []
    document: str = ""
    instruction: str = ""
    editor_model: str = DEFAULT_EDITOR_MODEL


class TopicSaveRequest(BaseModel):
    id: str
    title: str
    conversation: list[Msg] = []
    document: str = ""
    summary: str = ""
    stats: dict = {}


class SaveRequest(BaseModel):
    filename: str
    content: str
