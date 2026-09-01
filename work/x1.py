import json
from pathlib import Path

base = Path(r"C:\Users\Jarmo\Documents\kode\debate\work")
print("=== Tiedostot work/-kansiossa ===")
for p in sorted(base.glob("*")):
    print(f"  {p.name}  ({p.stat().st_size} B)")

f = base / "threshold_optimization_results.json"
if f.exists():
    print("\n=== NYKYINEN TULOS ===")
    print(json.dumps(json.loads(f.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))