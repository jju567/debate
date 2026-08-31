"""Reititys ja päätepisteet aiheille (Topics) ja dokumenttikirjastolle (Library).
"""

import re
import json
import datetime
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

from library import list_library_documents, save_library_document, read_library_document, delete_library_document
from background_jobs import list_background_jobs, get_job_status

router = APIRouter()
DATA_DIR = Path(__file__).parent / "data"


class LibraryUploadRequest(BaseModel):
    filename: str
    content: str


class TopicSaveRequest(BaseModel):
    id: str
    title: str
    conversation: list = []
    document: str = ""
    summary: str = ""
    stats: dict = {}


def get_topics_dir() -> Path:
    topics_dir = DATA_DIR / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    return topics_dir


# ---------- Dokumenttikirjasto ----------

@router.get("/api/library")
async def get_library():
    """Hae kaikki kirjastossa olevat dokumentit ja tiivistelmät."""
    return {"documents": list_library_documents()}


@router.post("/api/library/upload")
async def upload_library_doc(req: LibraryUploadRequest):
    """Tallenna uusi viitetiedosto kirjastoon."""
    res = save_library_document(req.filename, req.content)
    return res


@router.get("/api/library/{doc_id}")
async def get_library_doc(doc_id: str):
    """Lue tietyn viitetiedoston sisältö."""
    return read_library_document(doc_id)


@router.delete("/api/library/{doc_id}")
async def remove_library_doc(doc_id: str):
    """Poista viitetiedosto kirjastosta."""
    ok = delete_library_document(doc_id)
    return {"ok": ok}


# ---------- Aiheet (Topics) ----------

@router.get("/api/topics")
async def list_topics():
    """Listaa kaikki tallennetut aiheet ja niiden metatiedot."""
    td = get_topics_dir()
    topics = []
    for p in td.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                topics.append({
                    "id": data.get("id", p.stem),
                    "title": data.get("title", p.stem),
                    "summary": data.get("summary", ""),
                    "updated_at": data.get("updated_at", ""),
                    "msg_count": len(data.get("conversation", [])),
                })
        except Exception:
            continue
    topics.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"topics": topics}


@router.get("/api/topics/{topic_id}")
async def get_topic(topic_id: str):
    """Hae tietyn aiheen koko tila."""
    safe_id = re.sub(r"[^A-Za-z0-9_.\- ]", "_", topic_id).strip()
    path = get_topics_dir() / f"{safe_id}.json"
    if not path.exists():
        return {"error": "Aihetta ei löydy"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/api/topics/save")
async def save_topic(req: TopicSaveRequest):
    """Tallenna aihe data/topics -kansioon."""
    td = get_topics_dir()
    safe_id = re.sub(r"[^A-Za-z0-9_.\- ]", "_", req.id).strip() or "aihe_1"
    path = td / f"{safe_id}.json"
    
    summary = req.summary
    if not summary and req.conversation:
        last_msgs = [m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "") for m in req.conversation]
        summary = (last_msgs[-1][:120] + "...") if last_msgs else req.title

    topic_data = {
        "id": safe_id,
        "title": req.title.strip() or safe_id,
        "summary": summary,
        "conversation": req.conversation,
        "document": req.document,
        "stats": req.stats,
        "updated_at": datetime.datetime.now().isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(topic_data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "topic": topic_data}


# ---------- Taustatyöt (Background Jobs) ----------

@router.get("/api/jobs")
async def get_jobs():
    """Listaa kaikki taustalaskentatyöt."""
    return {"jobs": list_background_jobs()}


@router.get("/api/jobs/{job_id}")
async def get_job_info(job_id: str):
    """Hae yksittäisen taustalaskennan tila ja tuoreimmat lokit."""
    return get_job_status(job_id)
