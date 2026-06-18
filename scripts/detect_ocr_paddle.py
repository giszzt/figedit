#!/usr/bin/env python3
"""PaddleOCR adapter for editable SVG reconstruction."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def _bbox_from_poly(poly: list[list[float]]) -> dict[str, float]:
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}


def _normalize_classic_result(raw: Any) -> list[dict[str, Any]]:
    """Normalize PaddleOCR v2-style output into stable records."""
    if not raw:
        return []
    page = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
    records: list[dict[str, Any]] = []
    for idx, item in enumerate(page or []):
        try:
            poly = [[float(x), float(y)] for x, y in item[0]]
            text = str(item[1][0])
            confidence = float(item[1][1])
        except Exception:
            continue
        records.append(
            {
                "id": f"ocr-text-{idx:04d}",
                "text": text,
                "confidence": confidence,
                "polygon": poly,
                "bbox": _bbox_from_poly(poly),
                "engine": "paddleocr",
                "review_status": "ok" if confidence >= 0.82 else "low-confidence",
            }
        )
    return records


def _plain_result(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, type(None))):
        return obj
    if isinstance(obj, dict):
        return {k: _plain_result(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain_result(v) for v in obj]
    if hasattr(obj, "tolist"):
        try:
            return obj.tolist()
        except Exception:
            pass
    for name in ("to_dict", "dict"):
        method = getattr(obj, name, None)
        if callable(method):
            try:
                return _plain_result(method())
            except Exception:
                pass
    json_value = getattr(obj, "json", None)
    if isinstance(json_value, dict):
        return _plain_result(json_value)
    if callable(json_value):
        try:
            return _plain_result(json_value())
        except Exception:
            pass
    data = getattr(obj, "__dict__", None)
    if isinstance(data, dict):
        return {k: _plain_result(v) for k, v in data.items() if not k.startswith("_")}
    return str(obj)


def _poly_from_box(box: Any) -> list[list[float]]:
    values = _plain_result(box)
    if isinstance(values, list) and len(values) == 4 and all(not isinstance(v, list) for v in values):
        x1, y1, x2, y2 = [float(v) for v in values]
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if isinstance(values, list) and values and isinstance(values[0], list):
        return [[float(p[0]), float(p[1])] for p in values]
    return [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def _normalize_v3_result(raw: Any) -> list[dict[str, Any]]:
    pages = raw if isinstance(raw, list) else [raw]
    records: list[dict[str, Any]] = []
    for page in pages:
        data = _plain_result(page)
        if not isinstance(data, dict):
            continue
        texts = data.get("rec_texts") or data.get("texts") or data.get("text")
        scores = data.get("rec_scores") or data.get("scores") or data.get("confidence")
        polys = data.get("rec_polys") or data.get("dt_polys") or data.get("polys") or data.get("boxes")
        boxes = data.get("rec_boxes") or data.get("text_boxes")
        if isinstance(texts, str):
            texts = [texts]
        if not isinstance(texts, list):
            continue
        if not isinstance(scores, list):
            scores = [scores if scores is not None else 0.0] * len(texts)
        if not isinstance(polys, list):
            polys = boxes if isinstance(boxes, list) else []
        for text_idx, content in enumerate(texts):
            text_value = str(content).strip()
            if not text_value:
                continue
            score = float(scores[text_idx]) if text_idx < len(scores) and scores[text_idx] is not None else 0.0
            poly_source = polys[text_idx] if text_idx < len(polys) else [0, 0, 1, 1]
            poly = _poly_from_box(poly_source)
            records.append(
                {
                    "id": f"ocr-text-{len(records):04d}",
                    "text": text_value,
                    "confidence": score,
                    "polygon": poly,
                    "bbox": _bbox_from_poly(poly),
                    "engine": "paddleocr",
                    "review_status": "ok" if score >= 0.82 else "low-confidence",
                }
            )
    return records


def _normalize_result(raw: Any) -> list[dict[str, Any]]:
    classic = _normalize_classic_result(raw)
    if classic:
        return classic
    return _normalize_v3_result(raw)


def _ocr_init_attempts(profile: str, lang: str, use_gpu: bool) -> list[dict[str, Any]]:
    base = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": True,
    }
    if use_gpu:
        base["device"] = "gpu"

    profiles = {
        "v6_medium": {
            "text_detection_model_name": "PP-OCRv6_medium_det",
            "text_recognition_model_name": "PP-OCRv6_medium_rec",
        },
        "v6_small": {
            "text_detection_model_name": "PP-OCRv6_small_det",
            "text_recognition_model_name": "PP-OCRv6_small_rec",
        },
        "v6_tiny": {
            "text_detection_model_name": "PP-OCRv6_tiny_det",
            "text_recognition_model_name": "PP-OCRv6_tiny_rec",
        },
        "v5_mobile": {
            "lang": lang,
            "text_detection_model_name": "PP-OCRv5_mobile_det",
            "text_recognition_model_name": "PP-OCRv5_mobile_rec",
        },
    }

    attempts: list[dict[str, Any]] = []
    if profile in profiles:
        attempts.append({**base, **profiles[profile], "_profile": profile})
    elif profile != "auto":
        attempts.append({**base, **profiles["v6_medium"], "_profile": "v6_medium"})

    # PaddleOCR 3.7+ defaults to PP-OCRv6_medium. Keep this generic attempt so
    # newer patch releases can select their own best default configuration.
    attempts.append({**base, "_profile": "paddleocr_default"})
    attempts.append({**base, **profiles["v5_mobile"], "_profile": "v5_mobile"})
    attempts.append({"lang": lang, "_profile": "legacy_lang_default"})
    return attempts


def run_ocr(image_path: Path, lang: str = "ch", use_gpu: bool = False, profile: str = "v6_medium") -> dict[str, Any]:
    """Run PaddleOCR if available; return an explicit disabled result otherwise."""
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("FLAGS_use_onednn", "0")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except Exception as exc:
        return {
            "engine": "paddleocr",
            "status": "disabled",
            "error": f"PaddleOCR import failed: {exc}",
            "items": [],
        }

    try:
        init_attempts = _ocr_init_attempts(profile, lang, use_gpu)
        last_error: Exception | None = None
        selected_profile = None
        selected_models: dict[str, Any] = {}
        raw = None
        for kwargs in init_attempts:
            attempt_profile = str(kwargs.pop("_profile", "unknown"))
            try:
                ocr = PaddleOCR(**kwargs)
                if hasattr(ocr, "predict"):
                    raw = ocr.predict(str(image_path))
                else:
                    raw = ocr.ocr(str(image_path), cls=True)
                selected_profile = attempt_profile
                selected_models = {
                    "text_detection_model_name": kwargs.get("text_detection_model_name"),
                    "text_recognition_model_name": kwargs.get("text_recognition_model_name"),
                }
                break
            except Exception as exc:
                last_error = exc
                raw = None
        if raw is None:
            raise RuntimeError(f"All PaddleOCR attempts failed: {last_error!r}")
        items = _normalize_result(raw)
        return {
            "engine": "paddleocr",
            "status": "ok",
            "lang": lang,
            "use_gpu": use_gpu,
            "requested_profile": profile,
            "selected_profile": selected_profile,
            "selected_models": selected_models,
            "items": items,
            "count": len(items),
        }
    except Exception as exc:
        return {
            "engine": "paddleocr",
            "status": "failed",
            "error": repr(exc),
            "items": [],
        }


def save_ocr_outputs(image_path: Path, out_json: Path, overlay_path: Path, lang: str = "ch", use_gpu: bool = False, profile: str = "v6_medium") -> dict[str, Any]:
    result = run_ocr(image_path, lang=lang, use_gpu=use_gpu, profile=profile)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for item in result.get("items", []):
        poly = [tuple(p) for p in item.get("polygon", [])]
        if len(poly) >= 3:
            color = (0, 180, 255, 70) if item.get("review_status") == "ok" else (255, 160, 0, 100)
            draw.polygon(poly, outline=(0, 110, 220, 255), fill=color)
        bbox = item.get("bbox", {})
        draw.text((bbox.get("x", 0), bbox.get("y", 0)), item.get("text", "")[:24], fill=(0, 70, 180))
    image.save(overlay_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, default=Path("ocr_results.json"))
    parser.add_argument("--overlay", type=Path, default=Path("diagnostics/ocr_overlay.png"))
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--profile", default="v6_medium", choices=["auto", "v6_medium", "v6_small", "v6_tiny", "v5_mobile"])
    args = parser.parse_args()
    result = save_ocr_outputs(args.image, args.out, args.overlay, lang=args.lang, use_gpu=args.gpu, profile=args.profile)
    print(json.dumps({"status": result.get("status"), "profile": result.get("selected_profile"), "count": len(result.get("items", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
