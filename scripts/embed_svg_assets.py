#!/usr/bin/env python3
"""Embed local raster assets in an SVG as base64 data URIs.

Usage:
  python scripts/embed_svg_assets.py editable.svg --base . --out editable_embedded.svg
"""
from __future__ import annotations

import argparse
import base64
import mimetypes
import re
from pathlib import Path


HREF_RE = re.compile(r'href="([^"]+)"')


def embed(svg_path: Path, base_dir: Path, out_path: Path) -> None:
    text = svg_path.read_text(encoding="utf-8")

    def repl(match: re.Match) -> str:
        href = match.group(1)
        if href.startswith("data:") or href.startswith("http://") or href.startswith("https://"):
            return match.group(0)
        asset_path = (base_dir / href).resolve()
        if not asset_path.exists():
            return match.group(0)
        mime = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
        return f'href="data:{mime};base64,{data}"'

    out_path.write_text(HREF_RE.sub(repl, text), encoding="utf-8")
    print(f"Embedded SVG written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("--base", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("editable_embedded.svg"))
    args = parser.parse_args()
    embed(args.svg, args.base, args.out)


if __name__ == "__main__":
    main()
