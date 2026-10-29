"""Generate the same small dataset twice and compare file checksums."""
import hashlib
import json
import tempfile
from pathlib import Path
import generator.generate_data as generator

ROOT = Path(__file__).resolve().parents[1]

def checksum_map(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).iterdir()) if p.is_file()}

def main():
    original_data, original_output = generator.DATA_DIR, generator.OUTPUT_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/"first", Path(tmp)/"second"
            first.mkdir(); second.mkdir()
            generator.DATA_DIR, generator.OUTPUT_DIR = first, first
            generator.generate(products=10, days=5, promotions=5, seed=20261022)
            checksums_first = checksum_map(first)
            generator.DATA_DIR, generator.OUTPUT_DIR = second, second
            generator.generate(products=10, days=5, promotions=5, seed=20261022)
            checksums_second = checksum_map(second)
            result = {"reproducible": checksums_first == checksums_second, "files_compared": len(checksums_first), "checksums_first": checksums_first, "checksums_second": checksums_second}
    finally:
        generator.DATA_DIR, generator.OUTPUT_DIR = original_data, original_output
    out = ROOT/"outputs"; out.mkdir(exist_ok=True)
    (out/"reproducibility_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"reproducible":result["reproducible"],"files_compared":result["files_compared"]}, indent=2))
    raise SystemExit(0 if result["reproducible"] else 1)

if __name__ == "__main__":
    main()
