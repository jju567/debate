"""Dokumenttikirjasto ja tilapäisten liitetiedostojen hallinta.

Mahdollistaa dokumenttien tallentamisen ja niiden hyödyntämisen viitteinä
(on-demand / summarisoituna) ilman pysyvää keskustelukontekstin paisuttamista.
"""

import re
import shutil
from pathlib import Path
from pydantic import BaseModel

LIBRARY_DIR = Path(__file__).parent / "data" / "library"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


class LibraryDoc(BaseModel):
    id: str
    filename: str
    size: int
    char_count: int
    summary: str


def list_library_documents() -> list[dict]:
    """Listaa kaikki kirjastossa olevat dokumentit."""
    docs = []
    for p in sorted(LIBRARY_DIR.glob("*")):
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                # Luodaan nopea ensimmäisen 200 merkin tiivistelmä
                preview = text.strip()[:180].replace("\n", " ") + "..." if len(text) > 180 else text.strip()
                docs.append({
                    "id": p.name,
                    "filename": p.name,
                    "size": p.stat().st_size,
                    "char_count": len(text),
                    "summary": preview
                })
            except Exception:
                continue
    return docs


def save_library_document(filename: str, content: str) -> dict:
    """Tallenna uusi dokumentti kirjastoon."""
    safe_name = re.sub(r"[^A-Za-z0-9_.\- ]", "_", filename).strip() or "tiedosto.txt"
    path = LIBRARY_DIR / safe_name
    path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "id": safe_name,
        "filename": safe_name,
        "size": path.stat().st_size,
        "char_count": len(content),
        "summary": content[:180].replace("\n", " ") + "..."
    }


def read_library_document(doc_id: str, max_chars: int = 4000) -> dict:
    """Lue tietty dokumentti kirjastosta (rajattu maksimipituus)."""
    safe_id = re.sub(r"[^A-Za-z0-9_.\- ]", "_", doc_id).strip()
    path = LIBRARY_DIR / safe_id
    if not path.exists() or not path.is_file():
        return {"success": False, "error": f"Dokumenttia '{doc_id}' ei löydy kirjastosta."}
    
    text = path.read_text(encoding="utf-8", errors="replace")
    truncated = text[:max_chars]
    return {
        "success": True,
        "id": safe_id,
        "content": truncated,
        "is_truncated": len(text) > max_chars,
        "total_chars": len(text)
    }


def delete_library_document(doc_id: str) -> bool:
    """Poista dokumentti kirjastosta."""
    safe_id = re.sub(r"[^A-Za-z0-9_.\- ]", "_", doc_id).strip()
    path = LIBRARY_DIR / safe_id
    if path.exists() and path.is_file():
        path.unlink()
        return True
    return False
