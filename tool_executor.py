"""Työkalujen suorituksen ja tulosten koonnin apumoduuli."""

import json
import logging
from tools import (
    run_python_code,
    eval_in_memory,
    search_web,
    fetch_webpage_content,
    read_local_file_content,
    list_local_directory_contents,
)
from library import read_library_document, list_library_documents
from background_jobs import start_background_job, get_job_status, list_background_jobs

logger = logging.getLogger("debate.tool_executor")
logger.setLevel(logging.INFO)


def execute_tool_call(fn_name: str, args: dict) -> tuple[str, str]:
    """Suorita yksittäinen työkalukutsu ja palauta (chat_esitys, raaka_tulos).

    Returns:
        (out_msg_for_chat, tool_result_string)
    """
    logger.info(f"Suoritetaan työkalu: {fn_name} parametreilla: {args}")
    
    if fn_name == "execute_python":
        code_to_run = args.get("code", "")
        res = run_python_code(code_to_run)
        output_str = res.get("output", "")
        out_msg = (
            f"\n```python\n# Suoritettu koodi:\n{code_to_run}\n```\n"
            f"**⚡ Tuloste:**\n```\n{output_str}\n```\n"
        )
        return out_msg, output_str

    elif fn_name == "start_background_job":
        code_to_run = args.get("code", "")
        job_name = args.get("name", "laskenta")
        res = start_background_job(code_to_run, job_name)
        job_id = res.get("job_id", "")
        out_msg = (
            f"\n🚀 **[Taustalaskenta käynnistetty]**\n"
            f"- **Nimi:** {job_name}\n"
            f"- **Job ID:** `{job_id}`\n"
            f"- *Laskenta suoritetaan omassa taustaprosessissa ilman aikarajaa. Tarkista tila: `check_job_status(job_id=\"{job_id}\")`*\n"
        )
        return out_msg, json.dumps(res, ensure_ascii=False)

    elif fn_name == "check_job_status":
        job_id = args.get("job_id", "")
        res = get_job_status(job_id)
        if not res.get("success"):
            err_text = res.get("error", "Virhe")
            return f"\n⚠️ **Virhe taustatyössä:** {err_text}\n", err_text
        
        status = res.get("status")
        runtime = res.get("runtime_sec", 0)
        logs = res.get("recent_logs", "")
        out_msg = (
            f"\n⏱️ **[Taustatyön tila: `{job_id}`]**\n"
            f"- **Tila:** `{status}` (kesto: {runtime}s)\n"
            f"**Uusimmat lokitulosteet:**\n```\n{logs}\n```\n"
        )
        return out_msg, json.dumps(res, ensure_ascii=False)

    elif fn_name == "list_background_jobs":
        jobs = list_background_jobs()
        if not jobs:
            summary = "(ei käynnistettyjä taustalaskentoja)"
        else:
            summary = "\n".join([f"- `{j['job_id']}` ({j['name']}): status `{j['status']}`" for j in jobs])
        out_msg = f"\n📋 **[Kaikki taustatyöt:]**\n{summary}\n"
        return out_msg, summary

    elif fn_name == "eval_python_expression":
        expr_to_run = args.get("code_or_expr", "")
        res = eval_in_memory(expr_to_run)
        output_str = res.get("output", "")
        out_msg = f"\n⚡ *[REPL: `{expr_to_run}`]*\n**Tulos:** `{output_str}`\n"
        return out_msg, output_str

    elif fn_name == "web_search":
        query = args.get("query", "")
        res = search_web(query)
        output_str = res.get("output", "")
        out_msg = f"\n🌐 *[Verkkohaku: \"{query}\"]*\n**Tulokset:**\n{output_str}\n"
        return out_msg, output_str

    elif fn_name == "fetch_webpage":
        url_to_fetch = args.get("url", "")
        res = fetch_webpage_content(url_to_fetch)
        output_str = res.get("output", "")
        out_msg = f"\n📄 *[Haettu sivu: {url_to_fetch}]*\n**Sisältö:**\n{output_str[:500]}...\n"
        return out_msg, output_str

    elif fn_name == "read_library_doc":
        doc_id = args.get("doc_id", "")
        res = read_library_document(doc_id)
        output_str = res["content"] if res.get("success") else res.get("error", "Virhe")
        out_msg = f"\n📚 *[Luettu viitedokumentti: {doc_id}]*\n```\n{output_str[:600]}...\n```\n"
        return out_msg, output_str

    elif fn_name == "list_library_docs":
        docs = list_library_documents()
        docs_summary = "\n".join([f"- {d['filename']} ({d['char_count']} merkkiä): {d['summary']}" for d in docs]) or "(kirjasto on tyhjä)"
        out_msg = f"\n📚 *[Kirjaston dokumentit:]*\n{docs_summary}\n"
        return out_msg, docs_summary

    elif fn_name == "read_local_file":
        path_val = args.get("path", "")
        res = read_local_file_content(path_val)
        output_str = res.get("output", "")
        out_msg = f"\n📂 *[Luettu paikallinen tiedosto: `{path_val}`]*\n```\n{output_str[:600]}...\n```\n"
        return out_msg, output_str

    elif fn_name == "list_local_directory":
        dir_path = args.get("path", "")
        res = list_local_directory_contents(dir_path)
        output_str = res.get("output", "")
        out_msg = f"\n📁 *[Kansion sisältö: `{dir_path}`]*\n```\n{output_str}\n```\n"
        return out_msg, output_str

    else:
        err_msg = f"Tuntematon työkalu: {fn_name}"
        logger.warning(err_msg)
        return f"\n⚠️ {err_msg}\n", err_msg
