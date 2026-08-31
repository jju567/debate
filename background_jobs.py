"""Asynkroninen taustalaskentamoottori (Background Job Runner).

Mahdollistaa raskaiden Python-simulaatioiden, optimointien ja data-ajojen
suorittamisen taustalla ilman HTTP/SSE-aikakatkaisurajoja.
"""

import sys
import uuid
import json
import time
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any

JOBS_DIR = Path(__file__).parent / "data" / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# Muistissa pidettävä työrekisteri
_JOBS: Dict[str, Dict[str, Any]] = {}


def start_background_job(code: str, name: str = "laskenta") -> dict:
    """Käynnistää Python-koodin suorituksen taustaprosessina ilman aikarajaa."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    script_path = job_dir / "script.py"
    log_path = job_dir / "output.log"
    status_path = job_dir / "status.json"

    script_path.write_text(code, encoding="utf-8")

    job_info = {
        "job_id": job_id,
        "name": name,
        "status": "running",
        "start_time": time.time(),
        "end_time": None,
        "script_path": str(script_path),
        "log_path": str(log_path),
        "returncode": None,
    }
    _save_status(job_id, job_info)

    def _runner():
        with open(log_path, "w", encoding="utf-8") as lf:
            try:
                # Sääntöjen mukainen Windows 'py -3' suoritus
                proc = subprocess.Popen(
                    ["py", "-3", str(script_path)],
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    cwd=str(Path(__file__).parent),
                    text=True,
                )
                proc.wait()
                job_info["returncode"] = proc.returncode
                job_info["status"] = "completed" if proc.returncode == 0 else "failed"
            except Exception as e:
                lf.write(f"\nVirhe prosessin käynnistyksessä: {e}\n")
                job_info["status"] = "failed"
                job_info["returncode"] = -1
            finally:
                job_info["end_time"] = time.time()
                _save_status(job_id, job_info)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()

    return {
        "success": True,
        "job_id": job_id,
        "name": name,
        "status": "running",
        "message": f"Taustalaskenta '{name}' käynnistetty onnistuneesti (ID: {job_id}).",
    }


def get_job_status(job_id: str, tail_lines: int = 25) -> dict:
    """Tarkistaa taustalaskennan tilan ja hakee uusimmat lokitulosteet."""
    status_path = JOBS_DIR / job_id / "status.json"
    log_path = JOBS_DIR / job_id / "output.log"

    if not status_path.exists():
        return {"success": False, "error": f"Taustatyötä {job_id} ei löydy."}

    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        data = _JOBS.get(job_id, {"status": "unknown"})

    # Luetaan lokin loppuosa
    logs = ""
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            logs = "\n".join(lines[-tail_lines:]) if lines else "(ei tulostetta vielä)"
        except Exception as e:
            logs = f"(Lokin lukuvirhe: {e})"

    runtime_sec = (data.get("end_time") or time.time()) - data.get("start_time", time.time())

    return {
        "success": True,
        "job_id": job_id,
        "name": data.get("name"),
        "status": data.get("status"),
        "runtime_sec": round(runtime_sec, 2),
        "returncode": data.get("returncode"),
        "recent_logs": logs,
    }


def list_background_jobs() -> list[dict]:
    """Listaa kaikki suoritetut ja käynnissä olevat taustatyöt."""
    jobs = []
    for sp in JOBS_DIR.glob("*/status.json"):
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
            jobs.append({
                "job_id": data.get("job_id", sp.parent.name),
                "name": data.get("name"),
                "status": data.get("status"),
                "start_time": data.get("start_time"),
            })
        except Exception:
            continue
    jobs.sort(key=lambda x: x.get("start_time") or 0, reverse=True)
    return jobs


def _save_status(job_id: str, data: dict):
    _JOBS[job_id] = data
    status_path = JOBS_DIR / job_id / "status.json"
    try:
        status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass
