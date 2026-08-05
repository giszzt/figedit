#!/usr/bin/env python3
"""Shared pixel measurements for region tools (internal module, not an entry script).

Used by inspect_regions.py and snap_boxes.py. Answers pixel questions only:
background estimation, ink masks, tight boxes, edge occupancy. Semantic
decisions (what an object is, which route it takes) stay with the model.
"""

from __future__ import annotations

from typing import Any

import numpy as np

INK_DISTANCE = 40.0
UNIFORM_SHARE = 0.97


def dominant_border_color(arr: np.ndarray) -> tuple[np.ndarray, float]:
    """Estimate the background color from the border pixels of an RGB array.

    Returns (color as float array of 3, share of border pixels in that bucket).
    """
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], axis=0)
    quantized = (border // 16) * 16
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    mode_idx = int(np.argmax(counts))
    selected = (quantized == colors[mode_idx]).all(axis=1)
    dominant = border[selected].mean(axis=0).astype(float)
    share = float(counts[mode_idx]) / float(len(quantized))
    return dominant, share


def ink_mask(arr: np.ndarray, background: np.ndarray, threshold: float = INK_DISTANCE) -> np.ndarray:
    """Boolean mask of pixels that differ from the background color."""
    distance = np.sqrt(((arr.astype(float) - background) ** 2).sum(axis=2))
    return distance > threshold


def tight_bbox(mask: np.ndarray) -> list[int] | None:
    """[x1, y1, x2, y2] of true pixels, or None when the mask is empty."""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]


def edge_occupancy(mask: np.ndarray) -> dict[str, float]:
    if mask.size == 0:
        return {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0}
    return {
        "top": round(float(mask[0].mean()), 4),
        "bottom": round(float(mask[-1].mean()), 4),
        "left": round(float(mask[:, 0].mean()), 4),
        "right": round(float(mask[:, -1].mean()), 4),
    }


def uniformity(arr: np.ndarray, exclude: np.ndarray | None = None) -> dict[str, Any]:
    """Check whether pixels (minus an excluded mask) form one uniform flat color."""
    pixels = arr.reshape(-1, 3) if exclude is None else arr[~exclude]
    if len(pixels) == 0:
        return {"uniform": False, "color": None, "share": 0.0}
    quantized = (pixels // 16) * 16
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    mode_idx = int(np.argmax(counts))
    share = float(counts[mode_idx]) / float(len(pixels))
    selected = (quantized == colors[mode_idx]).all(axis=1)
    mean_color = pixels[selected].mean(axis=0)
    return {
        "uniform": share >= UNIFORM_SHARE,
        "color": rgb_hex(mean_color),
        "share": round(share, 4),
    }


def rgb_hex(color: np.ndarray | list[float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(round(float(v))))) for v in color])


def color_close(hex_a: str | None, hex_b: str | None, tolerance: float = INK_DISTANCE) -> bool:
    if not hex_a or not hex_b:
        return False
    a = np.array([int(hex_a[i : i + 2], 16) for i in (1, 3, 5)], dtype=float)
    b = np.array([int(hex_b[i : i + 2], 16) for i in (1, 3, 5)], dtype=float)
    return float(np.sqrt(((a - b) ** 2).sum())) <= tolerance


def mode_color(pixels: np.ndarray) -> tuple[np.ndarray, float]:
    """Dominant quantized color of a pixel list. Returns (color, bucket share)."""
    if len(pixels) == 0:
        return np.array([255.0, 255.0, 255.0]), 0.0
    quantized = (pixels // 16) * 16
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    mode_idx = int(np.argmax(counts))
    selected = (quantized == colors[mode_idx]).all(axis=1)
    return pixels[selected].mean(axis=0).astype(float), float(counts[mode_idx]) / float(len(pixels))


def ring_pixels(arr: np.ndarray, box: tuple[int, int, int, int], width: int) -> np.ndarray:
    """Pixels in a ring of the given width just outside a box, clipped to arr."""
    height, w_total = arr.shape[:2]
    x, y, w, h = box
    x1, y1 = max(0, x - width), max(0, y - width)
    x2, y2 = min(w_total, x + w + width), min(height, y + h + width)
    outer = arr[y1:y2, x1:x2]
    mask = np.ones(outer.shape[:2], dtype=bool)
    ix1, iy1 = x - x1, y - y1
    mask[max(0, iy1) : iy1 + h, max(0, ix1) : ix1 + w] = False
    return outer[mask]


def flat_share(pixels: np.ndarray, tolerance: float = 20.0) -> dict[str, Any]:
    """How flat a pixel population is: share within color distance of its mode."""
    if len(pixels) == 0:
        return {"color": None, "share": 0.0}
    center, _ = mode_color(pixels)
    distance = np.sqrt(((pixels.astype(float) - center) ** 2).sum(axis=1))
    return {"color": rgb_hex(center), "share": round(float((distance <= tolerance).mean()), 4)}


def measure(crop_arr: np.ndarray) -> dict[str, Any]:
    """Legacy per-crop measurement used by inspect_regions."""
    if crop_arr.size == 0:
        return {"tight_bbox": None, "dominant_color": None, "non_background_ratio": 0.0}
    background, border_share = dominant_border_color(crop_arr)
    ink = ink_mask(crop_arr, background)
    return {
        "tight_bbox": tight_bbox(ink),
        "dominant_color": rgb_hex(background),
        "border_dominant_share": round(border_share, 4),
        "non_background_ratio": round(float(ink.mean()), 4),
        "edge_ink_occupancy": edge_occupancy(ink),
    }
