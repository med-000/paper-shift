"""Exercise the distributable skills-only plugin without model or API calls."""

import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

import pymupdf


ROOT = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_packaged_bridge_extracts_and_renders_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            package = runpy.run_path(str(ROOT / "scripts/package-plugin.py"))["package"]
            archive = package(folder / "plugin.zip")
            with ZipFile(archive) as zip_file:
                self.assertIn("paper-shift/plugin.json", zip_file.namelist())
                zip_file.extractall(folder)
            bridge = folder / "paper-shift/scripts/pdf_bridge.py"
            source = folder / "source.pdf"
            manifest = folder / "manifest.json"
            translations = folder / "translations.json"
            output = folder / "translated.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page(width=400, height=600)
                page.insert_text((40, 100), "The experiment was successful.", fontsize=11)
                page.insert_textbox((40, 300, 350, 550),
                                    "References\n1. Example author, an English paper.", fontsize=10)
                page = doc.new_page(width=400, height=600)
                page.insert_text((40, 100), "2. A continued English citation.", fontsize=10)
                doc.save(source)

            def invoke(*args: Path | str) -> subprocess.CompletedProcess:
                return subprocess.run([sys.executable, str(bridge), *map(str, args)],
                                      capture_output=True, text=True, check=False)

            extracted = invoke("extract", source, manifest)
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["pages"], 2)
            self.assertEqual([item["texts"] for item in data["batches"]],
                             [["The experiment was successful."]])

            # Reject missing batches before writing any output.
            translations.write_text('{"batches":[]}', encoding="utf-8")
            self.assertNotEqual(invoke("render", source, manifest, translations, output).returncode, 0)
            self.assertFalse(output.exists())

            translations.write_text(json.dumps({"batches": [
                {"id": data["batches"][0]["id"], "translations": ["実験は成功した。"]},
            ]}, ensure_ascii=False), encoding="utf-8")
            rendered = invoke("render", source, manifest, translations, output)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            with pymupdf.open(output) as doc:
                self.assertEqual(doc.page_count, 2)
                self.assertIn("実験は成功した", doc[0].get_text())
                self.assertIn("Example author", doc[0].get_text())
                self.assertIn("continued English citation", doc[1].get_text())

            # A changed input cannot silently reuse a previously translated manifest.
            with source.open("ab") as stream:
                stream.write(b"\n")
            another = folder / "changed.pdf"
            self.assertNotEqual(invoke("render", source, manifest, translations, another).returncode, 0)
            self.assertFalse(another.exists())

            # Distinct pages can be translated in parallel without mixing their results.
            pair = folder / "two-pages.pdf"
            pair_manifest = folder / "two-pages.json"
            pair_translations = folder / "two-pages-ja.json"
            pair_output = folder / "two-pages-ja.pdf"
            with pymupdf.open() as doc:
                for text in ("The first page is correct.", "The second page is different."):
                    page = doc.new_page(width=400, height=600)
                    page.insert_text((40, 100), text, fontsize=11)
                doc.save(pair)
            self.assertEqual(invoke("extract", pair, pair_manifest).returncode, 0)
            pair_data = json.loads(pair_manifest.read_text(encoding="utf-8"))
            pair_translations.write_text(json.dumps({"batches": [
                {"id": batch["id"], "translations": [translation]}
                for batch, translation in zip(pair_data["batches"], ("最初のページ。", "次のページ。"), strict=True)
            ]}, ensure_ascii=False), encoding="utf-8")
            result = invoke("render", pair, pair_manifest, pair_translations, pair_output)
            self.assertEqual(result.returncode, 0, result.stderr)
            with pymupdf.open(pair_output) as doc:
                self.assertIn("最初のページ", doc[0].get_text())
                self.assertIn("次のページ", doc[1].get_text())

            repeated = folder / "repeated.pdf"
            repeated_manifest = folder / "repeated.json"
            repeated_translations = folder / "repeated-ja.json"
            repeated_output = folder / "repeated-ja.pdf"
            with pymupdf.open() as doc:
                for _ in range(2):
                    page = doc.new_page(width=400, height=600)
                    page.insert_text((40, 100), "The same English sentence.", fontsize=11)
                doc.save(repeated)
            self.assertEqual(invoke("extract", repeated, repeated_manifest).returncode, 0)
            repeated_data = json.loads(repeated_manifest.read_text(encoding="utf-8"))
            repeated_translations.write_text(json.dumps({"batches": [
                {"id": batch["id"], "translations": [translation]}
                for batch, translation in zip(repeated_data["batches"], ("一ページ目。", "二ページ目。"), strict=True)
            ]}, ensure_ascii=False), encoding="utf-8")
            result = invoke("render", repeated, repeated_manifest, repeated_translations, repeated_output)
            self.assertEqual(result.returncode, 0, result.stderr)
            with pymupdf.open(repeated_output) as doc:
                self.assertIn("一ページ目", doc[0].get_text())
                self.assertIn("二ページ目", doc[1].get_text())


if __name__ == "__main__":
    unittest.main()
