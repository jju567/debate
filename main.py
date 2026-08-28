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
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import load_agents_config, DEFAULT_EDITOR_MODEL, MAX_HISTORY_MESSAGES
from llm import stream_chat, LLMError

load_dotenv()

app = FastAPI(title="AI Design Studio")

DOCS_DIR = Path(__file__).parent / "documents"
DATA_DIR = Path(__file__).parent / "data"
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


from tools import TOOLS, run_python_code, eval_in_memory

# ---------- Päätepisteet ----------

@app.post("/api/tools/execute")
async def execute_code_api(payload: dict):
    """Suora päätepiste Python-koodin ajamiseen (tukee myös pikaevaluointia)."""
    code = payload.get("code", "")
    use_fast = payload.get("fast", False)
    if use_fast:
        return eval_in_memory(code)
    return run_python_code(code)

@app.get("/api/config")
async def get_config():
    """Palauta ajantasainen agenttikonfiguraatio ja käyttäjäprofiili agents.json-tiedostosta."""
    cfg = load_agents_config()
    return {
        "participants": cfg["participants"],
        "default_active": cfg["default_active"],
        "editor_model": cfg["editor_model"],
        "max_history_messages": cfg["max_history_messages"],
        "model_pricing": cfg.get("model_pricing", {}),
        "user_profile": cfg.get("user_profile", {
            "id": "user",
            "name": "Käyttäjä",
            "role": "Tuoteomistaja",
            "is_human": True
        }),
    }


@app.post("/api/respond")
async def respond(req: RespondRequest):
    """Valitut osallistujat vastaavat tarpeen mukaan (suora kutsu @nimellä tai valittu paneeli).
    
    Kierroksen päätteeksi päivitetään automaattisesti suunnitteludokumentti (jos auto_update_doc=True).
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    cfg = load_agents_config()
    participants_dict = cfg["participants"]

    # Tarkistetaan viimeisimmästä käyttäjän viestistä mahdolliset suorat @kutsut (esim. @seppo, @matti, "Seppo, ...")
    last_user_msg = ""
    for m in reversed(req.conversation):
        if m.role == "user":
            last_user_msg = m.content.lower()
            break

    # Etsitään mainitut agentit
    mentioned_ids = []
    for pid, p in participants_dict.items():
        name_lower = p["name"].lower()
        if f"@{pid}" in last_user_msg or f"@{name_lower}" in last_user_msg or last_user_msg.startswith(f"{name_lower},") or last_user_msg.startswith(f"{name_lower}:"):
            mentioned_ids.append(pid)

    # Määritetään vastaajat: jos käyttäjä kutsui suoraan tiettyä agenttia/agentteja, vastataan vain heille!
    selected_participants: list[Participant] = []
    if mentioned_ids:
        for pid in mentioned_ids:
            p = participants_dict[pid]
            selected_participants.append(Participant(
                id=p["id"],
                name=p["name"],
                role=p["role"],
                model=p["model"],
                system_prompt=p.get("system_prompt")
            ))
    elif req.participants:
        selected_participants = req.participants
    else:
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
            # 1. Osallistujat vastaavat
            for p in selected_participants:
                yield sse({
                    "type": "message_start",
                    "id": p.id,
                    "model": p.model,
                    "name": p.name,
                    "role": p.role
                })
                
                system_prompt = p.system_prompt or (
                    f"Olet {p.name}, rooliltasi {p.role}. Osallistut järjestelmäsuunnitteluun. "
                    "Keskustele rakentavasti ja vie asioita eteenpäin tiiviisti suomeksi."
                )
                messages = [{"role": "system", "content": system_prompt}]
                messages += conversation_for_model(working, p.id, req.document, window_size=window_size)
                
                parts: list[str] = []
                tool_calls_accumulator = []
                try:
                    # Mallille annetaan työkalut (esim. execute_python)
                    async for event in stream_chat(client, p.model, messages, api_key, tools=TOOLS):
                        if event["type"] == "text":
                            chunk = event["text"]
                            parts.append(chunk)
                            yield sse({"type": "token", "id": p.id, "name": p.name, "text": chunk})
                        elif event["type"] == "tool_calls":
                            tool_calls_accumulator.extend(event["tool_calls"])
                        elif event["type"] == "usage":
                            yield sse({
                                "type": "usage",
                                "id": p.id,
                                "name": p.name,
                                "model": p.model,
                                "usage": event["usage"]
                            })

                    # Jos malli kutsui työkalua (esim. suoritti Python-koodia)
                    if tool_calls_accumulator:
                        yield sse({"type": "token", "id": p.id, "name": p.name, "text": "\n\n⚡ *[Suoritetaan Python-koodia...]*\n"})
                        for tc in tool_calls_accumulator:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name")
                            args_str = fn.get("arguments", "{}")
                            try:
                                args = json.loads(args_str) if isinstance(args_str, str) else args_str
                            except Exception:
                                args = {}

                            if fn_name == "execute_python":
                                code_to_run = args.get("code", "")
                                yield sse({
                                    "type": "tool_executed",
                                    "tool": "execute_python",
                                    "code": code_to_run
                                })
                                res = run_python_code(code_to_run)
                                output_text = res["output"]
                                parts.append(f"\n```python\n# Suoritettu koodi:\n{code_to_run}\n```\n**Tuloste:**\n```\n{output_text}\n```\n")
                                yield sse({
                                    "type": "token",
                                    "id": p.id,
                                    "name": p.name,
                                    "text": f"\n```python\n# Suoritettu koodi:\n{code_to_run}\n```\n**Tuloste:**\n```\n{output_text}\n```\n"
                                })
                            elif fn_name == "eval_python_expression":
                                expr_to_run = args.get("code_or_expr", "")
                                yield sse({
                                    "type": "tool_executed",
                                    "tool": "eval_python_expression",
                                    "code": expr_to_run
                                })
                                res = eval_in_memory(expr_to_run)
                                output_text = res["output"]
                                parts.append(f"\n⚡ *[REPL: `{expr_to_run}`]*\n**Tulos:** `{output_text}`\n")
                                yield sse({
                                    "type": "token",
                                    "id": p.id,
                                    "name": p.name,
                                    "text": f"\n⚡ *[REPL: `{expr_to_run}`]*\n**Tulos:** `{output_text}`\n"
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
                    updated_doc = "".join(doc_parts).strip()
                    if updated_doc:
                        yield sse({"type": "doc_auto_update_done", "document": updated_doc})
                    else:
                        yield sse({"type": "doc_auto_update_done", "document": req.document})
                except LLMError as e:
                    yield sse({"type": "error", "text": f"Dokumentin automaattipäivitys epäonnistui: {e}"})
                    yield sse({"type": "doc_auto_update_done", "document": req.document})

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


# ---------- Aiheiden (Topics) hallinta ----------

def get_topics_dir() -> Path:
    topics_dir = DATA_DIR / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    return topics_dir


@app.get("/api/topics")
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
    # Järjestetään uusimmat ensin
    topics.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"topics": topics}


@app.get("/api/topics/{topic_id}")
async def get_topic(topic_id: str):
    """Hae tietyn aiheen koko tila (keskustelu, dokumentti, tilastot)."""
    safe_id = re.sub(r"[^A-Za-z0-9_.\- ]", "_", topic_id).strip()
    path = get_topics_dir() / f"{safe_id}.json"
    if not path.exists():
        return {"error": "Aihetta ei löydy"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/topics/save")
async def save_topic(req: TopicSaveRequest):
    """Tallenna aihe ja sen tiivistetty tila data/topics -kansioon."""
    td = get_topics_dir()
    safe_id = re.sub(r"[^A-Za-z0-9_.\- ]", "_", req.id).strip() or "aihe_1"
    path = td / f"{safe_id}.json"
    
    # Luodaan lyhyt tiivistelmä jos ei annettu
    summary = req.summary
    if not summary and req.conversation:
        last_msgs = [m.content for m in req.conversation if m.role == "user"]
        summary = (last_msgs[-1][:120] + "...") if last_msgs else req.title

    import datetime
    topic_data = {
        "id": safe_id,
        "title": req.title.strip() or safe_id,
        "summary": summary,
        "conversation": [m.dict() for m in req.conversation],
        "document": req.document,
        "stats": req.stats,
        "updated_at": datetime.datetime.now().isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(topic_data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "topic": topic_data}


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


@app.get("/")
async def root():
    """Palvele etusivun käyttöliittymä."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "AI Design Studio Backend Running. static/index.html not found."}


# Palvele staattiset tiedostot (CSS, JS, kuvat)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)


