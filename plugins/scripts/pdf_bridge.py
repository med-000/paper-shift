"""Offline bridge between ChatGPT-generated translations and the PaperShift PDF engine."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from threading import Lock


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
if not VENDOR.is_dir():
    raise SystemExit("Plugin package is incomplete: run scripts/package-plugin.py first.")
sys.path.insert(0, str(VENDOR))

import pymupdf  # noqa: E402
from src.pdf import PdfError, _batches, _page_blocks, translate_pdf  # noqa: E402


class BridgeError(Exception):
    """Manifest or translations do not match the original PDF."""


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BridgeError(f"JSON object expected: {path}")
    return data


def _manifest(source: Path) -> dict:
    if not source.is_file():
        raise BridgeError(f"PDF not found: {source}")
    with pymupdf.open(source) as document:
        if not document.is_pdf or document.needs_pass or not document.page_count:
            raise BridgeError("A readable, unencrypted PDF is required.")
        batches = []
        in_references = False
        for number, page in enumerate(document, start=1):
            blocks, in_references = _page_blocks(page, in_references)
            for index, texts in enumerate(_batches(blocks), start=1):
                batches.append({"id": f"p{number:04d}-b{index:04d}", "page": number, "texts": texts})
        if not batches:
            raise BridgeError("No extractable English text to translate.")
        return {"format": 1, "source_sha256": _digest(source), "pages": document.page_count, "batches": batches}


def extract(source: Path, manifest: Path) -> None:
    if manifest.exists():
        raise BridgeError(f"Manifest already exists: {manifest}")
    data = _manifest(source)
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {data['pages']} pages, {len(data['batches'])} translation batches: {manifest}")


def render(source: Path, manifest: Path, translations: Path, output: Path) -> None:
    expected = _manifest(source)
    if _read_json(manifest) != expected:
        raise BridgeError("Manifest does not match the current PDF or extraction settings; extract again.")
    data = _read_json(translations)
    entries = data.get("batches")
    if not isinstance(entries, list) or len(entries) != len(expected["batches"]):
        raise BridgeError("Translation batch count differs from manifest.")
    by_id = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] in by_id:
            raise BridgeError("Missing or duplicate translation batch ID.")
        by_id[entry["id"]] = entry.get("translations")
    by_batch = {}
    for batch in expected["batches"]:
        results = by_id.get(batch["id"])
        if not isinstance(results, list) or len(results) != len(batch["texts"]) or not all(
            isinstance(item, str) and item.strip() for item in results
        ):
            raise BridgeError(f"Missing or invalid translations for {batch['id']}.")
        by_batch[batch["id"]] = (batch["texts"], results)
    completed = set()
    lock = Lock()

    def consume(page: int, batch_number: int, texts: list[str]) -> list[str]:
        batch_id = f"p{page:04d}-b{batch_number:04d}"
        with lock:
            entry = by_batch.get(batch_id)
            if entry is None or batch_id in completed or entry[0] != texts:
                raise BridgeError("PDF translation batches changed; extract again.")
            completed.add(batch_id)
            return entry[1]

    pages, blocks = translate_pdf(source, output, translate_batch=consume)
    if len(completed) != len(expected["batches"]):
        output.unlink(missing_ok=True)
        raise BridgeError("Not all translation batches were consumed.")
    print(f"Saved {pages} pages, {blocks} translated text areas: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract_parser = commands.add_parser("extract")
    extract_parser.add_argument("source", type=Path)
    extract_parser.add_argument("manifest", type=Path)
    render_parser = commands.add_parser("render")
    for name in ("source", "manifest", "translations", "output"):
        render_parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            extract(args.source, args.manifest)
        else:
            render(args.source, args.manifest, args.translations, args.output)
    except (BridgeError, PdfError, pymupdf.FileDataError, OSError, ValueError) as error:
        parser.exit(1, f"PaperShift: {error}\n")


if __name__ == "__main__":
    main()
