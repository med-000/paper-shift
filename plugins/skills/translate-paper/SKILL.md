---
name: translate-paper
description: Translate an attached English research PDF into a downloadable Japanese PDF using PaperShift. Use when a user asks to translate a paper PDF into Japanese while preserving its figures, page layout, and references.
---

# Translate a research PDF

Use ChatGPT's own model to translate. Do not call the OpenAI API, use a developer API key, or run `pshift login`. This skill requires a Python environment able to execute the packaged script and import PyMuPDF, with access to the user's attached PDF and the packaged fonts. If these are unavailable, explain the limitation; do not invent a downloadable PDF.

1. Locate the user-provided PDF in the current execution environment. Run `python <plugin-root>/scripts/pdf_bridge.py extract <input.pdf> <manifest.json>`. If `import pymupdf` fails, install from `<plugin-root>/requirements.txt` only when the environment permits package installation, then retry. The script prints the number of pages and batches. Do not pass the PDF to an external service.
2. Read `manifest.json`. Each batch contains `id`, `page`, and `texts` (ordered English fragments). Translate **every** fragment into natural Japanese in the same order. Preserve citations, URLs, numbers, mathematical notation, and proper nouns. Never translate references; the extractor excludes the reference section. Do not combine or split items, even across page boundaries.
3. Write `translations.json` as `{"batches":[{"id":"p0001-b0001","translations":["訳文", ...]}, ...]}`. Use precisely the IDs and item counts from the manifest; do not use the sample ID above if it isn't present. Work in small groups of batches when the paper is long, saving completed entries as you go. Do not fabricate or silently omit any batch. If the context is insufficient to finish, retain the files and tell the user which IDs are incomplete.
4. Run `python <plugin-root>/scripts/pdf_bridge.py render <input.pdf> <manifest.json> <translations.json> <output-ja.pdf>`. The renderer rejects altered inputs, missing or duplicate batches, empty translations, and mismatched item counts. If it fails, correct the specific translations and retry. Do not bypass validation or translate with a separate API.
5. Open the generated PDF and check its page count, visible Japanese text, and original references where present. Return the generated PDF as a downloadable file using the current ChatGPT file interface. State any layout or untranslated-section limitations.

Only extractable text is supported; scanned PDFs need OCR. The current layout algorithm preserves whole pages after a detected References heading, including non-reference sections on later pages. The script uses the PDF processor bundled from the PaperShift CLI; see `../../scripts/pdf_bridge.py` for the executable entry point (the path is relative to this skill directory).
