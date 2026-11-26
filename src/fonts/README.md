# Bundled Japanese fonts

PaperShift includes static instances of the following open-source fonts so PDF output looks the same on macOS and Windows:

- `NotoSansJP-Regular.ttf` and `NotoSansJP-Bold.ttf`: generated from [Noto Sans JP](https://github.com/google/fonts/tree/main/ofl/notosansjp) at `wght=400` and `wght=700`.
- `NotoSerifJP-Regular.ttf`: generated from [Noto Serif JP](https://github.com/google/fonts/tree/main/ofl/notoserifjp) at `wght=400`.

The static instances were made with FontTools varLib.instancer and updated with matching family/style metadata. Both font families retain their own SIL Open Font License 1.1 terms; see `OFL-NotoSansJP.txt` and `OFL-NotoSerifJP.txt`. The licenses do not apply to PDFs generated with these fonts.
