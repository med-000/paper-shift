"""Verify saved Japanese text, page geometry, and non-destructive failure paths."""

from pathlib import Path
from threading import Barrier
import tempfile
import unittest
from unittest.mock import Mock

import pymupdf

from src.pdf import PdfError, translate_pdf


class PdfTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory / "paper.pdf"
        self.output = self.directory / "paper-ja.pdf"

    def _paper(self) -> None:
        with pymupdf.open() as doc:
            first = doc.new_page(width=320, height=450)
            first.insert_text((40, 65), "The results were significant.", fontsize=11)
            first.draw_rect((45, 140, 180, 200), fill=(1, 0, 0), color=(1, 0, 0))
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
            pix.clear_with(200)
            first.insert_image((200, 150, 230, 180), pixmap=pix)
            second = doc.new_page(width=320, height=500)
            second.insert_text((40, 310), "Further studies are needed.", fontsize=11)
            doc.save(self.source)

    def test_pdf_keeps_pages_and_approximate_text_positions(self) -> None:
        self._paper()
        translator = Mock(side_effect=[["結果は有意だった。"], ["さらなる研究が必要である。"]])
        self.assertEqual(translate_pdf(self.source, self.output, translator), (2, 2))
        self.assertEqual(translator.call_count, 2)
        with pymupdf.open(self.output) as doc:
            self.assertEqual([page.rect.height for page in doc], [450, 500])
            first, second = doc
            self.assertIn("結果は有意だった", first.get_text())
            self.assertIn("さらなる研究が必要", second.get_text())
            self.assertNotIn("The results", first.get_text())
            self.assertNotIn("Further studies", second.get_text())
            positions = [page.search_for(word)[0].y0 for page, word in (
                (first, "結果"), (second, "さらなる"),
            )]
            self.assertTrue(40 < positions[0] < 85)
            self.assertTrue(280 < positions[1] < 330)
            self.assertTrue(first.get_drawings())
            self.assertTrue(first.get_images())

    def test_failure_does_not_leave_partial_or_overwrite_input(self) -> None:
        self._paper()
        translator = Mock(return_value=["とても長い文章。" * 2000])
        with self.assertRaises(PdfError):
            translate_pdf(self.source, self.output, translator)
        self.assertFalse(self.output.exists())
        with pymupdf.open(self.source) as doc:
            self.assertIn("The results were significant", doc[0].get_text())
        with self.assertRaisesRegex(PdfError, "同じファイル"):
            translate_pdf(self.source, self.source, translator)
        self.output.write_bytes(b"existing")
        with self.assertRaisesRegex(PdfError, "既に存在"):
            translate_pdf(self.source, self.output, translator)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_image_only_pdf_is_not_reported_as_translated(self) -> None:
        with pymupdf.open() as doc:
            doc.new_page(width=300, height=300)
            doc.save(self.source)
        with self.assertRaisesRegex(PdfError, "英文テキストがありません"):
            translate_pdf(self.source, self.output, Mock())
        self.assertFalse(self.output.exists())

    def test_two_columns_keep_their_separate_page_areas(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=780)
            page.insert_textbox((40, 110, 275, 250), "This paper describes the first result. " * 5, fontsize=10)
            page.insert_textbox((325, 110, 560, 250), "The second result is described here. " * 5, fontsize=10)
            doc.save(self.source)
        with pymupdf.open(self.source) as doc:
            self.assertEqual(len([b for b in doc[0].get_text("blocks") if b[6] == 0]), 2)
        translator = Mock(return_value=["最初の結果について述べる。" * 3, "二つ目の結果について述べる。" * 3])
        translate_pdf(self.source, self.output, translator)
        translator.assert_called_once()
        with pymupdf.open(self.output) as doc:
            first = doc[0].search_for("最初の結果")[0]
            second = doc[0].search_for("二つ目の結果")[0]
            self.assertLess(first.x0, 275)
            self.assertGreaterEqual(second.x0, 325)
            self.assertTrue(90 < first.y0 < 140)
            self.assertTrue(90 < second.y0 < 140)

    def test_references_remain_untranslated_across_pages(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page(width=400, height=600)
            page.insert_text((40, 100), "The experiment was successful.", fontsize=11)
            page.insert_text((40, 450), "REFERENCES", fontsize=10)
            page.insert_text((40, 490), "[1] Example author, Example journal.", fontsize=11)
            page = doc.new_page(width=400, height=600)
            page.insert_text((40, 100), "[2] Further work, Example journal.", fontsize=11)
            doc.save(self.source)
        translator = Mock(return_value=["実験は成功した。"])
        self.assertEqual(translate_pdf(self.source, self.output, translator), (2, 1))
        translator.assert_called_once()
        with pymupdf.open(self.output) as doc:
            self.assertIn("実験は成功した", doc[0].get_text())
            self.assertIn("REFERENCES", doc[0].get_text())
            self.assertIn("Example author", doc[0].get_text())
            self.assertIn("Further work", doc[1].get_text())

    def test_reference_heading_merged_with_citations_is_not_sent_to_model(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page(width=400, height=600)
            page.insert_text((40, 100), "The experiment was successful.", fontsize=11)
            page.insert_textbox((40, 300, 350, 550),
                                "References\n1. Example author, an English paper.\n2. Another author, more results.", fontsize=10)
            page.insert_textbox((210, 60, 380, 180), "17. Xie, P. et al. A cited work.", fontsize=10)
            page = doc.new_page(width=400, height=600)
            page.insert_text((40, 100), "3. A continued English citation.", fontsize=10)
            doc.save(self.source)
        with pymupdf.open(self.source) as doc:
            self.assertIn("References\n1.", doc[0].get_text())
        translator = Mock(return_value=["実験は成功した。"])
        self.assertEqual(translate_pdf(self.source, self.output, translator), (2, 1))
        translator.assert_called_once_with(["The experiment was successful."])
        with pymupdf.open(self.output) as doc:
            self.assertIn("Example author", doc[0].get_text())
            self.assertIn("continued English citation", doc[1].get_text())

    def test_independent_batches_can_translate_concurrently(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=1200)
            for y in (100, 400, 700, 1000):
                page.insert_textbox((40, y, 550, y + 150), "A scientific result was observed. " * 30, fontsize=10)
            doc.save(self.source)
        barrier = Barrier(2, timeout=5)

        def translate(texts: list[str]) -> list[str]:
            barrier.wait()
            return ["結果。" for _ in texts]

        self.assertEqual(translate_pdf(self.source, self.output, translate), (1, 4))

    def test_short_pages_are_submitted_before_waiting_for_first_translation(self) -> None:
        with pymupdf.open() as doc:
            for _ in range(2):
                page = doc.new_page(width=400, height=600)
                page.insert_text((40, 100), "The experiment was successful.", fontsize=11)
            doc.save(self.source)
        barrier = Barrier(2, timeout=5)

        def translate(texts: list[str]) -> list[str]:
            barrier.wait()
            return ["実験は成功した。"]

        self.assertEqual(translate_pdf(self.source, self.output, translate), (2, 2))

    def test_small_footer_stays_clear_of_translated_body(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page(width=360, height=400)
            page.insert_textbox((40, 65, 320, 125), "The study examined the results of the experiment. " * 4, fontsize=10)
            page.insert_text((40, 220), "JOURNAL 2026", fontsize=6)
            doc.save(self.source)
        translate_pdf(self.source, self.output, Mock(return_value=["実験結果を詳しく調査した。" * 15]))
        with pymupdf.open(self.output) as doc:
            page = doc[0]
            self.assertIn("JOURNAL 2026", page.get_text())
            japanese = page.search_for("実験結果")
            self.assertTrue(japanese)
            self.assertLess(japanese[-1].y1, page.search_for("JOURNAL")[0].y0)

    def test_original_block_sizes_and_weights_are_preserved_when_they_fit(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page(width=500, height=650)
            page.insert_text((40, 75), "A Scientific Study", fontname="hebo", fontsize=21)
            page.insert_text((40, 125), "Haneen Example, Member, IEEE, Joseph Example", fontsize=11)
            page.insert_text((40, 205), "Abstract. The first result was significant.", fontname="hebo", fontsize=9)
            page.insert_text((40, 305), "The explanatory note is smaller.", fontname="tiro", fontsize=8)
            page.insert_text((40, 405), "The main body has its own size.", fontname="tiro", fontsize=10)
            doc.save(self.source)
        translator = Mock(return_value=["日本語の科学的研究", "要旨：結果は有意だった。", "補足の説明。", "本文は別の大きさ。"])
        self.assertEqual(translate_pdf(self.source, self.output, translator), (1, 4))
        with pymupdf.open(self.output) as doc:
            page = doc[0]
            self.assertIn("Haneen Example", page.get_text())
            spans = [span for block in page.get_text("dict")["blocks"] if block["type"] == 0
                     for line in block["lines"] for span in line["spans"]]
            def matching(needle: str) -> dict:
                return next(span for span in spans if needle in span["text"])
            title = matching("日本語の科学的研究")
            abstract = matching("要旨")
            note = matching("補足")
            body = matching("本文は")
            self.assertIn("Noto Sans JP Bold", title["font"])
            self.assertIn("Noto Sans JP Bold", abstract["font"])
            self.assertIn("Noto Serif JP Regular", note["font"])
            self.assertEqual([round(s["size"]) for s in (title, abstract, note, body)], [21, 9, 8, 10])
            self.assertLess(page.search_for("日本語の科学的研究")[0].y1, page.search_for("Haneen Example")[0].y0)


if __name__ == "__main__":
    unittest.main()
