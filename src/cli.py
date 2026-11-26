"""Command-line entry point for PaperShift."""

import argparse
from importlib.metadata import version


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pshift",
        description="PDF翻訳ツール（翻訳機能は今後実装予定）",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('paper-shift')}",
    )
    parser.parse_args()
