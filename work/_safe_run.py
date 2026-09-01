import sys
import io
import os
import runpy
import traceback

# Varmistetaan UTF-8 -koodaus Windows-konsolissa ja putkissa
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def main():
    target_script = sys.argv[1] if len(sys.argv) > 1 else None

    if target_script:
        if not os.path.exists(target_script):
            print(f"[VIRHE] Tiedostoa ei löydy: {target_script}", file=sys.stderr)
            print("\n[VALMIS] Suoritus päättyi virheeseen.")
            sys.exit(1)

        print(f"--- Aloitetaan suoritus: {target_script} ---")
        try:
            sys.argv = sys.argv[1:]
            runpy.run_path(target_script, run_name="__main__")
            print("\n[VALMIS] Skriptin suoritus päättyi onnistuneesti.")
        except Exception:
            traceback.print_exc()
            print("\n[VALMIS] Skriptin suoritus keskeytyi virheeseen.")
            sys.exit(1)
    else:
        print("[INFO] _safe_run alustettu UTF-8 -tilassa.")
        print("\n[VALMIS] Valmis suorittamaan komentoja ja skriptejä.")

if __name__ == "__main__":
    main()