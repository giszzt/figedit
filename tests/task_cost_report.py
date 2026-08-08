#!/usr/bin/env python3
"""Where did a finished figedit task's wall-clock time actually go?

Wall time is round trips times model latency; script compute is a rounding error
next to it (a whole compose is single-digit seconds). So the number that decides
whether a change worked is how many times the model had to stop and ask, and
what it was asking for. Only the session transcript records that -- a counter
inside the pipeline cannot see the calls that bypass the pipeline, which are
exactly the ones worth removing.

Run it after a task to check a change against its target, instead of re-reading
the conversation by hand.

Usage:
  python tests/task_cost_report.py                     # newest figedit sessions
  python tests/task_cost_report.py --last 5 --detail
  python tests/task_cost_report.py --dir <transcript dir> --session 0816be32
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_DIR = Path.home() / ".claude" / "projects"
PIPELINE = {
    "prepare_measurements.py", "probe_geometry.py", "measure.py", "snap_boxes.py",
    "inspect_regions.py", "crop_assets.py", "draft_elements.py", "manifest_edit.py",
    "compose_svg_package.py", "fit_text.py", "pptx_text_fit.py", "render_pptx.py",
    "validate_manifest.py", "quality_audit.py", "audit_editability.py", "fix_worklist.py",
    "probe_palette.py", "chroma_key.py", "slice_grid.py", "generate_clean_plate.py",
    "prepare_clean_plate_mask.py", "check_plate_registration.py", "build_svg_from_manifest.py",
}


def parse(path: Path) -> list[dict]:
    out = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    return out


def stamp(rec: dict):
    try:
        return datetime.datetime.fromisoformat(rec["timestamp"].replace("Z", "+00:00"))
    except Exception:
        return None


def bucket(name: str, inp: dict) -> str:
    """Group a call by what it cost the task, not by which tool it used."""
    if name in {"Bash", "PowerShell"}:
        cmd = inp.get("command") or ""
        m = re.search(r"scripts[/\\]([a-z_0-9]+\.py)", cmd)
        if m:
            return ("管线 " if m.group(1) in PIPELINE else "非管线脚本 ") + m.group(1)
        if re.search(r"python[a-z0-9]*\s+-c|python\s*-\s*<<|<<\s*'?PY", cmd):
            return "即兴测量 python -c"
        m = re.search(r"python[a-z0-9]*\s+[\"']?([^\s\"';|]+\.py)", cmd)
        if m:
            return "临时脚本 " + os.path.basename(m.group(1))
        return "其他 shell"
    if name == "Read":
        p = (inp.get("file_path") or "").lower()
        return "看图" if p.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) else "读文件"
    if name in {"Write", "Edit"}:
        return f"写文件 {name}"
    return name


def analyse(path: Path) -> dict | None:
    recs = parse(path)
    if not recs:
        return None
    events = []
    for r in recs:
        if r.get("type") != "assistant":
            continue
        content = r.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        ts = stamp(r)
        if ts is None:
            continue
        for c in content:
            if c.get("type") == "tool_use":
                events.append((ts, bucket(c.get("name", ""), c.get("input", {}) or {})))
    if len(events) < 8:
        return None
    blob = json.dumps(recs[:80], ensure_ascii=False)
    if "figedit" not in blob.lower():
        return None

    gaps: collections.Counter = collections.Counter()
    counts: collections.Counter = collections.Counter()
    for i, (ts, b) in enumerate(events):
        counts[b] += 1
        if i:
            d = (ts - events[i - 1][0]).total_seconds()
            gaps[b] += d if 0 <= d <= 1800 else 0.0
    span = (events[-1][0] - events[0][0]).total_seconds() / 60.0
    improvised = sum(v for k, v in counts.items() if k.startswith(("即兴测量", "临时脚本")))
    return {
        "session": path.stem[:8],
        "start": events[0][0],
        "minutes": span,
        "calls": len(events),
        "improvised": improvised,
        "images": counts.get("看图", 0),
        "counts": counts,
        "gaps": gaps,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, help="transcript directory (default: newest under ~/.claude/projects)")
    ap.add_argument("--last", type=int, default=6)
    ap.add_argument("--session", help="only sessions whose id starts with this")
    ap.add_argument("--detail", action="store_true", help="per-bucket time for each task")
    args = ap.parse_args()

    root = args.dir
    if root is None:
        if not DEFAULT_DIR.is_dir():
            print(f"transcript directory not found: {DEFAULT_DIR}", file=sys.stderr)
            return 2
        dirs = sorted((d for d in DEFAULT_DIR.iterdir() if d.is_dir()),
                      key=lambda d: d.stat().st_mtime, reverse=True)
        if not dirs:
            print("no project transcripts found", file=sys.stderr)
            return 2
        root = dirs[0]

    files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if args.session:
        files = [f for f in files if f.stem.startswith(args.session)]
    rows = []
    for f in files:
        if len(rows) >= args.last:
            break
        r = analyse(f)
        if r:
            rows.append(r)
    if not rows:
        print("no figedit tasks found in transcripts", file=sys.stderr)
        return 2

    print(f"{'会话':10s}{'开始':12s}{'分钟':>6}{'调用':>6}{'即兴测量':>9}{'看图':>6}")
    print("-" * 52)
    for r in rows:
        print(f"{r['session']:10s}{r['start']:%m-%d %H:%M}{r['minutes']:7.0f}{r['calls']:6d}"
              f"{r['improvised']:9d}{r['images']:6d}")
    print("-" * 52)
    n = len(rows)
    print(f"{'平均':10s}{'':12s}{sum(r['minutes'] for r in rows)/n:7.0f}"
          f"{sum(r['calls'] for r in rows)/n:6.0f}{sum(r['improvised'] for r in rows)/n:9.1f}"
          f"{sum(r['images'] for r in rows)/n:6.1f}")

    print("\n目标：分钟 ≤25   调用 ≤45   即兴测量 ≤3   看图 ≤12")

    if args.detail:
        for r in rows:
            total = sum(r["gaps"].values()) or 1.0
            print(f"\n=== {r['session']}  {r['minutes']:.0f} 分钟  {r['calls']} 次调用")
            for k, v in sorted(r["gaps"].items(), key=lambda kv: -kv[1])[:10]:
                print(f"  {k:32s}{r['counts'][k]:4d} 次{v/60:7.1f} 分{100*v/total:6.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
