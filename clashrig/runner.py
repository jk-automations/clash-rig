"""Clash Rig batch runner: N over-the-top fight shots. Default `--plate-backend local` is open weights end to end: Z-Image Turbo
draws a character sheet per fighter, Qwen Image Edit 2511 locks every plate to them, LTX-2.5 22B distilled makes video + audio,
Clash FX adds hit flashes and shake, then the shots are stitched into a reel. All renders go through the Comfy SDK (Comfy API v2).
`--plate-backend codex` is an optional closed-model path (Codex CLI, off-GPU) for the sheets and plates.

    python -m clashrig --style-fight anime_power --arena "floating sky islands" --shots 8 --seed 7 --out runs/clash-rig/fight1
        [--hero "an original ..."] [--rival "..."] [--hero-photo me.png] [--rival-photo rival.png] [--style auto]
        [--rig "auto (fight sequence)"] [--beat auto] [--light "blood moon"] [--intensity 0.85] [--aspect "16:9 landscape"]
        [--plate-backend local|codex] [--plates-only] [--dry-run]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from clashrig import comfy
from clashrig.graphs.edit import qwen_edit
from clashrig.graphs.still import text_to_image
from clashrig.graphs.video import ltx_i2v

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "custom_nodes" / "comfyui-clash-rig"
TRIM_FRAMES = 6


def _load(name):
    spec = importlib.util.spec_from_file_location(f"clash_rig_{name}", PACK / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rigs, reel_lib, plate_gen, fx_lib = (_load(n) for n in ("rigs", "reel", "plate_gen", "fx"))
_log_lock = threading.Lock()
T0 = time.time()


def log(msg, step=False):
    with _log_lock:
        print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)
        if step:
            comfy.emit("step", msg=msg)


def apply_fx_to_video(raw_mp4: Path, dest_mp4: Path, fx_params: dict, fps: float, seed: int) -> Path:
    """Decode raw_mp4, apply Clash FX (hit flashes, shake, chroma, speed lines, impact frames, ramp), mux the LTX audio back."""
    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    with tempfile.TemporaryDirectory(prefix="cr_fx_") as tmp:
        in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
        in_dir.mkdir()
        out_dir.mkdir()
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(raw_mp4), str(in_dir / "%05d.png")], check=True)
        files = sorted(in_dir.glob("*.png"))
        if not files:
            shutil.copy(raw_mp4, dest_mp4)
            return dest_mp4
        tensor = torch.from_numpy(np.stack([np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255.0 for p in files]))
        out = fx_lib.apply(tensor, seed=seed, fps=fps, **{k: float(fx_params.get(k, 0.0)) for k in fx_lib.KEYS})
        for idx, arr in enumerate((out.numpy().clip(0, 1) * 255.0).astype(np.uint8), 1):
            Image.fromarray(arr).save(out_dir / f"{idx:05d}.png")
        dest_mp4.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(int(fps)), "-i", str(out_dir / "%05d.png"),
                        "-i", str(raw_mp4), "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "17", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(dest_mp4)], check=True)
    return dest_mp4


def make_plate(shot, i, out: Path, backend: str, refs: list[Path], worker: str | None) -> Path:
    dest = out / "plates" / f"{i + 1:02d}.png"
    if dest.exists():
        log(f"plate {i + 1:02d} {shot['rig']} / {shot['beat']} cached", True)
        return dest
    t = time.time()
    if backend == "codex":
        plate_gen.generate_plate(shot["plate_prompt"], dest, width=shot["plate_width"], height=shot["plate_height"], refs=refs)
        log(f"plate {i + 1:02d} ({shot['rig']} / {shot['beat']}) via Codex in {time.time() - t:.0f}s", True)
        return dest
    notes = ["image 1 is the hero fighter"] + (["image 2 is the rival fighter"] if len(refs) > 1 else [])
    prompt = ("A completely new image. " + "; ".join(notes).capitalize() + ". Keep each fighter's exact face, hair, body, outfit and "
              "colors, and keep the two fighters clearly different from each other. The camera and scene are: " + shot["plate_prompt"])
    g = qwen_edit(prompt, len(refs), seed=shot["seed"], width=shot["plate_width"], height=shot["plate_height"],
                  negative=shot["plate_negative"], prefix="clash_rig/plate")
    comfy.run(g, {"save": dest}, url=worker, label=f"plate {i + 1}", inputs={(f"img{n}", "image"): r for n, r in enumerate(refs, 1)})
    log(f"plate {i + 1:02d} {shot['rig']} / {shot['beat']} (Qwen Image Edit) in {time.time() - t:.0f}s", True)
    return dest


def make_clip(shot, i, plate: Path, out: Path, worker: str | None) -> Path:
    dest, raw = out / "clips" / f"{i + 1:02d}_shot.mp4", out / "clips" / f"{i + 1:02d}_raw.mp4"
    if dest.exists():
        log(f"clip  {i + 1:02d} {shot['rig']} / {shot['beat']} cached", True)
        return dest
    t = time.time()
    if not raw.exists():
        g = ltx_i2v(shot["motion_prompt"], width=shot["width"], height=shot["height"], seconds=int(shot["seconds"]),
                    fps=int(shot["fps"]), seed=shot["seed"], negative=shot["video_negative"], prefix="clash_rig/raw", audio=True)
        comfy.run(g, {"save": raw}, url=worker, label=f"shot {i + 1} {shot['rig']}", inputs={("img1", "image"): plate})
    apply_fx_to_video(raw, dest, shot["fx"], fps=shot["fps"], seed=shot["seed"])
    log(f"clip  {i + 1:02d} {shot['rig']} / {shot['beat']} (LTX-2.5 + Clash FX) in {time.time() - t:.0f}s", True)
    return dest


def build_contact_sheet(plates: list[Path], shots: list[dict], refs: list[Path], dest: Path):
    items = [(ref, f"REF {tag}") for ref, tag in zip(refs, ("HERO", "RIVAL")) if ref.exists()]
    items += [(p, s["label"]) for p, s in zip(plates, shots) if p.exists()]
    if not items:
        return
    cols, tw, th, pad, lh = 2, 512, 288, 16, 30
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + lh + pad) + pad), (18, 18, 22))
    draw = ImageDraw.Draw(sheet)
    for idx, (p, title) in enumerate(items):
        r, c = divmod(idx, cols)
        x, y = pad + c * (tw + pad), pad + r * (th + lh + pad)
        with Image.open(p) as im:
            sheet.paste(im.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS), (x, y + lh))
        draw.text((x + 4, y + 6), title, fill=(235, 220, 140))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=92)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", type=int, default=8)
    ap.add_argument("--style-fight", default="anime_power", choices=list(rigs.FIGHT_STYLES), help="boxing, muay_thai, mma, bjj, kung_fu_wuxia, anime_power")
    ap.add_argument("--style", default="auto", choices=["auto"] + list(rigs.STYLES), help="visual style; auto = the fight style's own")
    ap.add_argument("--hero", default="")
    ap.add_argument("--rival", default="")
    ap.add_argument("--hero-photo", help="a photo of you (or anyone): becomes the hero identity ref")
    ap.add_argument("--rival-photo")
    ap.add_argument("--arena", default="")
    ap.add_argument("--arena-custom", default="")
    ap.add_argument("--rig", default="auto (fight sequence)", help="a rig name, 'auto (fight sequence)', 'auto (cycle by shot)', 'random', or a comma list")
    ap.add_argument("--beat", default="auto")
    ap.add_argument("--light", default="arena default")
    ap.add_argument("--intensity", type=float, default=0.85)
    ap.add_argument("--seconds", type=float, default=0.0, help="per-shot seconds (0 = the rig's own 2-4 s)")
    ap.add_argument("--extra", default="")
    ap.add_argument("--aspect", default="16:9 landscape")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--plate-backend", default="local", choices=["local", "codex"], help="local = open weights (default); codex = optional closed model")
    ap.add_argument("--plates-only", action="store_true")
    ap.add_argument("--comfy", default=None, help="Comfy API v2 base URL (default: $COMFY_BASE_URL or http://127.0.0.1:8195)")
    ap.add_argument("--dry-run", action="store_true", help="build and save the real graphs, write placeholder outputs, contact no server")
    a = ap.parse_args(argv)
    if a.dry_run:
        comfy.DRY = True
        a.plate_backend = "local"

    out = Path(a.out)
    for d in ("refs", "plates", "clips"):
        (out / d).mkdir(parents=True, exist_ok=True)
    hero_photo = Path(a.hero_photo).resolve() if a.hero_photo else None
    rival_photo = Path(a.rival_photo).resolve() if a.rival_photo else None
    hero = a.hero or ("the fighter in the first reference image, keeping their exact face, hair and likeness" if hero_photo else "")
    rival = a.rival or ("the fighter in the second reference image, keeping their exact face, hair and likeness" if rival_photo else "")
    rig_list = [r.strip() for r in a.rig.split(",")] if "," in a.rig else [a.rig] * a.shots

    shots = [rigs.compose(hero=hero, rival=rival, arena=a.arena, arena_custom=a.arena_custom, fight_style=a.style_fight, style=a.style,
                          rig=rig_list[i % len(rig_list)], beat=a.beat, light=a.light, intensity=a.intensity, aspect=a.aspect,
                          seconds=a.seconds, extra=a.extra, shot_index=i, seed=a.seed) for i in range(a.shots)]
    (out / "shots.json").write_text(json.dumps(shots, indent=1))
    wanted = [("hero", hero_photo, shots[0]["hero"])] + ([("rival", rival_photo, shots[0]["rival"])] if shots[0]["rival"] else [])
    comfy.emit("plan", total=len(wanted) + a.shots * (1 if a.plates_only else 2) + (0 if a.plates_only else 1))
    log(f"{a.shots} shots: " + ", ".join(f"{s['rig']} ({s['beat']})" for s in shots))
    style_label = rigs.STYLES[shots[0]["style"]]["label"]

    def make_ref(n, name, src, desc):
        dest = out / "refs" / f"{name}.png"
        if src and not dest.exists():
            shutil.copy(src, dest)
        if dest.exists():
            log(f"reference {name} ready", True)
            return dest
        t = time.time()
        if a.plate_backend == "local":
            g = text_to_image(rigs.fighter_ref_prompt(desc, style_label), width=768, height=1024, seed=a.seed + n, prefix=f"clash_rig/ref_{name}")
            comfy.run(g, {"10": dest}, url=a.comfy, label=f"{name} ref")
        else:
            plate_gen.ensure_fighter_ref(desc, dest, style_label)
        log(f"reference {name} ({'Z-Image Turbo' if a.plate_backend == 'local' else 'Codex'}) in {time.time() - t:.0f}s", True)
        return dest

    with ThreadPoolExecutor(len(wanted)) as pool:
        refs = [f.result() for f in [pool.submit(make_ref, n, *w) for n, w in enumerate(wanted)]]

    with ThreadPoolExecutor(3 if a.plate_backend == "codex" else 1) as pool:
        plates = [f.result() for f in [pool.submit(make_plate, s, i, out, a.plate_backend, refs, a.comfy) for i, s in enumerate(shots)]]
    sheet = out / "plates" / "contact_sheet.jpg"
    build_contact_sheet(plates, shots, refs, sheet)
    if a.plates_only:
        log(f"plates_only complete: {sheet}")
        return

    clips = [make_clip(s, i, p, out, a.comfy) for i, (s, p) in enumerate(zip(shots, plates))]
    reel = out / "reel.mp4"
    reel_lib.assemble(clips, reel, shots[0]["fps"], TRIM_FRAMES)
    log(f"reel: {reel} ({len(clips)} shots)", True)


if __name__ == "__main__":
    main(sys.argv[1:])
