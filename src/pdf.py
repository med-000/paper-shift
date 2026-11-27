"""Replace extractable English text with Japanese in approximately the same page areas."""

import os
from pathlib import Path
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from dataclasses import dataclass

import pymupdf


class PdfError(Exception):
    """An input PDF cannot be translated without losing text or layout."""


FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONTS = {
    "PSans": FONT_DIR / "NotoSansJP-Regular.ttf",
    "PSansBold": FONT_DIR / "NotoSansJP-Bold.ttf",
    "PSerif": FONT_DIR / "NotoSerifJP-Regular.ttf",
}


@dataclass(frozen=True)
class TextBlock:
    rect: pymupdf.Rect
    text: str
    size: float
    bold: bool
    serif: bool
    title: bool
    heading: bool


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


def _text_blocks(page: pymupdf.Page) -> list[TextBlock]:
    blocks = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block["type"] != 0:
            continue
        lines = block["lines"]
        spans = [span for line in lines for span in line["spans"] if span["text"].strip()]
        if not spans:
            continue
        raw = "\n".join("".join(span["text"] for span in line["spans"]) for line in lines)
        text = re.sub(r"-\s*\n\s*", "", raw).replace("\n", " ").strip()
        if not re.search(r"[A-Za-z]", text):
            continue
        rect = pymupdf.Rect(block["bbox"]) & page.cropbox
        if rect.is_empty or rect.is_infinite or rect.height < 10.5:
            continue
        if page.number == 0 and (
            (rect.y0 < page.rect.height * 0.25 and "Member, IEEE" in text)
            or text.startswith("Received ")
            or "@" in text
            or text.startswith("This article has supplementary")
        ):
            # Preserve names, affiliations and publication metadata verbatim.
            continue
        dominant = max(spans, key=lambda span: len(span["text"].strip()))
        size = float(dominant["size"])
        title = page.number == 0 and rect.y0 < page.rect.height * 0.25 and size >= 16
        bold = sum(len(s["text"]) for s in spans if s["flags"] & 16) >= sum(len(s["text"]) for s in spans) / 2
        heading = not title and bold and len(text) < 110 and (size >= 10 or bool(re.match(r"^[IVX]+\.\s+[A-Z]", text)))
        font = dominant["font"].lower()
        serif = any(name in font for name in ("times", "serif", "roman", "mincho"))
        blocks.append(TextBlock(rect, text, size, bold, serif, title, heading))
    return blocks


def _reference_start(page: pymupdf.Page) -> float | None:
    """Find a reference heading even when PyMuPDF merges it with citation lines."""
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if re.fullmatch(r"(?:[IVX]+\.|\d+\.?\s+)?(?:references|bibliography|works cited)\s*:?", text, re.IGNORECASE):
                return float(line["bbox"][1])
    return None


def _citation_block(text: str) -> bool:
    return bool(re.match(r"\s*\d{1,3}\.\s*(?:\n|[A-Z])", text))


def _page_blocks(page: pymupdf.Page, in_references: bool) -> tuple[list[TextBlock], bool]:
    reference_start = None if in_references else _reference_start(page)
    blocks = [] if in_references else _text_blocks(page)
    if reference_start is not None:
        blocks = [block for block in blocks if block.rect.y0 < reference_start
                  and not _citation_block(block.text)]
        in_references = True
    return blocks, in_references


def _batches(blocks: list[TextBlock]) -> list[list[str]]:
    fragments = [fragment for block in blocks for fragment in _chunks(block.text)]
    batches = []
    current = []
    length = 0
    for fragment in fragments:
        if current and length + len(fragment) > 3000:
            batches.append(current)
            current = []
            length = 0
        current.append(fragment)
        length += len(fragment)
    if current:
        batches.append(current)
    return batches


def _register_fonts(page: pymupdf.Page) -> None:
    for name, path in FONTS.items():
        if not path.is_file():
            raise PdfError(f"日本語フォントがありません: {path.name}")
        page.insert_font(fontname=name, fontfile=str(path))


def _style(block: TextBlock, scale: float) -> tuple[str, float]:
    size = block.size * scale
    if block.title or block.heading:
        return "PSansBold", size
    if block.bold:
        return "PSansBold", size
    return ("PSerif" if block.serif else "PSans"), size


def _lane(rect: pymupdf.Rect, page: pymupdf.Page) -> str:
    if rect.width > page.cropbox.width * 0.65:
        return "full"
    return "left" if (rect.x0 + rect.x1) / 2 < (page.cropbox.x0 + page.cropbox.x1) / 2 else "right"


def _overlaps_horizontally(a: pymupdf.Rect, b: pymupdf.Rect) -> bool:
    return min(a.x1, b.x1) - max(a.x0, b.x0) > min(a.width, b.width) * 0.3


def _layout(
    canvas: pymupdf.Page, blocks: list[TextBlock], translations: list[str], obstacles: list[pymupdf.Rect],
    scales: list[float],
) -> tuple[list[tuple[pymupdf.Rect, str, str, float]] | None, int | None]:
    cursor = {"full": 0.0, "left": 0.0, "right": 0.0}
    placements = []
    for index, (block, text, scale) in enumerate(zip(blocks, translations, scales, strict=True)):
        lane = _lane(block.rect, canvas)
        start = max(block.rect.y0, cursor[lane], cursor["full"])
        if lane == "full":
            start = max(start, cursor["left"], cursor["right"])
        for obstacle in obstacles:
            if _overlaps_horizontally(block.rect, obstacle) and obstacle.y0 <= start < obstacle.y1:
                start = obstacle.y1 + 2
        bottom = canvas.cropbox.y1 - 12
        if block.title:
            for following in blocks:
                if following.rect.y0 > block.rect.y0 + 1 and _overlaps_horizontally(block.rect, following.rect):
                    bottom = min(bottom, following.rect.y0 - 2)
        for obstacle in obstacles:
            if obstacle.y0 > start + 1 and _overlaps_horizontally(block.rect, obstacle):
                bottom = min(bottom, obstacle.y0 - 2)
        if start >= bottom:
            return None, index
        right = max(block.rect.x1, canvas.cropbox.x1 - block.rect.x0) if block.title else block.rect.x1
        area = pymupdf.Rect(block.rect.x0, start, right, bottom)
        font, size = _style(block, scale)
        remaining = canvas.insert_textbox(area, text, fontname=font, fontsize=size, lineheight=1.2)
        if remaining < 0:
            return None, index
        visible = [pymupdf.Rect(span["bbox"])
                   for rendered in canvas.get_text("dict", clip=area)["blocks"] if rendered["type"] == 0
                   for line in rendered["lines"] for span in line["spans"]
                   if span["bbox"][1] >= start - 1
                   and (pymupdf.Rect(span["bbox"]) & area).width >= pymupdf.Rect(span["bbox"]).width * 0.8]
        if not visible:
            return None, index
        bounds = visible[0]
        for other in visible[1:]:
            bounds |= other
        if bounds.y1 > bottom - 1 or any((bounds & obstacle).get_area() > 1 for obstacle in obstacles):
            return None, index
        used_bottom = bounds.y1 + 2
        if lane == "full":
            cursor = {key: used_bottom for key in cursor}
        else:
            cursor[lane] = used_bottom
        placements.append((area, text, font, size))
    return placements, None


def _choose_layout(page: pymupdf.Page, blocks: list[TextBlock], translations: list[str], obstacles: list[pymupdf.Rect]) -> list[tuple[pymupdf.Rect, str, str, float]]:
    def attempt(scales: list[float]) -> tuple[list[tuple[pymupdf.Rect, str, str, float]] | None, int | None]:
        with pymupdf.open() as preview:
            canvas = preview.new_page(width=page.rect.width, height=page.rect.height)
            _register_fonts(canvas)
            return _layout(canvas, blocks, translations, obstacles, scales)

    # Start from the exact extracted sizes. Shrink only the block that fails;
    # if it is already at the limit, make room by shrinking an earlier block.
    scales = [1.0] * len(blocks)
    for _ in range(len(blocks) * 12):
        placements, failed = attempt(scales)
        if placements is not None:
            return placements
        assert failed is not None
        candidates = [failed] + [index for index in range(failed - 1, -1, -1)
                                 if _overlaps_horizontally(blocks[index].rect, blocks[failed].rect)]
        target = next((index for index in candidates if scales[index] > 0.61), None)
        if target is None:
            break
        next_scale = round(scales[target] - 0.05, 2)
        if blocks[target].title:
            for index, block in enumerate(blocks):
                if block.title:
                    scales[index] = min(scales[index], next_scale)
        else:
            scales[target] = next_scale

    # A shared reduction can still succeed when many small adjustments interact.
    for scale in (0.9, 0.8, 0.7, 0.6):
        placements, _ = attempt([scale] * len(blocks))
        if placements is not None:
            return placements
    raise PdfError(f"{page.number + 1}ページ目の訳文を元の文字サイズ比率のまま配置できませんでした。")


def translate_pdf(
    source: Path, destination: Path, translate_texts: Callable[[list[str]], list[str]] | None = None, *, force: bool = False,
    progress: Callable[[int, int], None] | None = None,
    translate_batch: Callable[[int, int, list[str]], list[str]] | None = None,
) -> tuple[int, int]:
    """Save a translated copy only after every translated block fits on its original page."""
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_file():
        raise PdfError(f"入力PDFが見つかりません: {source}")
    if translate_texts is None and translate_batch is None:
        raise PdfError("翻訳処理が指定されていません。")
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
        # Network requests dominate PDF processing; bounded concurrency keeps
        # independent batches in flight while preserving their original order.
        with ThreadPoolExecutor(max_workers=3) as executor:
            prepared = []
            for number, page in enumerate(document, start=1):
                blocks, in_references = _page_blocks(page, in_references)
                if not blocks:
                    prepared.append((number, blocks, [], []))
                    continue
                fragments = [(index, fragment) for index, block in enumerate(blocks) for fragment in _chunks(block.text)]
                pending = []
                processed = 0
                for batch_number, texts in enumerate(_batches(blocks), start=1):
                    batch = fragments[processed:processed + len(texts)]
                    if translate_batch is None:
                        assert translate_texts is not None
                    future = (executor.submit(translate_batch, number, batch_number, texts)
                              if translate_batch is not None else executor.submit(translate_texts, texts))
                    pending.append((batch, future))
                    processed += len(texts)
                raw_blocks = [block for block in page.get_text("blocks") if block[6] == 0]
                prepared.append((number, blocks, raw_blocks, pending))

            for number, blocks, raw_blocks, pending in prepared:
                if not blocks:
                    if progress:
                        progress(number, document.page_count)
                    continue
                page = document[number - 1]
                translations = [[] for _ in blocks]
                for batch, future in pending:
                    results = future.result()
                    if len(results) != len(batch) or not all(isinstance(result, str) and result.strip() for result in results):
                        raise PdfError(f"{number}ページ目の訳文と原文領域の対応が崩れました。")
                    for (index, _), result in zip(batch, results):
                        translations[index].append(result.strip())
                # Only text that stays in the original PDF acts as a fixed obstacle.
                obstacles = [pymupdf.Rect(raw[:4]) for raw in raw_blocks
                             if not any((pymupdf.Rect(raw[:4]) & block.rect).get_area() >= block.rect.get_area() * 0.9
                                        for block in blocks)]
                layout = _choose_layout(page, blocks, ["".join(parts) for parts in translations], obstacles)
                for block in blocks:
                    page.add_redact_annot(block.rect, fill=False, cross_out=False)
                page.apply_redactions(images=0, graphics=0, text=0)
                _register_fonts(page)
                for area, text, font, size in layout:
                    if page.insert_textbox(area, text, fontname=font, fontsize=size, lineheight=1.2) < 0:
                        raise PdfError(f"{number}ページ目の訳文を配置できませんでした。")
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
            document.subset_fonts()
            document.save(temporary, garbage=4, deflate=True)
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return document.page_count, translated
