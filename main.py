"""AI-suunnittelupaja — FastAPI-backend.

Kaksi streamaavaa päätepistettä:
  - /api/respond   : valitut mallit vastaavat keskusteluun vuorotellen (paneeli)
  - /api/document  : editori-malli laatii/päivittää suunnitteludokumentin

Tila (keskustelu + dokumentti) elää selaimessa; backend on tilaton ja saa
tarvittavan kontekstin joka pyynnössä.
"""

import json
import os
import re
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import load_agents_config, DEFAULT_EDITOR_MODEL, MAX_HISTORY_MESSAGES
from llm import stream_chat, LLMError

load_dotenv()

app = FastAPI(title="AI Design Studio")

DOCS_DIR = Path(__file__).parent / "documents"
STATIC_DIR = Path(__file__).parent / "static"


# ---------- Pyyntömallit ----------

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
    conversation: list[Msg] = []
    participants: list[Participant] | None = None
    document: str = ""
    auto_update_doc: bool = True
    editor_model: str | None = None
    max_history: int | None = None



class DocumentRequest(BaseModel):
    conversation: list[Msg] = []
    document: str = ""
    instruction: str = ""
    editor_model: str = DEFAULT_EDITOR_MODEL


class SaveRequest(BaseModel):
    filename: str
    content: str


# ---------- Kehotepohjat ----------

EDITOR_SYSTEM = (
    "Olet suunnitteludokumentin päätoimittaja. Kokoat paneelin keskustelusta "
    "yhtenäisen, hyvin jäsennellyn suunnitteludokumentin markdown-muodossa. "
    "Säilytä hyvät osat aiemmasta dokumentista, integroi keskustelun uudet "
    "oivallukset, ratkaise ristiriidat perustellusti ja merkitse avoimet "
    "kysymykset selkeästi. Palauta VAIN dokumentin sisältö markdownina, ei "
    "muuta selitystä. Kirjoita suomeksi."
)


def conversation_for_model(conv: list[Msg], participant_id_or_model: str, document: str, window_size: int = MAX_HISTORY_MESSAGES) -> list[dict]:
    """Muunna jaettu keskustelu yhden mallin näkökulman viestilistaksi.

    Käyttää liukuvaa ikkunaa (viimeiset window_size viestiä), jotta token-määrät pysyvät hallinnassa.
    Mallin omat aiemmat viestit -> assistant. Muiden (ja käyttäjän) -> user,
    puhujan nimellä varustettuna. Nykyinen dokumentti annetaan kontekstina.
    """
    messages: list[dict] = []
    if document.strip():
        messages.append({
            "role": "system",
            "content": f"Nykyinen suunnitteludokumentti (työn alla):\n\n{document}",
        })
    
    recent_conv = conv[-window_size:] if len(conv) > window_size else conv
    for m in recent_conv:
        if m.role == "assistant" and (m.model == participant_id_or_model or m.name == participant_id_or_model):
            messages.append({"role": "assistant", "content": m.content})
        else:
            messages.append({"role": "user", "content": f"[{m.name}]: {m.content}"})
    return messages


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# ---------- Päätepisteet ----------

@app.get("/api/config")
async def get_config():
    """Palauta ajantasainen agenttikonfiguraatio agents.json-tiedostosta."""
    cfg = load_agents_config()
    return {
        "participants": cfg["participants"],
        "default_active": cfg["default_active"],
        "editor_model": cfg["editor_model"],
        "max_history_messages": cfg["max_history_messages"],
        "model_pricing": cfg.get("model_pricing", {}),
    }


@app.post("/api/respond")
async def respond(req: RespondRequest):
    """Valitut osallistujat vastaavat vuorotellen omilla rooleillaan ja malleillaan.
    
    Kierroksen päätteeksi päivitetään automaattisesti suunnitteludokumentti (jos auto_update_doc=True).
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    cfg = load_agents_config()

    # Määritetään osallistujalista joko pyynnöstä tai suoraan dynaamisesta konfiguraatiosta
    selected_participants: list[Participant] = []
    if req.participants:
        selected_participants = req.participants
    else:
        participants_dict = cfg["participants"]
        for pid in cfg["default_active"]:
            if pid in participants_dict:
                p = participants_dict[pid]
                selected_participants.append(Participant(
                    id=p["id"],
                    name=p["name"],
                    role=p["role"],
                    model=p["model"],
                    system_prompt=p.get("system_prompt")
                ))

    editor_model = req.editor_model or cfg["editor_model"]
    window_size = req.max_history or cfg["max_history_messages"]

    async def gen():
        if not api_key:
            yield sse({"type": "error", "text": "OPENROUTER_API_KEY puuttuu. Aseta se .env-tiedostoon."})
            yield sse({"type": "done"})
            return

        # Työkopio keskustelusta, jota täydennetään kierroksen aikana, jotta
        # seuraava malli näkee edellisten vastaukset (paneelikeskustelu).
        working = list(req.conversation)

        async with httpx.AsyncClient() as client:
            # 1. Paneelikierros: Jokainen osallistuja vastaa vuorollaan
            for p in selected_participants:
                yield sse({
                    "type": "message_start",
                    "id": p.id,
                    "model": p.model,
                    "name": p.name,
                    "role": p.role
                })
                
                system_prompt = p.system_prompt or (
                    f"Olet {p.name}, rooliltasi {p.role}. Osallistut järjestelmäsuunnittelupaneeliin. "
                    "Keskustele rakentavasti ja vie asioita eteenpäin tiiviisti suomeksi."
                )
                messages = [{"role": "system", "content": system_prompt}]
                messages += conversation_for_model(working, p.id, req.document, window_size=window_size)
                
                parts: list[str] = []
                try:
                    async for event in stream_chat(client, p.model, messages, api_key):
                        if event["type"] == "text":
                            chunk = event["text"]
                            parts.append(chunk)
                            yield sse({"type": "token", "id": p.id, "name": p.name, "text": chunk})
                        elif event["type"] == "usage":
                            yield sse({
                                "type": "usage",
                                "id": p.id,
                                "name": p.name,
                                "model": p.model,
                                "usage": event["usage"]
                            })
                except LLMError as e:
                    err = f"[Virhe osallistujalta {p.name}: {e}]"
                    parts.append(err)
                    yield sse({"type": "error", "id": p.id, "name": p.name, "text": str(e)})
                
                text = "".join(parts)
                yield sse({"type": "message_done", "id": p.id, "name": p.name})
                working.append(Msg(role="assistant", name=p.name, model=p.model, content=text))

            # 2. Automaattinen dokumentin päivitys kierroksen päätteeksi
            if req.auto_update_doc:
                yield sse({"type": "doc_auto_update_start"})
                transcript = "\n\n".join(f"[{m.name}]: {m.content}" for m in working)
                user_content = (
                    "Päivitä suunnitteludokumentti paneelin uusimpien keskustelujen pohjalta.\n\n"
                    f"=== NYKYINEN DOKUMENTTI ===\n{req.document or '(tyhjä — luo ensimmäinen versio)'}\n\n"
                    f"=== PANEELIN KESKUSTELU ===\n{transcript or '(ei keskustelua)'}"
                )
                doc_messages = [
                    {"role": "system", "content": EDITOR_SYSTEM},
                    {"role": "user", "content": user_content},
                ]
                
                doc_parts: list[str] = []
                try:
                    async for event in stream_chat(client, editor_model, doc_messages, api_key):
                        if event["type"] == "text":
                            chunk = event["text"]
                            doc_parts.append(chunk)
                            yield sse({"type": "doc_auto_update_token", "text": chunk})
                        elif event["type"] == "usage":
                            yield sse({
                                "type": "usage",
                                "id": "editor",
                                "name": "Editori",
                                "model": editor_model,
                                "usage": event["usage"]
                            })
                    updated_doc = "".join(doc_parts)
                    yield sse({"type": "doc_auto_update_done", "document": updated_doc})
                except LLMError as e:
                    yield sse({"type": "error", "text": f"Dokumentin automaattipäivitys epäonnistui: {e}"})

        yield sse({"type": "done"})


    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/document")
async def document(req: DocumentRequest):
    """Editori-malli laatii/päivittää suunnitteludokumentin markdownina."""
    api_key = os.environ.get("OPENROUTER_API_KEY")

    async def gen():
        if not api_key:
            yield sse({"type": "error", "text": "OPENROUTER_API_KEY puuttuu. Aseta se .env-tiedostoon."})
            yield sse({"type": "done"})
            return

        # Rakenna editorille luettava tiivistelmä keskustelusta.
        transcript = "\n\n".join(f"[{m.name}]: {m.content}" for m in req.conversation)
        instruction = req.instruction.strip() or (
            "Laadi tai päivitä suunnitteludokumentti keskustelun pohjalta."
        )
        user_content = (
            f"{instruction}\n\n"
            f"=== NYKYINEN DOKUMENTTI ===\n{req.document or '(tyhjä — luo ensimmäinen versio)'}\n\n"
            f"=== PANEELIN KESKUSTELU ===\n{transcript or '(ei keskustelua vielä)'}"
        )
        messages = [
            {"role": "system", "content": EDITOR_SYSTEM},
            {"role": "user", "content": user_content},
        ]

        yield sse({"type": "doc_start"})
        async with httpx.AsyncClient() as client:
            try:
                async for event in stream_chat(client, req.editor_model, messages, api_key):
                    if event["type"] == "text":
                        yield sse({"type": "doc_token", "text": event["text"]})
                    elif event["type"] == "usage":
                        yield sse({
                            "type": "usage",
                            "id": "editor",
                            "name": "Editori",
                            "model": req.editor_model,
                            "usage": event["usage"]
                        })
            except LLMError as e:
                yield sse({"type": "error", "text": str(e)})
        yield sse({"type": "doc_done"})
        yield sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/save")
async def save(req: SaveRequest):
    """Tallenna dokumentti paikallisesti documents/-kansioon."""
    DOCS_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.\- ]", "_", req.filename).strip() or "dokumentti"
    if not safe.endswith(".md"):
        safe += ".md"
    path = DOCS_DIR / safe
    path.write_text(req.content, encoding="utf-8")
    return {"ok": True, "path": str(path)}


# Palvele käyttöliittymä (rekisteröidään API-reittien jälkeen).
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

