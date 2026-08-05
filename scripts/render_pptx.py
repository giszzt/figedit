#!/usr/bin/env python3
"""Safely render a PPTX without terminating the user's PowerPoint process."""

from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _record_native_render(out_dir: Path, backend: str) -> None:
    """Increment package metrics when a nearby timings.json exists."""

    candidates = [out_dir / "timings.json", out_dir.parent / "timings.json"]
    timing_path = next((path for path in candidates if path.exists()), None)
    if timing_path is None:
        return
    try:
        report = json.loads(timing_path.read_text(encoding="utf-8"))
        counts = report.setdefault("counts", {})
        counts["native_pptx_render"] = int(counts.get("native_pptx_render", 0)) + 1
        report["last_native_pptx_render"] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "backend": backend,
        }
        timing_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # Metrics must never turn an optional render into a failure.
        return


def _powerpoint_running() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq POWERPNT.EXE", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return "POWERPNT.EXE" in result.stdout.upper()
    except Exception:
        return False


def _render_powerpoint(pptx: Path, out_dir: Path, allow_attach: bool) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("Microsoft PowerPoint rendering is available only on Windows.")

    already_running = _powerpoint_running()
    if already_running and not allow_attach:
        raise PermissionError(
            "PowerPoint is already running. Native rendering is skipped by default so the user's session is not disturbed. "
            "After explicit user consent, rerun with --allow-attach; the renderer opens only the target file and never quits PowerPoint."
        )

    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except Exception as exc:
        raise RuntimeError("PowerPoint rendering requires pywin32 on Windows.") from exc

    pythoncom.CoInitialize()
    app = None
    presentation = None
    before_count = None
    try:
        if already_running:
            # Never create a second hidden PowerPoint instance while the user
            # already has one open. If the active object cannot be acquired,
            # fail safely and let the user retry later.
            app = win32com.client.GetActiveObject("PowerPoint.Application")
        else:
            app = win32com.client.DispatchEx("PowerPoint.Application")
        before_count = int(app.Presentations.Count)
        # ReadOnly=True, Untitled=False, WithWindow=False.
        presentation = app.Presentations.Open(str(pptx), True, False, False)
        out_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[str] = []
        for index in range(1, int(presentation.Slides.Count) + 1):
            output = out_dir / f"slide-{index}.png"
            presentation.Slides.Item(index).Export(str(output), "PNG")
            outputs.append(str(output))
        presentation.Close()
        presentation = None

        after_count = int(app.Presentations.Count)
        if already_running and after_count != before_count:
            raise RuntimeError(f"PowerPoint presentation count changed unexpectedly: before={before_count}, after={after_count}")
        if not already_running and after_count == 0:
            app.Quit()
        return {
            "backend": "powerpoint",
            "attached_to_existing": already_running,
            "outputs": outputs,
            "presentation_count_before": before_count,
            "presentation_count_after": after_count,
        }
    except PermissionError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "Native PowerPoint rendering failed. If PowerPoint is in a modal dialog or edit state, retry later. "
            "The renderer does not poll, terminate, or quit the user's PowerPoint session."
        ) from exc
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        # Never call Quit here. Quit is allowed only in the proven self-created
        # success path above, after our presentation has closed.
        presentation = None
        app = None
        gc.collect()
        pythoncom.CoUninitialize()


def _find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    for candidate in [
        Path(os.environ.get("ProgramFiles", "")) / "LibreOffice" / "program" / "soffice.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "LibreOffice" / "program" / "soffice.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def _render_libreoffice(pptx: Path, out_dir: Path) -> dict[str, Any]:
    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice is not installed or not on PATH.")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="figedit-lo-") as temp_name:
        temp_dir = Path(temp_name)
        profile = (temp_dir / "profile").resolve().as_uri()
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                f"-env:UserInstallation={profile}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_dir),
                str(pptx),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        pdf = temp_dir / f"{pptx.stem}.pdf"
        if result.returncode != 0 or not pdf.exists():
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr or result.stdout}")

        outputs: list[str] = []
        pdftoppm = shutil.which("pdftoppm")
        magick = shutil.which("magick")
        if pdftoppm:
            prefix = out_dir / "slide"
            subprocess.run([pdftoppm, "-png", "-r", "144", str(pdf), str(prefix)], check=True)
            outputs = [str(path) for path in sorted(out_dir.glob("slide-*.png"))]
        elif magick:
            pattern = out_dir / "slide-%d.png"
            subprocess.run([magick, "-density", "144", str(pdf), str(pattern)], check=True)
            outputs = [str(path) for path in sorted(out_dir.glob("slide-*.png"))]
        else:
            copied_pdf = out_dir / "libreoffice-render.pdf"
            shutil.copy2(pdf, copied_pdf)
            outputs = [str(copied_pdf)]
        return {
            "backend": "libreoffice",
            "outputs": outputs,
            "warning": "Rendered by LibreOffice. Font and Office Math placement are advisory and do not replace native PowerPoint acceptance.",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--backend", choices=["auto", "powerpoint", "libreoffice"], default="auto")
    parser.add_argument("--allow-attach", action="store_true")
    args = parser.parse_args()

    pptx = args.pptx.resolve()
    out_dir = args.out.resolve()
    if not pptx.exists():
        parser.error(f"PPTX not found: {pptx}")

    try:
        backend = args.backend
        if backend == "auto":
            backend = "powerpoint" if os.name == "nt" else "libreoffice"
        if backend == "powerpoint":
            report = _render_powerpoint(pptx, out_dir, args.allow_attach)
        else:
            report = _render_libreoffice(pptx, out_dir)
        report_path = out_dir / "render-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _record_native_render(out_dir, str(report.get("backend") or backend))
        print(json.dumps({**report, "report": str(report_path)}, ensure_ascii=False, indent=2))
        return 0
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
