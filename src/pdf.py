"""Replace extractable English text with Japanese in approximately the same page areas."""

import os
from pathlib import Path
import re
import tempfile
from collections.abc import Callable

import pymupdf


class PdfError(Exception):
    """An input PDF cannot be translated without losing text or layout."""


def _chunks(text: str, max_length: int = 3500) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        while len(word) > max_length:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(word[:max_length])
            word = word[max_length:]
        if len(current) + len(word) + (1 if current else 0) > max_length:
            chunks.append(current)
            current = ""
        current = f"{current} {word}" if current else word
    if current:
        chunks.append(current)
    return chunks


def _text_blocks(page: pymupdf.Page) -> list[tuple[pymupdf.Rect, str]]:
    blocks = []
    for block in page.get_text("blocks", sort=True):
        if block[6] != 0:
            continue
        text = re.sub(r"-\s*\n\s*", "", block[4]).replace("\n", " ").strip()
        if not text or not re.search(r"[A-Za-z]", text):
            continue
        rect = pymupdf.Rect(block[:4]) & page.cropbox
        # Very thin headers, footers and figure labels often contain dense
        # metadata that cannot be legibly replaced within the same page.
        if rect.is_empty or rect.is_infinite or rect.height < 10.5:
            continue
        blocks.append((rect, text))
    return blocks


def _placement(page: pymupdf.Page, blocks: list[tuple[pymupdf.Rect, str]], obstacles: list[pymupdf.Rect], index: int) -> pymupdf.Rect:
    source = blocks[index][0]
    bottom = page.cropbox.y1 - 12
    for other in obstacles:
        if other.y0 < source.y1 - 1 or other == source:
            continue
        overlap = min(source.x1, other.x1) - max(source.x0, other.x0)
        if overlap > min(source.width, other.width) * 0.3:
            bottom = min(bottom, other.y0 - 2)
    return pymupdf.Rect(source.x0, source.y0, source.x1, max(source.y1, bottom))


def _insert_translation(page: pymupdf.Page, area: pymupdf.Rect, text: str, page_number: int, block_number: int) -> None:
    for size in (10.5, 9.5, 8.5, 7.5, 6.5, 5.5, 5.0):
        remaining = page.insert_textbox(area, text, fontsize=size, fontname="japan", lineheight=1.2)
        if remaining >= 0:
            return
    raise PdfError(f"{page_number}ページ目の{block_number}番目の訳文が収まりません（領域{area.width:.0f}×{area.height:.0f}pt、訳文{len(text)}文字）。")


def translate_pdf(
    source: Path, destination: Path, translate_texts: Callable[[list[str]], list[str]], *, force: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[int, int]:
    """Save a translated copy only after every translated block fits on its original page."""
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_file():
        raise PdfError(f"入力PDFが見つかりません: {source}")
    if source == destination:
        raise PdfError("入力PDFと出力先を同じファイルにできません。")
    if destination.exists() and not force:
        raise PdfError(f"出力先が既に存在します: {destination}（上書きする場合は--force）")
    if not destination.parent.is_dir():
        raise PdfError(f"出力先のフォルダが見つかりません: {destination.parent}")

    try:
        document = pymupdf.open(source)
    except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError) as error:
        raise PdfError("入力ファイルをPDFとして開けませんでした。") from error
    with document:
        if not document.is_pdf or document.needs_pass or document.page_count == 0:
            raise PdfError("暗号化されていないページ付きのPDFを指定してください。")
        translated = 0
        in_references = False
        for number, page in enumerate(document, start=1):
            raw_blocks = [block for block in page.get_text("blocks") if block[6] == 0]
            obstacles = [pymupdf.Rect(block[:4]) for block in raw_blocks]
            headings = [pymupdf.Rect(block[:4]).y0 for block in raw_blocks
                        if block[4].strip().lower() in ("references", "bibliography")]
            reference_start = min(headings) if headings else None
            blocks = [] if in_references else _text_blocks(page)
            if reference_start is not None:
                blocks = [(rect, text) for rect, text in blocks if rect.y0 < reference_start]
                in_references = True
            if not blocks:
                if progress:
                    progress(number, document.page_count)
                continue
            fragments = [(index, fragment) for index, (_, text) in enumerate(blocks) for fragment in _chunks(text)]
            translations = [[] for _ in blocks]
            processed = 0
            while processed < len(fragments):
                batch = []
                length = 0
                for index, fragment in fragments[processed:]:
                    if batch and length + len(fragment) > 3000:
                        break
                    batch.append((index, fragment))
                    length += len(fragment)
                results = translate_texts([text for _, text in batch])
                if len(results) != len(batch) or not all(isinstance(result, str) and result.strip() for result in results):
                    raise PdfError(f"{number}ページ目の訳文と原文領域の対応が崩れました。")
                for (index, _), result in zip(batch, results):
                    translations[index].append(result.strip())
                processed += len(batch)
            for rect, _ in blocks:
                page.add_redact_annot(rect, fill=False, cross_out=False)
            page.apply_redactions(images=0, graphics=0, text=0)
            for index, result in enumerate(translations):
                _insert_translation(page, _placement(page, blocks, obstacles, index), "".join(result), number, index + 1)
                translated += 1
            if progress:
                progress(number, document.page_count)
        if translated == 0:
            raise PdfError("翻訳できる英文テキストがありません。画像だけのPDFは現在対象外です。")

        temporary: Path | None = None
        try:
            fd, path = tempfile.mkstemp(prefix=".pshift-", suffix=".pdf", dir=destination.parent)
            os.close(fd)
            temporary = Path(path)
            document.save(temporary, garbage=4, deflate=True)
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return document.page_count, translated
