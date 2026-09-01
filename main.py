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

from config import load_agents_config, DEFAULT_EDITOR_MODEL, MAX_HISTORY_MESSAGES
from llm import stream_chat, LLMError
from model_router import resolve_model, get_fallback_model, FREE_FALLBACK_MODEL
from tools import TOOLS, run_python_code
from tool_executor import execute_tool_call
from storage_routes import router as storage_router
from schemas import (
    Msg,
    Participant,
    RespondRequest,
    DocumentRequest,
    TopicSaveRequest,
    SaveRequest,
)

load_dotenv()

app = FastAPI(title="AI Design Studio")

DOCS_DIR = Path(__file__).parent / "documents"
DATA_DIR = Path(__file__).parent / "data"
STATIC_DIR = Path(__file__).parent / "static"


# ---------- Kehotepohjat ----------

AGENT_TOOL_INSTRUCTIONS = (
    "\n\nTYÖKALU-, KANSIO- JA TALLENNUSSÄÄNNÖT (EHDOTTOMAT):\n"
    "- Kooditiedostot ja skriptit: Tallenna AINA projektin 'work/'-kansioon käyttäen 'write_local_file' (esim. 'work/analyysi.py'). ÄLÄ KOSKAAN luo skriptejä minne sattuu tai tilapäiskansioihin.\n"
    "- Tulokset ja raportit: Tallenna kaikki laskenta-, simulaatio- ja analyysitulokset, raportit ja data AINA projektin 'results/'-kansioon (esim. 'results/sharpe_raportti.json', 'results/tulos.csv', 'results/yhteenveto.txt'). ÄLÄ tallenna tuloksia temp-kansioihin.\n"
    "- Koodin suoritus:\n"
    "  * Pikatestit (< 10s): Käytä 'execute_python(code)' tai 'eval_python_expression(code_or_expr)'.\n"
    "  * Raskaat laskennat ja iso data (Polars, Parquet, simulaatiot > 10s): Käytä AINA 'start_background_job(code, name)'. Anna täydellinen koodi ja tallenna tulostiedostot 'results/'-kansioon.\n"
    "- Tiedostojen luku: 'read_local_file(path)' tai 'list_local_directory(path)'."
)

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


app.include_router(storage_router)

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
        # Etsitään @nimi, @id tai lauseen aloitus "Nimi, ..."
        pattern = rf"(?:@|^|\b)({re.escape(pid)}|{re.escape(name_lower)})(?:[:,\s]|$)"
        if f"@{pid}" in last_user_msg or f"@{name_lower}" in last_user_msg:
            mentioned_ids.append(pid)
        elif re.search(pattern, last_user_msg) and (last_user_msg.startswith(name_lower) or f" {name_lower}" in last_user_msg):
            # Varmistetaan ettei tavallinen sana vahingossa liipaise jos ei @-etuliitettä
            if f"@{pid}" in last_user_msg or f"@{name_lower}" in last_user_msg or last_user_msg.startswith(f"{name_lower},") or last_user_msg.startswith(f"{name_lower}:"):
                mentioned_ids.append(pid)

    # Määritetään vastaajat: jos käyttäjä kutsui suoraan tiettyä agenttia/agentteja, vastataan vain heille!
    selected_participants: list[Participant] = []
    if mentioned_ids:
        for pid in mentioned_ids:
            if pid in participants_dict:
                p = participants_dict[pid]
                selected_participants.append(Participant(
                    id=p["id"],
                    name=p["name"],
                    role=p["role"],
                    model=p["model"],
                    system_prompt=p.get("system_prompt")
                ))
    elif req.participants and len(req.participants) > 0:
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

    # Varmistus: jos lista on silti tyhjä, otetaan vähintään seppo
    if not selected_participants and participants_dict:
        first_p = list(participants_dict.values())[0]
        selected_participants.append(Participant(
            id=first_p["id"],
            name=first_p["name"],
            role=first_p["role"],
            model=first_p["model"],
            system_prompt=first_p.get("system_prompt")
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
                base_prompt = p.system_prompt or (
                    f"Olet {p.name}, rooliltasi {p.role}. Osallistut järjestelmäsuunnitteluun. "
                    "Keskustele rakentavasti ja vie asioita eteenpäin tiiviisti suomeksi."
                )
                system_prompt = base_prompt + AGENT_TOOL_INSTRUCTIONS
                messages = [{"role": "system", "content": system_prompt}]
                messages += conversation_for_model(working, p.id, req.document, window_size=window_size)
                
                # Määritetään suoritettava malli (huomioi dynaaminen auto-valinta)
                actual_model = resolve_model(p.model, p.id, messages=messages)

                yield sse({
                    "type": "message_start",
                    "id": p.id,
                    "model": actual_model,
                    "name": p.name,
                    "role": p.role
                })
                
                parts: list[str] = []
                try:
                    # Mallille annetaan työkalut (esim. execute_python)
                    current_model_messages = list(messages)
                    
                    # Agent Tool Loop (max 2 kierrosta: 1. suoritus, 2. kommentointi)
                    p_fallback_model = get_fallback_model(p.id)
                    for loop_step in range(2):
                        tool_calls_complete = []
                        async for event in stream_chat(
                            client,
                            actual_model,
                            current_model_messages,
                            api_key,
                            tools=TOOLS if loop_step == 0 else None,
                            fallback_model=p_fallback_model
                        ):
                            if event["type"] == "text":
                                chunk = event["text"]
                                parts.append(chunk)
                                yield sse({"type": "token", "id": p.id, "name": p.name, "text": chunk})
                            elif event["type"] == "fallback_triggered":
                                actual_model = event["fallback_model"]
                                notice = f"\n\n🛡️ *[Varajärjestelmä aktivoitu: {event['reason']} Käytetään ilmaista mallia: {actual_model}]*\n\n"
                                parts.append(notice)
                                yield sse({"type": "token", "id": p.id, "name": p.name, "text": notice})
                            elif event["type"] == "tool_calls_complete":
                                tool_calls_complete = event["tool_calls"]
                            elif event["type"] == "usage":
                                yield sse({
                                    "type": "usage",
                                    "id": p.id,
                                    "name": p.name,
                                    "model": actual_model,
                                    "usage": event["usage"]
                                })

                        if not tool_calls_complete:
                            # Ei työkalukutsuja tai kommentointikierros valmis
                            break

                        # Malli pyysi työkalukutsuja: suoritetaan ja valmistellaan re-prompt
                        yield sse({"type": "token", "id": p.id, "name": p.name, "text": "\n\n⚡ *[Suoritetaan työkalua...]*\n"})
                        
                        assistant_msg_content = "".join(parts)
                        current_model_messages.append({
                            "role": "assistant",
                            "content": assistant_msg_content or None,
                            "tool_calls": tool_calls_complete
                        })

                        for tc in tool_calls_complete:
                            call_id = tc.get("id", "call_1")
                            fn = tc.get("function", {})
                            fn_name = fn.get("name", "")
                            args_str = fn.get("arguments", "{}")
                            try:
                                args = json.loads(args_str) if isinstance(args_str, str) else args_str
                            except Exception:
                                args = {}

                            chat_msg, raw_result = execute_tool_call(fn_name, args)
                            parts.append(chat_msg)
                            yield sse({"type": "token", "id": p.id, "name": p.name, "text": chat_msg})

                            # Lisätään tulos mallin kontekstiin
                            current_model_messages.append({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": fn_name,
                                "content": raw_result or "(ei tulostetta)"
                            })
                        
                        # Ilmoitetaan että malli analysoi tuloksia
                        yield sse({"type": "token", "id": p.id, "name": p.name, "text": "\n💬 *[Analysoidaan tulosta...]*\n\n"})

                    # Agentin vastauskierros valmis (koodien automaattinen 10s väkisinsuoritus poistettu, jotta raskaat ajot eivät katkea)
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
                actual_editor_model = resolve_model(editor_model, "editor", messages=doc_messages)
                try:
                    async for event in stream_chat(client, actual_editor_model, doc_messages, api_key):
                        if event["type"] == "text":
                            chunk = event["text"]
                            doc_parts.append(chunk)
                            yield sse({"type": "doc_auto_update_token", "text": chunk})
                        elif event["type"] == "fallback_triggered":
                            actual_editor_model = event["fallback_model"]
                        elif event["type"] == "usage":
                            yield sse({
                                "type": "usage",
                                "id": "editor",
                                "name": "Editori",
                                "model": actual_editor_model,
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
        actual_model = resolve_model(req.editor_model, "editor", messages=messages)
        async with httpx.AsyncClient() as client:
            try:
                async for event in stream_chat(client, actual_model, messages, api_key):
                    if event["type"] == "text":
                        yield sse({"type": "doc_token", "text": event["text"]})
                    elif event["type"] == "fallback_triggered":
                        actual_model = event["fallback_model"]
                    elif event["type"] == "usage":
                        yield sse({
                            "type": "usage",
                            "id": "editor",
                            "name": "Editori",
                            "model": actual_model,
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
