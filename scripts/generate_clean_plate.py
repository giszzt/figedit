#!/usr/bin/env python3
"""Reference-capable clean-plate backend adapter.

Route selection is still owned by the FigEdit workflow. Use this script only
after the Background Gate selected ``ai-clean-plate`` and a dynamic preserve /
remove / reconstruct prompt brief has been written.

Priority outside Codex:
  1. Labnana GPT-Image-2 (provider=openai, model=gpt-image-2)
  2. Labnana Gemini / Nano Banana (provider=google, model=gemini-3-pro-image)
  3. Official OpenAI / Gemini adapters when local SDK/API support is available
  4. Configured external command adapter

Inside Codex, use the built-in Image Gen / image editing capability first. This
script cannot invoke that interactive tool; it covers scriptable fallbacks.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


LABNANA_DEFAULT_BASE_URL = "https://api.labnana.com"
LABNANA_IMAGE_ENDPOINT = "/openapi/v1/images/generation"
LABNANA_GPT_MODEL = "gpt-image-2"
LABNANA_GEMINI_MODEL = "gemini-3-pro-image"


def _read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _guess_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed and guessed.startswith("image/"):
        return guessed
    head = path.read_bytes()[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _source_reference(path: Path) -> dict[str, Any]:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "inlineData": {
            "data": data,
            "mimeType": _guess_mime(path),
        }
    }


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except Exception:
        pass

    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            length = int.from_bytes(data[i : i + 2], "big")
            if marker in range(0xC0, 0xC4):
                h = int.from_bytes(data[i + 3 : i + 5], "big")
                w = int.from_bytes(data[i + 5 : i + 7], "big")
                return w, h
            i += length
    return None


def _nearest_aspect_ratio(source: Path) -> str:
    size = _image_size(source)
    if not size:
        return "16:9"
    width, height = size
    ratio = width / max(height, 1)
    candidates = {
        "1:1": 1.0,
        "2:3": 2 / 3,
        "3:2": 3 / 2,
        "3:4": 3 / 4,
        "4:3": 4 / 3,
        "4:5": 4 / 5,
        "5:4": 5 / 4,
        "9:16": 9 / 16,
        "16:9": 16 / 9,
        "21:9": 21 / 9,
    }
    return min(candidates, key=lambda key: abs(candidates[key] - ratio))


def _write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_image_bytes(obj: Any) -> tuple[bytes, str] | None:
    """Best-effort extraction for Labnana/OpenAI/Gemini-like JSON responses."""
    if isinstance(obj, dict):
        inline = obj.get("inlineData") or obj.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return base64.b64decode(str(inline["data"])), str(mime)
        if obj.get("b64_json"):
            return base64.b64decode(str(obj["b64_json"])), "image/png"
        if obj.get("data") and str(obj.get("mimeType") or obj.get("mime_type") or "").startswith("image/"):
            mime = obj.get("mimeType") or obj.get("mime_type") or "image/png"
            return base64.b64decode(str(obj["data"])), str(mime)
        for value in obj.values():
            found = _extract_image_bytes(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _extract_image_bytes(value)
            if found:
                return found
    return None


def _save_image_bytes(out: Path, data: bytes, mime: str) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".png" and mime not in ("image/png", "image/x-png"):
        try:
            from PIL import Image  # type: ignore
            import io

            with Image.open(io.BytesIO(data)) as img:
                img.save(out, format="PNG")
            return out
        except Exception:
            pass
    out.write_bytes(data)
    return out


def _load_command_config(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        env_path = os.environ.get("FIGEDIT_CLEAN_PLATE_CONFIG")
        path = Path(env_path) if env_path else None
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Clean-plate backend config not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Clean-plate backend config must be a JSON object.")
    command = config.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("Clean-plate backend config must contain a non-empty string-list 'command'.")
    if not str(config.get("name", "")).strip():
        config["name"] = "configured-reference-image-backend"
    return config


def _format_command(config: dict[str, Any], source: Path, prompt_file: Path, out: Path, provenance: Path | None) -> list[str]:
    values = {
        "source": str(source),
        "prompt_file": str(prompt_file),
        "out": str(out),
        "provenance": str(provenance or ""),
    }
    return [part.format(**values) for part in config["command"]]


def _run_command_backend(args: argparse.Namespace, *, source: Path, prompt_file: Path, out: Path, provenance: Path | None) -> dict[str, Any]:
    config = _load_command_config(args.config)
    if not config:
        raise RuntimeError("No configured command backend. Set FIGEDIT_CLEAN_PLATE_CONFIG or pass --config.")
    command = _format_command(config, source, prompt_file, out, provenance)
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=args.timeout)
    record = {
        "role": "primary-clean-plate",
        "backend": config.get("name"),
        "source": str(source),
        "prompt_file": str(prompt_file),
        "output": str(out),
        "command_config": str(args.config or os.environ.get("FIGEDIT_CLEAN_PLATE_CONFIG", "")),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "accepted": proc.returncode == 0 and out.exists(),
    }
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-4000:])
    if not out.exists():
        raise RuntimeError("Backend command returned success but did not create the requested output image.")
    return record


def _labnana_available() -> bool:
    return bool(os.environ.get("LABNANA_API_KEY"))


def _run_labnana(args: argparse.Namespace, *, variant: str, source: Path, prompt: str, out: Path) -> dict[str, Any]:
    api_key = os.environ.get("LABNANA_API_KEY")
    if not api_key:
        raise RuntimeError("LABNANA_API_KEY is not set.")

    if variant == "labnana-gpt-image-2":
        provider = "openai"
        model = LABNANA_GPT_MODEL
        image_config: dict[str, Any] = {"imageSize": args.image_size}
        # GPT-Image-2 supports arbitrary aspect ratios through Labnana; omit
        # aspectRatio in auto mode to preserve non-standard source geometry.
        if args.aspect_ratio != "auto":
            image_config["aspectRatio"] = args.aspect_ratio
    elif variant == "labnana-nano-banana":
        provider = "google"
        model = LABNANA_GEMINI_MODEL
        image_config = {
            "imageSize": args.image_size,
            "aspectRatio": _nearest_aspect_ratio(source) if args.aspect_ratio == "auto" else args.aspect_ratio,
        }
    else:
        raise ValueError(f"Unsupported Labnana variant: {variant}")

    payload = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "imageConfig": image_config,
        "referenceImages": [_source_reference(source)],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    base_url = os.environ.get("LABNANA_BASE_URL", LABNANA_DEFAULT_BASE_URL).rstrip("/")
    req = urllib.request.Request(
        base_url + LABNANA_IMAGE_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        response_data = resp.read()
    response_json = json.loads(response_data.decode("utf-8"))
    extracted = _extract_image_bytes(response_json)
    if not extracted:
        raise RuntimeError("Labnana response did not contain image bytes.")
    image_bytes, mime = extracted
    written = _save_image_bytes(out, image_bytes, mime)
    return {
        "role": "primary-clean-plate",
        "backend": "labnana",
        "provider": provider,
        "model": model,
        "source": str(source),
        "output": str(written),
        "requested_image_size": args.image_size,
        "requested_aspect_ratio": image_config.get("aspectRatio", "auto"),
        "response_mime": mime,
        "accepted": written.exists(),
    }


def _run_official_openai(args: argparse.Namespace, *, source: Path, prompt: str, out: Path) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")
    try:
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        raise RuntimeError("The openai Python package is not installed.") from exc

    client = OpenAI()
    with source.open("rb") as image_file:
        result = client.images.edit(
            model=os.environ.get("FIGEDIT_OPENAI_IMAGE_MODEL", "gpt-image-2"),
            image=image_file,
            prompt=prompt,
            size=os.environ.get("FIGEDIT_OPENAI_IMAGE_SIZE", "auto"),
        )
    data_items = getattr(result, "data", None) or []
    if not data_items:
        raise RuntimeError("OpenAI Images API returned no image data.")
    item = data_items[0]
    b64 = getattr(item, "b64_json", None)
    if not b64 and isinstance(item, dict):
        b64 = item.get("b64_json")
    if not b64:
        raise RuntimeError("OpenAI Images API returned no b64_json image.")
    written = _save_image_bytes(out, base64.b64decode(b64), "image/png")
    return {
        "role": "primary-clean-plate",
        "backend": "openai-official",
        "model": os.environ.get("FIGEDIT_OPENAI_IMAGE_MODEL", "gpt-image-2"),
        "source": str(source),
        "output": str(written),
        "accepted": written.exists(),
    }


def _run_official_gemini(args: argparse.Namespace, *, source: Path, prompt: str, out: Path) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")
    mime = _guess_mime(source)
    payload = {
        "model": os.environ.get("FIGEDIT_GEMINI_IMAGE_MODEL", "gemini-3-pro-image"),
        "input": [
            {"type": "text", "text": prompt},
            {"type": "image", "mime_type": mime, "data": base64.b64encode(source.read_bytes()).decode("ascii")},
        ],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    base_url = os.environ.get("GEMINI_INTERACTIONS_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    req = urllib.request.Request(
        base_url + "/interactions",
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        response_data = resp.read()
    response_json = json.loads(response_data.decode("utf-8"))
    extracted = _extract_image_bytes(response_json)
    if not extracted:
        raise RuntimeError("Gemini response did not contain image bytes.")
    image_bytes, response_mime = extracted
    written = _save_image_bytes(out, image_bytes, response_mime)
    return {
        "role": "primary-clean-plate",
        "backend": "gemini-official",
        "model": payload["model"],
        "source": str(source),
        "output": str(written),
        "response_mime": response_mime,
        "accepted": written.exists(),
    }


def _backend_order(args: argparse.Namespace) -> list[str]:
    if args.backend != "auto":
        return [args.backend]
    order = [
        "labnana-gpt-image-2",
        "labnana-nano-banana",
        "openai-official",
        "gemini-official",
        "configured-command",
    ]
    preferred = os.environ.get("FIGEDIT_CLEAN_PLATE_BACKEND", "").strip()
    if preferred and preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    return order


def _available_routes(args: argparse.Namespace) -> list[dict[str, Any]]:
    routes = [
        {
            "priority": 0,
            "route": "codex-image-gen",
            "available": "agent-check-required",
            "note": "Use Codex built-in Image Gen first when the current agent has image editing with a source reference.",
        },
        {
            "priority": 1,
            "route": "labnana-gpt-image-2",
            "available": _labnana_available(),
            "required": ["LABNANA_API_KEY"],
        },
        {
            "priority": 2,
            "route": "labnana-nano-banana",
            "available": _labnana_available(),
            "required": ["LABNANA_API_KEY"],
        },
        {
            "priority": 3,
            "route": "openai-official",
            "available": bool(os.environ.get("OPENAI_API_KEY")),
            "required": ["OPENAI_API_KEY", "openai Python package"],
        },
        {
            "priority": 4,
            "route": "gemini-official",
            "available": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
            "required": ["GEMINI_API_KEY or GOOGLE_API_KEY"],
        },
        {
            "priority": 5,
            "route": "configured-command",
            "available": _load_command_config(args.config) is not None,
            "required": ["FIGEDIT_CLEAN_PLATE_CONFIG or --config"],
        },
    ]
    return routes


def precheck(args: argparse.Namespace) -> int:
    try:
        routes = _available_routes(args)
        scriptable_ok = any(item["available"] is True for item in routes if item["route"] != "codex-image-gen")
        result = {
            "status": "ok" if scriptable_ok else "unavailable",
            "routes": routes,
            "message": (
                "Scriptable backends are configured, but they are FALLBACKS: "
                "first check whether your own agent environment has a built-in "
                "reference-capable image tool (e.g. Codex Image Gen) and use it "
                "before any scriptable route, per references/image_backend_policy.md."
                if scriptable_ok
                else "No scriptable backend is configured. Use your agent's built-in image tool (e.g. Codex Image Gen) if present; otherwise copy env.example to .env at the skill root and fill in LABNANA_API_KEY or a provider key."
            ),
        }
    except Exception as exc:
        result = {"status": "failed", "message": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


def generate(args: argparse.Namespace) -> int:
    if not args.source or not args.prompt_file or not args.out:
        raise SystemExit("--source, --prompt-file, and --out are required unless --precheck is used.")
    source = args.source.resolve()
    prompt_file = args.prompt_file.resolve()
    out = args.out.resolve()
    provenance = args.provenance.resolve() if args.provenance else None

    if not source.exists():
        raise FileNotFoundError(f"Source image not found: {source}")
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    prompt = _read_prompt(prompt_file)
    errors: list[dict[str, str]] = []
    for backend in _backend_order(args):
        try:
            if backend == "labnana-gpt-image-2":
                record = _run_labnana(args, variant=backend, source=source, prompt=prompt, out=out)
            elif backend == "labnana-nano-banana":
                record = _run_labnana(args, variant=backend, source=source, prompt=prompt, out=out)
            elif backend == "openai-official":
                record = _run_official_openai(args, source=source, prompt=prompt, out=out)
            elif backend == "gemini-official":
                record = _run_official_gemini(args, source=source, prompt=prompt, out=out)
            elif backend == "configured-command":
                record = _run_command_backend(args, source=source, prompt_file=prompt_file, out=out, provenance=provenance)
            else:
                raise RuntimeError(f"Unknown backend: {backend}")
            record["prompt_file"] = str(prompt_file)
            record["fallback_errors"] = errors
            if provenance:
                _write_json(provenance, record)
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            errors.append({"backend": backend, "message": str(exc)})
            if args.backend != "auto":
                break

    failure = {
        "status": "failed",
        "message": "No clean-plate backend succeeded.",
        "errors": errors,
    }
    if provenance:
        _write_json(provenance, failure)
    print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


try:
    import api_keys as _api_keys
    _api_keys.load()
except Exception:
    pass  # .env loading is best-effort; real env vars still work


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--precheck", action="store_true", help="Check available scriptable backends.")
    parser.add_argument("--source", type=Path, help="Source image reference.")
    parser.add_argument("--prompt-file", type=Path, help="Model-ready prompt file.")
    parser.add_argument("--out", type=Path, help="Output clean-plate image path.")
    parser.add_argument("--provenance", type=Path, help="Where to write generation provenance JSON.")
    parser.add_argument("--config", type=Path, help="Provider-neutral backend command config JSON.")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=[
            "auto",
            "labnana-gpt-image-2",
            "labnana-nano-banana",
            "openai-official",
            "gemini-official",
            "configured-command",
        ],
        help="Scriptable backend to use. Codex Image Gen is handled by the agent before this script.",
    )
    parser.add_argument("--image-size", default="2K", help="Requested provider image size, default 2K.")
    parser.add_argument("--aspect-ratio", default="auto", help="auto or provider aspect ratio such as 16:9.")
    parser.add_argument("--timeout", type=int, default=600, help="Backend timeout in seconds.")
    args = parser.parse_args()

    if args.precheck:
        return precheck(args)
    return generate(args)


if __name__ == "__main__":
    raise SystemExit(main())
