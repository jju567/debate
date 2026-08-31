import io
import math
import sys
import subprocess
import tempfile
import contextlib
from pathlib import Path

# Työkansio skripteille
SCRIPTS_DIR = Path(__file__).parent / "scripts"
SCRIPTS_DIR.mkdir(exist_ok=True)

# Pysyvä muistitila kevyille kokeiluille (In-Memory REPL)
_REPL_GLOBALS = {
    "math": math,
    "__builtins__": __builtins__,
}

# 1. Täysi aliprosessi-suoritus
EXECUTE_PYTHON_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": "Suorita monimutkaista Python-koodia tai skriptejä erillisessä aliprosessissa ja palauta tuloste. Soveltuu tiedostokäsittelyyn ja laajoihin algoritmeihin.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Suoritettava Python-koodi."
                }
            },
            "required": ["code"]
        }
    }
}

# 2. Kevyt In-Memory REPL / kokeiluympäristö
EVAL_PYTHON_TOOL = {
    "type": "function",
    "function": {
        "name": "eval_python_expression",
        "description": "Erittäin nopea ja kevyt in-memory Python-kokeiluympäristö (REPL). Soveltuu matemaattisten kaavojen, funktion pika-arviointien ja pikakokeilujen ajamiseen ilman prosessin käynnistysviivettä.",
        "parameters": {
            "type": "object",
            "properties": {
                "code_or_expr": {
                    "type": "string",
                    "description": "Arvioitava Python-lauseke tai koodinpätkä (esim. 'math.sqrt(144) + sum([1,2,3])' tai 'res = [x**2 for x in range(10)]; print(res)')."
                }
            },
            "required": ["code_or_expr"]
        }
    }
}

# 3. Verkkohaku (DuckDuckGo)
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Hae ajantasaista tietoa, dokumentaatiota, teknologiavertailuja tai uutisia suoraan verkosta hakusanoilla.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Hakusanat tai hakulauseke (esim. 'FastAPI lifespan events documentation' tai 'Python asyncio best practices')."
                }
            },
            "required": ["query"]
        }
    }
}

# 4. Verkkosivun sisällön nouto
FETCH_WEBPAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_webpage",
        "description": "Lue tietyn URL-osoitteen tekstisisältö analysoitavaksi (esim. dokumentaatiosivu tai artikkeli).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Verkkosivun täysi URL-osoite (esim. 'https://docs.python.org/3/library/asyncio.html')."
                }
            },
            "required": ["url"]
        }
    }
}

# 5. Dokumenttikirjaston lukeminen (On-demand viitteet)
READ_LIBRARY_DOC_TOOL = {
    "type": "function",
    "function": {
        "name": "read_library_doc",
        "description": "Lue käyttäjän dokumenttikirjastoon lataama viitedokumentti tai tiedosto (esim. arkkitehtuurikuvaus, API-spec tai vaatimusmäärittely) tilapäisesti analysoitavaksi.",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "Kirjastossa olevan dokumentin nimi tai id (esim. 'arkkitehtuuri.md' tai 'api_spec.json')."
                }
            },
            "required": ["doc_id"]
        }
    }
}

LIST_LIBRARY_DOCS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_library_docs",
        "description": "Listaa kaikki dokumenttikirjastossa saatavilla olevat tiedostot ja niiden lyhyet tiivistelmät.",
        "parameters": {
            "type": "object",
            "properties": {},
        }
    }
}

# 6. Paikallisten tiedostojen ja kansioiden lukeminen
READ_LOCAL_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_local_file",
        "description": "Lue tietokoneella olemassa olevan paikallisen tiedoston sisältö annetusta polusta (esim. 'C:/Users/Jarmo/Documents/kode/trade/.../main.py' tai suhteellinen polku).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Tiedoston absoluuttinen tai suhteellinen polku."
                }
            },
            "required": ["path"]
        }
    }
}

LIST_LOCAL_DIRECTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "list_local_directory",
        "description": "Listaa tietyn paikallisen kansion sisältämät tiedostot ja alikansiot rakennekatsausta varten.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Kansion absoluuttinen tai suhteellinen polku (esim. 'C:/Users/Jarmo/Documents/kode/trade')."
                }
            },
            "required": ["path"]
        }
    }
}

TOOLS = [
    EXECUTE_PYTHON_TOOL,
    EVAL_PYTHON_TOOL,
    WEB_SEARCH_TOOL,
    FETCH_WEBPAGE_TOOL,
    READ_LIBRARY_DOC_TOOL,
    LIST_LIBRARY_DOCS_TOOL,
    READ_LOCAL_FILE_TOOL,
    LIST_LOCAL_DIRECTORY_TOOL
]


def read_local_file_content(path_str: str, max_chars: int = 5000) -> dict:
    """Lue paikallinen tiedosto turvallisesti ja siististi."""
    p = Path(path_str.strip().strip('"').strip("'"))
    if not p.exists():
        return {"success": False, "output": f"Tiedostoa ei löydy polusta: {p}"}
    if not p.is_file():
        return {"success": False, "output": f"Polku {p} ei ole tiedosto."}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        truncated = text[:max_chars]
        is_trunc = len(text) > max_chars
        suffix = f"\n... [Näytetään ensimmäiset {max_chars}/{len(text)} merkkiä]" if is_trunc else ""
        return {"success": True, "output": truncated + suffix}
    except Exception as e:
        return {"success": False, "output": f"Tiedoston luku epäonnistui: {e}"}


def list_local_directory_contents(path_str: str, max_items: int = 40) -> dict:
    """Listaa annetun kansion sisältö."""
    p = Path(path_str.strip().strip('"').strip("'"))
    if not p.exists():
        return {"success": False, "output": f"Kansiota ei löydy polusta: {p}"}
    if not p.is_dir():
        return {"success": False, "output": f"Polku {p} ei ole kansio."}
    try:
        entries = []
        for child in sorted(p.iterdir()):
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            icon = "📁" if child.is_dir() else "📄"
            entries.append(f"{icon} {child.name}")
            if len(entries) >= max_items:
                entries.append("... [lisää tiedostoja]")
                break
        return {"success": True, "output": "\n".join(entries) or "(tyhjä kansio)"}
    except Exception as e:
        return {"success": False, "output": f"Kansion listaus epäonnistui: {e}"}


def search_web(query: str, max_results: int = 5) -> dict:
    """Suorita verkkohaku DuckDuckGo HTML/API -rajapinnan kautta ilman maksullisia avaimia."""
    import urllib.parse
    import re
    import httpx

    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return {"success": False, "output": f"Hakuvirhe: HTTP {resp.status_code}"}
            
            html = resp.text
            # Etsitään tulokset yksinkertaisella regexillä (tulokset ja snippetit)
            results = []
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            titles = re.findall(r'<a class="result__url[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)

            for i in range(min(len(snippets), max_results)):
                raw_snippet = re.sub(r"<.*?>", "", snippets[i]).strip()
                res_url = titles[i][0] if i < len(titles) else ""
                results.append(f"{i+1}. {raw_snippet} (Lähde: {res_url})")

            if results:
                out = "\n\n".join(results)
                return {"success": True, "output": out}
            else:
                # Varavaihtoehto DuckDuckGo Lite API
                lite_url = f"https://lite.duckduckgo.com/lite/"
                lite_resp = client.post(lite_url, data={"q": query})
                clean_text = re.sub(r"<[^>]+>", " ", lite_resp.text)
                clean_text = re.sub(r"\s+", " ", clean_text)[:600]
                return {"success": True, "output": clean_text or "Ei suoria hakutuloksia."}
    except Exception as e:
        return {"success": False, "output": f"Verkkohaku epäonnistui: {e}"}


def fetch_webpage_content(url: str, max_chars: int = 2500) -> dict:
    """Nouda annetun verkkosivun teksti ja siisti HTML."""
    import re
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        with httpx.Client(headers=headers, timeout=12.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return {"success": False, "output": f"Sivun noutovirhe: HTTP {resp.status_code}"}
            
            html = resp.text
            # Poistetaan scriptit ja tyylit
            html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
            # Poistetaan HTML-tagit
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            truncated = text[:max_chars]
            return {"success": True, "output": truncated if truncated else "(sivu oli tyhjä)"}
    except Exception as e:
        return {"success": False, "output": f"Sivun lataus epäonnistui: {e}"}


def eval_in_memory(code_or_expr: str) -> dict:
    """Suorita koodi välittömästi muistissa ilman aliprosessin viivettä (kevyet kokeilut)."""
    code_or_expr = code_or_expr.strip()
    stdout_capture = io.StringIO()
    
    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stdout_capture):
            # Kokeillaan ensin eval (yksittäinen lauseke)
            try:
                compiled = compile(code_or_expr, "<repl>", "eval")
                result_val = eval(compiled, _REPL_GLOBALS)
                captured = stdout_capture.getvalue().strip()
                output = f"{captured}\n=> {result_val}" if captured else f"=> {result_val}"
                return {
                    "success": True,
                    "returncode": 0,
                    "stdout": output,
                    "stderr": "",
                    "output": output
                }
            except (SyntaxError, TypeError):
                # Monirivinen tai lauseita sisältävä koodi (exec)
                compiled = compile(code_or_expr, "<repl>", "exec")
                exec(compiled, _REPL_GLOBALS)
                captured = stdout_capture.getvalue().strip()
                return {
                    "success": True,
                    "returncode": 0,
                    "stdout": captured,
                    "stderr": "",
                    "output": captured if captured else "(koodi suoritettiin onnistuneesti muistissa ilman tulostetta)"
                }
    except Exception as e:
        return {
            "success": False,
            "returncode": 1,
            "stdout": "",
            "stderr": str(e),
            "output": f"Virhe: {e}"
        }


def run_python_code(code: str, timeout_sec: int = 15) -> dict:
    """Suorita annettu Python-koodi paikallisesti eristetyssä prosessissa Windows 'py' -komennolla."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(code)
        temp_file_path = tf.name

    try:
        # Käytetään sääntöjen mukaista Windows 'py' -komentoa
        result = subprocess.run(
            ["py", "-3", temp_file_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(Path(__file__).parent)
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output": stdout if stdout else (stderr if stderr else "(ei tulostetta)")
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Suoritus aikakatkaistiin ({timeout_sec}s aikaraja ylittyi).",
            "output": f"Aikakatkaisu ({timeout_sec}s)"
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "output": f"Virhe: {e}"
        }
    finally:
        try:
            Path(temp_file_path).unlink(missing_ok=True)
        except Exception:
            pass

