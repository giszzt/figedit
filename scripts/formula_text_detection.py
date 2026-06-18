#!/usr/bin/env python3
"""Detect formula-like content that leaked into plain text elements.

This is a manifest-level guardrail. It does not try to OCR formulas from
pixels; it catches authored text elements that still contain math syntax or
math typography and therefore should usually be split into `text` + `math`
elements before SVG/PPTX export.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TEX_COMMAND_RE = re.compile(
    r"\\(?:"
    r"frac|dfrac|tfrac|sqrt|sum|prod|int|oint|lim|log|ln|sin|cos|tan|"
    r"min|max|argmin|argmax|mathrm|mathbf|mathit|mathcal|mathbb|operatorname|"
    r"hat|bar|tilde|vec|dot|ddot|overline|underline|"
    r"alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|"
    r"iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|varphi|"
    r"chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Phi|Psi|Omega|"
    r"leq|geq|neq|approx|sim|cdot|times|pm|mp|infty|partial|nabla|"
    r"mapsto|rightarrow|leftarrow|Rightarrow|Leftarrow"
    r")\b"
)
BRACED_SCRIPT_RE = re.compile(r"(?:[A-Za-z0-9)\]}]|\\[A-Za-z]+)\s*[\^_]\s*\{[^}]+\}")
PAREN_SCRIPT_RE = re.compile(r"(?:[A-Za-z0-9)\]}]|\\[A-Za-z]+)\s*[\^_]\s*\([^)]{1,16}\)")
SIMPLE_SCRIPT_RE = re.compile(r"\b[A-Za-z](?:[A-Za-z0-9]*)\s*[\^_]\s*(?:[A-Za-z0-9]+|\\[A-Za-z]+)\b")
ASCII_MATH_OP_RE = re.compile(r"[A-Za-z0-9)\]}]\s*(?:=|<=|>=|<|>)\s*[A-Za-z0-9({\\]")
FRACTION_SLASH_RE = re.compile(r"\b(?:[A-Za-z]\w{0,4}|\d+(?:\.\d+)?)\s*/\s*(?:[A-Za-z]\w{0,4}|\d+(?:\.\d+)?)\b")
WORD_DEFINITION_RE = re.compile(r"\b[A-Z]\s*=\s*[a-z][a-z-]{2,}\b")

UNICODE_MATH_SYMBOL_RE = re.compile(r"[\u2200-\u22FF\u27C0-\u27EF\u2980-\u29FF\u2A00-\u2AFF]")
UNICODE_GREEK_RE = re.compile(r"[\u0370-\u03FF]")
UNICODE_SCRIPT_RE = re.compile(r"[\u2070-\u209F\u1D2C-\u1D6A]")

COMMON_FILE_EXT_RE = re.compile(r"\.(?:tsv|csv|json|md|txt|sh|py|js|ts|tsx|jsx|html|css|xml|yml|yaml|png|jpg|jpeg|svg|pdf)\b", re.I)
CODE_TOKEN_RE = re.compile(r"(?:\b(?:ls|cd|cat|grep|awk|sed|echo|python|node|npm|pip|git)\b|&&|\|\s*\w|/[A-Za-z0-9_.-]+)")

SUPPRESS_POLICIES = {"not-formula", "literal", "code", "text-label", "symbolic-name"}


def _text_values(el: dict[str, Any]) -> list[str]:
    values: list[str] = []
    text = el.get("text")
    if isinstance(text, str) and text.strip():
        values.append(text.strip())
    lines = el.get("lines")
    if isinstance(lines, list):
        joined = " ".join(str(line).strip() for line in lines if str(line).strip())
        if joined:
            values.append(joined)
    return values


def _is_suppressed(el: dict[str, Any]) -> bool:
    policy = str(el.get("formula_policy") or el.get("math_policy") or "").strip().lower()
    return policy in SUPPRESS_POLICIES


def _looks_like_code_or_path(text: str, el: dict[str, Any]) -> bool:
    cls = str(el.get("class") or "").lower()
    subtype = str(el.get("subtype") or "").lower()
    family = str(el.get("font_family") or "").lower()
    if any(token in cls for token in ("code", "filename", "path", "literal")):
        return True
    if subtype in {"code", "filename", "path", "literal"}:
        return True
    if "mono" in family:
        return True
    return bool(COMMON_FILE_EXT_RE.search(text) or CODE_TOKEN_RE.search(text))


def classify_formula_text(text: str, el: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return whether *text* looks like math that should not stay plain text."""
    el = el or {}
    normalized = " ".join(text.split())
    reasons: list[str] = []
    score = 0

    if not normalized or _is_suppressed(el):
        return {"is_leak": False, "score": 0, "reasons": []}

    if TEX_COMMAND_RE.search(normalized):
        score += 3
        reasons.append("tex-command")
    if BRACED_SCRIPT_RE.search(normalized):
        score += 3
        reasons.append("braced-subscript-or-superscript")
    if PAREN_SCRIPT_RE.search(normalized):
        score += 2
        reasons.append("parenthesized-subscript-or-superscript")
    if SIMPLE_SCRIPT_RE.search(normalized):
        score += 1
        reasons.append("simple-subscript-or-superscript")
    if ASCII_MATH_OP_RE.search(normalized):
        score += 2
        reasons.append("ascii-math-operator")
    if FRACTION_SLASH_RE.search(normalized) and not COMMON_FILE_EXT_RE.search(normalized):
        score += 1
        reasons.append("slash-fraction")
    if UNICODE_MATH_SYMBOL_RE.search(normalized):
        score += 2
        reasons.append("unicode-math-symbol")
    if UNICODE_SCRIPT_RE.search(normalized):
        score += 2
        reasons.append("unicode-super-or-subscript")
    if UNICODE_GREEK_RE.search(normalized):
        # Greek is weak evidence in prose, but strong in compact symbolic labels.
        compact = re.sub(r"[\s\-_/.,:;()\[\]{}]", "", normalized)
        if len(compact) <= 6 or any(reason in reasons for reason in ("ascii-math-operator", "unicode-math-symbol", "unicode-super-or-subscript")):
            score += 2
            reasons.append("compact-greek-symbol")
        else:
            score += 1
            reasons.append("greek-symbol")

    strong_reasons = {
        "tex-command",
        "braced-subscript-or-superscript",
        "parenthesized-subscript-or-superscript",
        "unicode-math-symbol",
        "unicode-super-or-subscript",
        "compact-greek-symbol",
    }
    has_strong_reason = bool(strong_reasons.intersection(reasons))

    if _looks_like_code_or_path(normalized, el) and not has_strong_reason:
        return {"is_leak": False, "score": score, "reasons": reasons, "suppressed_by": "code-or-path"}
    if not has_strong_reason and WORD_DEFINITION_RE.search(normalized):
        return {"is_leak": False, "score": score, "reasons": reasons, "suppressed_by": "word-definition"}

    is_leak = score >= 2
    return {"is_leak": is_leak, "score": score, "reasons": reasons}


def find_formula_text_leaks(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Find `type: text` elements that likely contain formulas."""
    leaks: list[dict[str, Any]] = []
    for el in manifest.get("elements", []):
        if not isinstance(el, dict) or str(el.get("type", "")).lower() != "text":
            continue
        for text in _text_values(el):
            verdict = classify_formula_text(text, el)
            if not verdict.get("is_leak"):
                continue
            leaks.append(
                {
                    "id": el.get("id"),
                    "text": text,
                    "score": verdict.get("score"),
                    "reasons": verdict.get("reasons", []),
                    "suggestion": "split mixed labels into adjacent text and math elements, or convert pure formulas to type=math",
                }
            )
    return leaks


def audit_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    leaks = find_formula_text_leaks(manifest)
    return {
        "status": "review" if leaks else "ok",
        "formula_text_leak_count": len(leaks),
        "formula_text_leak_samples": leaks[:80],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    result = audit_manifest(args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
