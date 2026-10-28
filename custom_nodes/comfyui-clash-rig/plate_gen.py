"""Optional closed-model backend: fighter reference sheets and plates via the Codex CLI (`codex exec` with its image tool).

Off-GPU, so the whole GPU stays free for LTX-2.5. Not used by the open-weights workflows or the default `--plate-backend local`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

CODEX_BIN = shutil.which("codex") or "codex"


def _fit_and_save(src: Path, dest: Path, width: int, height: int) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        rgb = im.convert("RGB")
        if rgb.size != (width, height):
            rgb = ImageOps.fit(rgb, (width, height), method=Image.Resampling.LANCZOS)
        rgb.save(dest, format="PNG")
    return dest


def generate_codex(prompt: str, dest: Path, width: int = 1024, height: int = 576,
                   refs: list[Path] | None = None, pilot_ref: Path | None = None, timeout: int = 240) -> Path:
    """Generate or edit a plate using Codex CLI's built-in image generation tool."""
    refs = [Path(r).resolve() for r in (refs or []) if r and Path(r).exists()]
    orient = "landscape 16:9 (1536x1024)" if width >= height else "portrait 9:16 (1024x1536)"
    with tempfile.TemporaryDirectory(prefix="cr_codex_") as tmp:
        tmpdir = Path(tmp)
        local_refs = []
        for idx, r in enumerate(refs, 1):
            lr = tmpdir / f"ref_{idx}.png"
            shutil.copy(r, lr)
            local_refs.append(lr)

        ref_note = ""
        if len(local_refs) == 1:
            ref_note = ("Use the attached reference image (ref_1.png) as the exact visual identity of the hero fighter "
                        "(keep the exact same face, hair, body, outfit and colors). ")
        elif len(local_refs) >= 2:
            ref_note = ("Use the first attached image (ref_1.png) as the exact visual identity of the hero fighter and the "
                        "second attached image (ref_2.png) as the exact visual identity of the rival fighter "
                        "(keep their exact faces, hair, bodies, outfits and colors; they must look clearly different from each other). ")

        if pilot_ref and Path(pilot_ref).exists():
            p_ref = tmpdir / "pilot_ref.png"
            shutil.copy(Path(pilot_ref), p_ref)
            local_refs.append(p_ref)

        out_raw = tmpdir / "out.png"
        instruction = (
            f"Use your built-in image generation tool to generate ONE {orient} image matching the exact visual style, action, and camera perspective specified below. "
            f"{ref_note}Scene and camera rig specification:\n\n{prompt}\n\n"
            f"After generating the image, copy the generated PNG file to {out_raw}. "
            f"Do not create any other files. Reply only with {out_raw}."
        )

        env = os.environ.copy()
        env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
        if Path("/etc/ssl/cert.pem").exists():
            env["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"

        cmd = [CODEX_BIN, "exec", "--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox", "-C", str(tmpdir)]
        for lr in local_refs:
            cmd += ["-i", str(lr)]
        cmd += ["--", instruction]

        subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout, check=False)

        if not out_raw.exists():
            pngs = [p for p in tmpdir.glob("*.png") if not p.name.startswith("ref_")]
            if pngs:
                out_raw = max(pngs, key=lambda p: p.stat().st_mtime)
        if not out_raw.exists():
            raise RuntimeError(f"Codex image generation did not produce an image for {dest.name}")
        return _fit_and_save(out_raw, dest, width, height)


def generate_plate(prompt: str, dest: Path, width: int = 1024, height: int = 576,
                   refs: list[Path] | None = None, pilot_ref: Path | None = None, backend: str = "codex") -> Path:
    """Generate a shot plate or fighter reference with Codex."""
    if dest.exists():
        return dest
    return generate_codex(prompt, dest, width=width, height=height, refs=refs, pilot_ref=pilot_ref)


def ensure_fighter_ref(desc: str, dest: Path, style_desc: str = "") -> Path:
    if dest.exists():
        return dest
    return generate_plate(fighter_ref_prompt(desc, style_desc), dest, width=1024, height=576, refs=None)


def fighter_ref_prompt(desc: str, style_desc: str = "") -> str:
    return (f"Full-body character turnaround sheet of {desc}: the same single character shown three times side by side on one plain "
            f"light-grey background (front view, three-quarter view, side view), standing in a relaxed fighting stance, "
            f"{style_desc + ', ' if style_desc else ''}soft even light so face, hair, body, outfit colors and details are crystal clear. "
            f"Original fictional character, no logos and no text.")
