#!/usr/bin/env python3
"""Render an SVG preview PNG with CairoSVG if available.

Usage:
  python scripts/render_svg_preview.py editable.svg --out preview.png
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("--out", type=Path, default=Path("preview.png"))
    args = parser.parse_args()

    try:
        import cairosvg
    except ImportError as exc:
        raise SystemExit("CairoSVG is not installed. Install with: pip install cairosvg") from exc

    cairosvg.svg2png(url=str(args.svg), write_to=str(args.out))
    print(f"Preview written to: {args.out}")


if __name__ == "__main__":
    main()
