#!/usr/bin/env python3
"""Offline evaluation of probe_geometry.py against a corpus of finished tasks.

Each corpus sample is a past task directory holding the source image plus the
final, human-owned manifest.json. The final manifest is the ground truth: every
element in it survived visual review, so a candidate that lands on one is a
candidate the model would have accepted.

The gates (§6.1 of the 0.8.0 plan) are deliberately asymmetric:

  precision       weighted >= 0.80. Precision is the one property that should
                  hold constant across figure types.
  abstention      on clean-plate samples (ground-truth rect count <= 1) the
                  probe must emit <= 5 fill candidates. This gate exists to
                  stop anyone from chasing coverage by inventing candidates.
  no regression   handled by the per-batch regression run, not here.

Recall is reported per category but is NOT a gate. A poster has no panels to
find; low recall there is correct behavior, not failure.

Scoping, and why it is not the same as lowering the bar: a final manifest
records a *route choice*, not the geometry of the image. 11 of the 29 corpus
samples draw no panels at all — they preserved that region as raster or
regenerated it — so a correct panel candidate there is unconfirmable rather
than wrong. Each candidate type is therefore scored only on samples whose
manifest used that type at all. Where the ground truth cannot answer, the
sample is excluded from the denominator and counted in `unscoreable`, never
counted as a pass.

Usage:
  python tests/eval_geometry.py                 # discover corpus, run gates
  python tests/eval_geometry.py --corpus x.json # explicit sample list
  python tests/eval_geometry.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
PROBE = SKILL_DIR / "scripts" / "probe_geometry.py"

IOU_THRESHOLD = 0.70
PERP_TOLERANCE = 3.0          # a hairline may sit this far off its ground-truth line
LINE_OVERLAP_THRESHOLD = 0.70
COLOR_TOLERANCE = 40.0        # euclidean RGB
FONT_SIZE_TOLERANCE = 3.0     # px
THICKNESS_TOLERANCE = 3.0     # px
CLEAN_PLATE_RECT_MAX = 1      # ground-truth rects at or below this => clean-plate sample
ABSTAIN_FILL_CAP = 5
PRECISION_GATE = 0.80
PANELS_DRAWN_MIN = 5          # panel candidates are scoreable only if the manifest drew panels
SLOTS_SCOREABLE_MIN = 10      # slots are scoreable only if the text was retyped, not flattened

STRUCTURAL_LINE_TYPES = {"line", "polyline", "path"}


# --- geometry helpers -------------------------------------------------------

def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _rgb(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, str) or not value.startswith("#"):
        return None
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _color_close(a: Any, b: Any) -> bool:
    ra, rb = _rgb(a), _rgb(b)
    if ra is None or rb is None:
        return True  # no color to compare on => don't punish the candidate
    return sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5 <= COLOR_TOLERANCE


# --- ground truth extraction ------------------------------------------------

def truth_boxes(manifest: dict) -> dict[str, list[dict]]:
    rects: list[dict] = []
    lines: list[dict] = []
    texts: list[dict] = []
    for element in manifest.get("elements", []):
        etype = element.get("type")
        if etype == "rect":
            try:
                box = (float(element["x"]), float(element["y"]), float(element["w"]), float(element["h"]))
            except (KeyError, TypeError, ValueError):
                continue
            thin = min(box[2], box[3]) <= 7 and max(box[2], box[3]) >= 30
            entry = {"box": box, "fill": element.get("fill"), "stroke": element.get("stroke")}
            (lines if thin else rects).append(entry)
        elif etype in STRUCTURAL_LINE_TYPES:
            box = _line_box(element)
            if box:
                lines.append({"box": box, "fill": element.get("stroke"), "width": element.get("stroke_width")})
        elif etype == "text":
            try:
                x, y = float(element["x"]), float(element["y"])
            except (KeyError, TypeError, ValueError):
                continue
            texts.append(
                {
                    "x": x,
                    "baseline_y": y,
                    "text": str(element.get("text", "")),
                    "font_size": element.get("font_size"),
                    "fill": element.get("fill"),
                    "anchor": element.get("text_anchor") or element.get("anchor"),
                }
            )
    return {"rects": rects, "lines": lines, "texts": texts}


def _line_box(element: dict) -> tuple[float, float, float, float] | None:
    if element.get("type") == "line":
        try:
            x1, y1 = float(element["x1"]), float(element["y1"])
            x2, y2 = float(element["x2"]), float(element["y2"])
        except (KeyError, TypeError, ValueError):
            return None
        width = float(element.get("stroke_width", 1) or 1)
        return (
            min(x1, x2) - width / 2,
            min(y1, y2) - width / 2,
            abs(x2 - x1) + width,
            abs(y2 - y1) + width,
        )
    points = element.get("points")
    if isinstance(points, str):
        nums: list[float] = []
        for chunk in points.replace(",", " ").split():
            try:
                nums.append(float(chunk))
            except ValueError:
                pass
        if len(nums) >= 4:
            xs, ys = nums[0::2], nums[1::2]
            return (min(xs), min(ys), max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0)
    return None


# --- matching ---------------------------------------------------------------

def match_fills(candidates: list[dict], truth: list[dict]) -> tuple[int, int]:
    used = [False] * len(truth)
    hits = 0
    for candidate in candidates:
        box = tuple(candidate["bbox"])
        best, best_iou = None, 0.0
        for index, target in enumerate(truth):
            if used[index]:
                continue
            value = _iou(box, target["box"])
            if value > best_iou:
                best, best_iou = index, value
        if best is not None and best_iou >= IOU_THRESHOLD:
            target = truth[best]
            if _color_close(candidate.get("color"), target.get("fill") or target.get("stroke")):
                used[best] = True
                hits += 1
    return hits, sum(used)


def match_rules(candidates: list[dict], truth: list[dict]) -> tuple[int, int]:
    """Match hairlines by colinearity, not IoU.

    IoU is the wrong metric for a 1px object: a one-pixel offset between a
    candidate and its ground-truth line drops IoU to 0.33 even though the two
    are visually the same line. Colinear overlap is the honest test.
    """
    used = [False] * len(truth)
    hits = 0
    for candidate in candidates:
        horizontal = candidate["orient"] == "h"
        c_long = (candidate["x1"], candidate["x2"]) if horizontal else (candidate["y1"], candidate["y2"])
        c_perp = (candidate["y1"] + candidate["y2"]) / 2 if horizontal else (candidate["x1"] + candidate["x2"]) / 2
        best, best_overlap = None, 0.0
        for index, target in enumerate(truth):
            if used[index]:
                continue
            tx, ty, tw, th = target["box"]
            t_horizontal = tw >= th
            if t_horizontal != horizontal:
                continue
            t_long = (tx, tx + tw) if horizontal else (ty, ty + th)
            t_perp = ty + th / 2 if horizontal else tx + tw / 2
            if abs(t_perp - c_perp) > PERP_TOLERANCE:
                continue
            overlap = min(c_long[1], t_long[1]) - max(c_long[0], t_long[0])
            span = min(c_long[1] - c_long[0], t_long[1] - t_long[0]) or 1.0
            ratio = overlap / span
            if ratio > best_overlap:
                best, best_overlap = index, ratio
        if best is not None and best_overlap >= LINE_OVERLAP_THRESHOLD:
            target = truth[best]
            width = target.get("width")
            ok_width = width is None or abs(float(width) - candidate["thickness"]) <= THICKNESS_TOLERANCE
            if ok_width and _color_close(candidate.get("color"), target.get("fill")):
                used[best] = True
                hits += 1
    return hits, sum(used)


def match_slots(candidates: list[dict], truth: list[dict]) -> tuple[int, int, int]:
    """Score a slot only where the same string exists in the final manifest.

    A slot carries no invention risk — it is OCR, which the model runs
    unconditionally, repackaged with a font size and a color. What it can get
    *wrong* is those two estimates, so scoring is: find the manifest text with
    the same string, then check font_size and fill. Slots whose string never
    made it into the manifest (flattened into a clean plate, or merged across
    lines) are not scored either way; they are reported as unscored.

    Returns (hits, covered_truth, scored).
    """
    by_text: dict[str, list[int]] = {}
    for index, target in enumerate(truth):
        by_text.setdefault(target["text"].strip(), []).append(index)
    used: set[int] = set()
    hits = 0
    scored = 0
    for candidate in candidates:
        text = candidate.get("text", "").strip()
        pool = [i for i in by_text.get(text, []) if i not in used]
        if not text or not pool:
            continue
        x, y, w, h = candidate["bbox"]
        best = min(pool, key=lambda i: abs(truth[i]["baseline_y"] - (y + h * 0.8)))
        scored += 1
        target = truth[best]
        size = target.get("font_size")
        ok_size = size is None or abs(float(size) - candidate["font_size_est"]) <= FONT_SIZE_TOLERANCE
        if ok_size and _color_close(candidate.get("fill"), target.get("fill")):
            used.add(best)
            hits += 1
    return hits, len(used), scored


# --- corpus -----------------------------------------------------------------

def discover(root: Path) -> list[dict]:
    """Find task directories that pair a source image with a final manifest."""
    samples: list[dict] = []
    for manifest_path in sorted(root.glob("*/manifest.json")) + sorted(root.glob("*/*/manifest.json")):
        if "/out/" in manifest_path.as_posix() or manifest_path.parent.name in {"out", "output", "work"}:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        canvas = manifest.get("canvas") or {}
        if not canvas.get("width") or not manifest.get("elements"):
            continue
        image = _find_source(manifest_path.parent, canvas)
        if image is None:
            continue
        samples.append({"name": manifest_path.parent.name, "manifest": str(manifest_path), "image": str(image)})
    return samples


def _find_source(task_dir: Path, canvas: dict) -> Path | None:
    from PIL import Image

    candidates: list[Path] = []
    for pattern in ("work/assets/source.*", "assets/source.*", "work/source.*", "source.*", "input.*"):
        candidates.extend(sorted(task_dir.glob(pattern)))
    for path in candidates:
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            continue
        try:
            with Image.open(path) as im:
                if im.size == (int(canvas["width"]), int(canvas["height"])):
                    return path
        except Exception:
            continue
    return None


# --- driver -----------------------------------------------------------------

def evaluate(sample: dict, workdir: Path) -> dict:
    manifest = json.loads(Path(sample["manifest"]).read_text(encoding="utf-8"))
    truth = truth_boxes(manifest)
    ocr = _sibling_ocr(Path(sample["manifest"]).parent)

    out = workdir / f"{sample['name']}.geometry.json"
    cmd = [sys.executable, str(PROBE), sample["image"], "--out", str(out), "--quiet"]
    if ocr:
        cmd += ["--ocr", str(ocr)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"name": sample["name"], "error": (proc.stdout + proc.stderr).strip()[:400]}

    geometry = json.loads(out.read_text(encoding="utf-8"))
    fill_hits, fill_cov = match_fills(geometry["fill_regions"], truth["rects"])
    slot_hits, slot_cov, slot_scored = match_slots(geometry["text_slots"], truth["texts"])

    canvas = manifest.get("canvas") or {}
    area = float(canvas.get("width", 0)) * float(canvas.get("height", 0))
    panels_drawn = sum(1 for r in truth["rects"] if r["box"][2] * r["box"][3] > area * 0.01)
    fills_scoreable = panels_drawn >= PANELS_DRAWN_MIN
    slots_scoreable = slot_scored >= SLOTS_SCOREABLE_MIN

    candidates = (len(geometry["fill_regions"]) if fills_scoreable else 0) + (
        slot_scored if slots_scoreable else 0
    )
    hits = (fill_hits if fills_scoreable else 0) + (slot_hits if slots_scoreable else 0)
    truth_rects = len(truth["rects"])
    return {
        "name": sample["name"],
        "category": "clean-plate" if truth_rects <= CLEAN_PLATE_RECT_MAX else "structured",
        "flat_design_score": geometry["image_profile"]["flat_design_score"],
        "abstained": geometry["image_profile"]["abstained"],
        "panels_drawn": panels_drawn,
        "candidates": candidates,
        "hits": hits,
        "precision": round(hits / candidates, 3) if candidates else None,
        "fills": {"n": len(geometry["fill_regions"]), "hit": fill_hits, "truth": truth_rects,
                  "scoreable": fills_scoreable,
                  "recall": round(fill_cov / truth_rects, 3) if truth_rects else None},
        "slots": {"n": len(geometry["text_slots"]), "scored": slot_scored, "hit": slot_hits,
                  "truth": len(truth["texts"]), "scoreable": slots_scoreable,
                  "recall": round(slot_cov / len(truth["texts"]), 3) if truth["texts"] else None},
    }


def _sibling_ocr(task_dir: Path) -> Path | None:
    for pattern in ("work/ocr_results.json", "ocr_results.json", "out/ocr_results.json"):
        path = task_dir / pattern
        if path.exists():
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--corpus", type=Path, default=None, help="JSON list of {name, manifest, image}")
    parser.add_argument("--work", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    samples = (
        json.loads(args.corpus.read_text(encoding="utf-8"))
        if args.corpus
        else discover(args.root.resolve())
    )
    if not samples:
        print("no corpus samples found", file=sys.stderr)
        return 2

    workdir = (args.work or Path.cwd() / ".eval_geometry").resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    results = [evaluate(sample, workdir) for sample in samples]
    ok = [r for r in results if "error" not in r and r["precision"] is not None]

    total_candidates = sum(r["candidates"] for r in ok)
    total_hits = sum(r["hits"] for r in ok)
    weighted_precision = total_hits / total_candidates if total_candidates else 0.0

    print(f"{'sample':34} {'cat':11} {'flat':5} {'abst':5} {'cand':>5} {'prec':>5}  fills/slots recall")
    for r in results:
        if "error" in r:
            print(f"{r['name'][:34]:34} ERROR {r['error'][:80]}")
            continue
        rec = "/".join(
            "-" if not r[k]["scoreable"] or r[k]["recall"] is None else f"{r[k]['recall']:.2f}"
            for k in ("fills", "slots")
        )
        precision = "  -  " if r["precision"] is None else f"{r['precision']:.2f} "
        print(
            f"{r['name'][:34]:34} {r['category']:11} {r['flat_design_score']:.2f}  "
            f"{'Y' if r['abstained'] else 'n':^5} {r['candidates']:5} {precision}  {rec}"
        )

    fill_n = sum(r["fills"]["n"] for r in results if "error" not in r and r["fills"]["scoreable"])
    fill_h = sum(r["fills"]["hit"] for r in results if "error" not in r and r["fills"]["scoreable"])
    slot_n = sum(r["slots"]["scored"] for r in results if "error" not in r and r["slots"]["scoreable"])
    slot_h = sum(r["slots"]["hit"] for r in results if "error" not in r and r["slots"]["scoreable"])
    unscoreable = sum(1 for r in results if "error" not in r and r["precision"] is None)
    print()
    print(f"fills  {fill_h}/{fill_n} = {fill_h / fill_n if fill_n else 0:.3f}"
          f"   slots  {slot_h}/{slot_n} = {slot_h / slot_n if slot_n else 0:.3f}"
          f"   unscoreable samples: {unscoreable}")

    print()
    gates: list[tuple[str, bool, str]] = []
    gates.append(
        ("precision", weighted_precision >= PRECISION_GATE,
         f"weighted {weighted_precision:.3f} (gate >= {PRECISION_GATE})")
    )
    clean = [r for r in ok if r["category"] == "clean-plate"]
    over = [r for r in clean if r["fills"]["n"] > ABSTAIN_FILL_CAP]
    gates.append(
        ("abstention", not over,
         f"{len(clean)} clean-plate samples, {len(over)} emit > {ABSTAIN_FILL_CAP} fill candidates"
         + (": " + ", ".join(f"{r['name']}({r['fills']['n']})" for r in over) if over else ""))
    )
    for name, passed, detail in gates:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    if args.json:
        args.json.write_text(
            json.dumps({"results": results, "weighted_precision": weighted_precision}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0 if all(g[1] for g in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
