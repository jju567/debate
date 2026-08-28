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

TOOLS = [EXECUTE_PYTHON_TOOL, EVAL_PYTHON_TOOL]


def eval_in_memory(code_or_expr: str) -> dict:
    """Suorita koodi välittömästi muistissa ilman aliprosessin viivettä (kevyet kokeilut)."""
    code_or_expr = code_or_expr.strip()
    stdout_capture = io.StringIO()
    
    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stdout_capture):
            # Kokeillaan ensin suoraa evaluointia (lauseke)
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
            except SyntaxError:
                # Jos kyseessä on monirivinen koodi (exec)
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

