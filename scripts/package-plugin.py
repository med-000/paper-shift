"""Assemble a skills-only plugin ZIP with the exact CLI PDF engine and fonts."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins"
OUTPUT = ROOT / "dist" / "paper-shift-plugin.zip"
FILES = {
    "plugin.json": PLUGIN / "plugin.json",
    "assets/icon.svg": PLUGIN / "assets/icon.svg",
    "LICENSE": ROOT / "LICENSE",
    "skills/translate-paper/SKILL.md": PLUGIN / "skills/translate-paper/SKILL.md",
    "scripts/pdf_bridge.py": PLUGIN / "scripts/pdf_bridge.py",
    "vendor/src/__init__.py": ROOT / "src/__init__.py",
    "vendor/src/pdf.py": ROOT / "src/pdf.py",
    **{f"vendor/src/fonts/{path.name}": path for path in (ROOT / "src/fonts").glob("*.ttf")},
    **{f"vendor/src/fonts/{path.name}": path for path in (ROOT / "src/fonts").glob("OFL-*.txt")},
    "vendor/src/fonts/README.md": ROOT / "src/fonts/README.md",
}


def package(output: Path = OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, path in sorted(FILES.items()):
            archive.write(path, f"paper-shift/{name}")
    return output


if __name__ == "__main__":
    print(package())
