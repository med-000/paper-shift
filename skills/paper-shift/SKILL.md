---
name: paper-shift
description: Translate an English research PDF into a Japanese PDF with PaperShift, preserving page geometry, figures, and references where possible. Use when the user supplies a paper PDF and asks an agent in Claude Code or Codex to translate it into Japanese.
---

# PaperShift: translate a research PDF

Use your own model for translation. Do not run `pshift login`, call a translation API, or use an API key for the PDF translation. The PaperShift bridge performs only local extraction, validation, and PDF rendering. It needs Python 3.11+, PyMuPDF 1.26–1.x, access to an extractable-text PDF, and the bundled Japanese fonts. Ask before installing packages if your environment requires approval. Scanned PDFs require OCR and are not supported by this workflow.

## Get the PDF engine

Use an existing, trusted `paper-shift-plugin.zip` from PaperShift v0.3.0 if the user has already supplied one. Otherwise download the asset from:

`https://github.com/med-000/paper-shift/releases/download/v0.3.0/paper-shift-plugin.zip`

Verify the ZIP's SHA-256 is `c82d71e85ddb11779b9c2d0bc8a7e451520155e96ef29ed76303a1517ad881cb` before extracting. Unzip into a new temporary working directory. The script is at `paper-shift/scripts/pdf_bridge.py` in the extracted directory; it reads `paper-shift/vendor/src/pdf.py` and the bundled fonts. If the archive cannot be downloaded or the checksum differs, stop and report the problem. Never execute an unverified replacement.

If PyMuPDF is unavailable, install the dependencies from `requirements.txt` next to this SKILL.md into an isolated Python environment (for example, `python -m pip install -r <skill-dir>/requirements.txt`). Use the same Python environment when running the bridge. Do not install the published `paper-shift` package from PyPI: this skill uses the verified release ZIP and the agent's own translations instead of the CLI's sign-in and inference path.

## Translate and render

1. Choose a PDF file provided by the user and an output path, e.g. `paper-ja.pdf`. Keep the source intact. Run `python <extracted>/paper-shift/scripts/pdf_bridge.py extract <source.pdf> <manifest.json>` in a working directory outside the skill installation. Use unique new paths for the manifest, translations, and output. The manifest contains page numbers, batch IDs, and ordered English text fragments. Do not send the PDF to another service.
2. Translate each `texts` item into natural Japanese using your current model. Preserve citations, mathematical notation, numbers, URLs, and proper nouns. Keep the order and count of fragments for every batch. The extractor excludes the detected reference section; do not translate it separately.
3. Save UTF-8 `translations.json` in this structure: `{"batches":[{"id":"<manifest batch id>","translations":["訳文", "訳文"]}]}`. Use every ID exactly once, with one nonempty Japanese string per corresponding source fragment. For a long paper, save completed batches as you work and resume from the first missing ID. Do not invent translations for unfinished batches.
4. Run `python <extracted>/paper-shift/scripts/pdf_bridge.py render <source.pdf> <manifest.json> <translations.json> <output-ja.pdf>`. If validation fails, fix the identified batch and retry. Never bypass the source hash, ID, count, or text-order checks.
5. Open the output PDF and confirm the page count, Japanese text, and original references. Give the user the output path or a downloadable file, as supported by the agent environment. Mention any areas that remained in English or did not fit the layout.

If translation cannot be completed in the current session, keep the manifest and partial translations in the working directory and report the remaining batch IDs. Reference detection leaves all subsequent pages unchanged, including non-reference sections after References.
