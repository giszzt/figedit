#!/usr/bin/env python3
"""Gate read_figure.py against finished tasks: did it put a number on every object?

Ground truth is the final manifest of a past task -- every asset it cropped or
regenerated, plus every drawn shape, is something the model actually needed.

Two different questions, deliberately scored apart:

  pointable   is there ANY candidate sitting on this object, so the model can
              refer to it by id? This is the gate. A miss here sends the model
              back to hand measurement, which is the cost this whole change
              exists to remove.
  boxed       is the candidate's box already pixel-accurate (IoU >= 0.6)? Not a
              gate. snap_boxes tightens boxes downstream, and the corpus shows
              the two granularities usually bracket the right answer.

The third number is candidate count. The atlas is only useful if a person can
read it, so an unbounded candidate list fails even at perfect recall.

Usage:
  python tests/eval_read_figure.py --root D:/AI_Ocean/Claude
  python tests/eval_read_figure.py --root . --cap 90 --json out.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

GATE_POINTABLE = 0.99
GATE_POINTABLE_PER_TASK = 0.90
GATE_MAX_CANDIDATES = 130
SHAPE_TYPES = {"rect", "circle", "ellipse", "polygon"}


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    return inter / float(aw * ah + bw * bh - inter)


def coverage(truth, cand) -> tuple[float, float]:
    tx, ty, tw, th = truth
    cx, cy, cw, ch = cand
    x0, y0 = max(tx, cx), max(ty, cy)
    x1, y1 = min(tx + tw, cx + cw), min(ty + th, cy + ch)
    if x1 <= x0 or y1 <= y0:
        return 0.0, 0.0
    inter = (x1 - x0) * (y1 - y0)
    return inter / float(tw * th), inter / float(cw * ch)


def truth_boxes(manifest: dict) -> list[tuple[str, str, list[int]]]:
    out = []
    for a in manifest.get("assets", []) or []:
        sr = a.get("source_region")
        if not sr or a.get("kind") == "background-plate":
            continue
        if a.get("decision") in {"generate-replacement"}:
            continue
        out.append((a.get("id", "?"), a.get("decision", "?"), [sr["x"], sr["y"], sr["w"], sr["h"]]))
    for e in manifest.get("elements", []) or []:
        if e.get("type") not in SHAPE_TYPES:
            continue
        x, y = e.get("x"), e.get("y")
        w, h = e.get("w"), e.get("h")
        if None in (x, y, w, h) or w < 8 or h < 8:
            continue
        out.append((e.get("id", "?"), "draw:" + e["type"], [int(x), int(y), int(w), int(h)]))
    return out


def find_source(task_dir: Path, canvas: dict):
    from PIL import Image
    for pattern in ("input.*", "source.*", "work/assets/source.*", "assets/source.*"):
        for p in sorted(task_dir.glob(pattern)):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                continue
            try:
                with Image.open(p) as im:
                    if im.size == (int(canvas["width"]), int(canvas["height"])):
                        return p
            except Exception:
                continue
    return None


def discover(root: Path) -> list[dict]:
    samples = []
    for mp in sorted(root.glob("*/manifest.json")) + sorted(root.glob("*/*/manifest.json")):
        if mp.parent.name in {"out", "output", "work"}:
            continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            continue
        canvas = m.get("canvas") or {}
        if not canvas.get("width") or not m.get("elements"):
            continue
        img = find_source(mp.parent, canvas)
        if img is None:
            continue
        samples.append({"name": mp.parent.name, "manifest": mp, "image": img, "dir": mp.parent})
    return samples


def sibling(task_dir: Path, name: str):
    for c in (task_dir / "work" / name, task_dir / "figure-task" / "work" / name):
        if c.is_file():
            return c
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--cap", type=int, default=GATE_MAX_CANDIDATES)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--only", help="substring filter on task name")
    args = ap.parse_args()

    # Parked, not wired in: it did not pass this gate. See parked/README.md.
    script = Path(__file__).resolve().parent.parent / "parked" / "read_figure.py"
    samples = discover(args.root)
    if args.only:
        samples = [s for s in samples if args.only in s["name"]]
    if not samples:
        print("no corpus samples found", file=sys.stderr)
        return 2

    rows = []
    tmp = Path(tempfile.mkdtemp(prefix="readfig_"))
    print(f"{'task':26s}{'真值':>5}{'候选':>6}{'能指到':>9}{'框准':>8}{'秒':>7}")
    print("-" * 68)
    for s in samples:
        manifest = json.loads(s["manifest"].read_text(encoding="utf-8"))
        truth = truth_boxes(manifest)
        if len(truth) < 3:
            continue
        out = tmp / f"{s['name']}.json"
        cmd = [sys.executable, str(script), str(s["image"]), "--out", str(out),
               "--cap", str(args.cap), "--quiet"]
        ocr = sibling(s["dir"], "ocr_results.json")
        geo = sibling(s["dir"], "geometry.json")
        if ocr:
            cmd += ["--ocr", str(ocr)]
        if geo:
            cmd += ["--geometry", str(geo)]
        import time
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - t0
        if proc.returncode != 0 or not out.is_file():
            print(f"{s['name'][:25]:26s}  FAILED  {proc.stderr.strip()[:60]}")
            continue
        ev = json.loads(out.read_text(encoding="utf-8"))
        # Anything carrying an id is pointable: a panel region and a text slot are
        # as nameable as a shape candidate, and area-level truths (preserve-raster
        # regions, background fields) are supposed to land on regions[], not on a
        # blob. Scoring only objects[] would fail the pipeline for doing the right
        # thing. Shape-only recall is kept alongside for diagnosis.
        shapes = [o["bbox"] for o in ev["objects"]]
        cands = shapes + [r["bbox"] for r in ev.get("regions", [])] + [t["bbox"] for t in ev.get("text_slots", [])]
        pointable = boxed = 0
        misses = []
        for tid, dec, tb in truth:
            best_iou = max((iou(tb, c) for c in cands), default=0.0)
            best_cov = max((coverage(tb, c)[0] for c in cands), default=0.0)
            inside = any(coverage(tb, c)[1] > 0.85 and coverage(tb, c)[0] > 0.15 for c in cands)
            if best_iou >= 0.6:
                boxed += 1
            if best_iou >= 0.6 or best_cov >= 0.4 or inside:
                pointable += 1
            else:
                misses.append((tid, dec, round(best_iou, 2), round(best_cov, 2)))
        n = len(truth)
        abst = bool(ev.get("abstained"))
        rows.append({"name": s["name"], "truth": n, "cands": len(cands), "shapes": len(shapes),
                     "pointable": pointable, "boxed": boxed, "misses": misses, "abstained": abst,
                     "flat": ev.get("image_profile", {}).get("flat_design_score"),
                     "seconds": round(elapsed, 1), "funnel": ev.get("funnel")})
        mark = "弃权" if abst else "    "
        print(f"{s['name'][:25]:26s}{n:5d}{len(shapes):6d}{100.0*pointable/n:8.1f}%{100.0*boxed/n:7.1f}%{elapsed:7.1f}  {mark}")

    if not rows:
        print("no scorable samples", file=sys.stderr)
        return 2

    # Gates apply to figures the script claims it can read. An abstained figure is
    # a correct refusal, not a miss -- scoring it as failure would push the fix
    # toward emitting confident garbage on photographs, which is the one outcome
    # that costs the model more than measuring by hand.
    live = [r for r in rows if not r["abstained"]]
    held = [r for r in rows if r["abstained"]]
    if not live:
        print("every sample abstained; nothing to gate", file=sys.stderr)
        return 1
    tp = sum(r["pointable"] for r in live)
    tb_ = sum(r["boxed"] for r in live)
    tt = sum(r["truth"] for r in live)
    worst = min(live, key=lambda r: r["pointable"] / r["truth"])
    maxc = max(r["shapes"] for r in live)
    slowest = max(r["seconds"] for r in rows)
    print("-" * 74)
    print(f"{'受门约束的图':24s}{tt:5d}{maxc:6d}{100.0*tp/tt:8.1f}%{100.0*tb_/tt:7.1f}%{slowest:7.1f}")
    if held:
        ht = sum(r["truth"] for r in held)
        hp = sum(r["pointable"] for r in held)
        print(f"{'弃权的图（不计门）':22s}{ht:5d}{'':6s}{100.0*hp/ht:8.1f}%   {len(held)} 张")

    print("\n门（只对声称读得了的图）：")
    checks = [
        ("总能指到 >= 99%", tp / tt >= GATE_POINTABLE, f"{100.0*tp/tt:.1f}%"),
        (f"单任务能指到 >= {GATE_POINTABLE_PER_TASK:.0%}", worst["pointable"] / worst["truth"] >= GATE_POINTABLE_PER_TASK,
         f"最差 {worst['name']} {100.0*worst['pointable']/worst['truth']:.1f}%"),
        (f"候选数 <= {GATE_MAX_CANDIDATES}", maxc <= GATE_MAX_CANDIDATES, f"最多 {maxc}"),
        ("单图 <= 90 秒", slowest <= 90, f"最慢 {slowest:.1f}s"),
    ]
    ok = True
    for label, passed, detail in checks:
        print(f"  {'通过' if passed else '不通过'}  {label:28s} {detail}")
        ok = ok and passed

    misses = [(r["name"], m) for r in rows for m in r["misses"]]
    if misses:
        print(f"\n漏掉 {len(misses)} 个（调参就看这些）：")
        for name, (tid, dec, bi, bc) in misses[:20]:
            print(f"  {name[:18]:19s} {tid[:30]:31s} {dec:16s} iou{bi} cov{bc}")

    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n明细 {args.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
