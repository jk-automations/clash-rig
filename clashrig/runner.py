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
from clashrig.graphs.video import ltx_flf, ltx_i2v

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


FX_STRENGTH = 0.45  # full-strength flashes + speed lines on every shot wash the frames out
END_STRENGTH = 1.0  # keyframe mode: end-frame guide scale


def scale_fx(fx: dict, k: float) -> dict:
    """Scale the overlay effects; camera shake and speed ramp keep their rig values."""
    return {n: (v if n in ("shake", "ramp") else round(v * k, 3)) for n, v in fx.items()}


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


def make_plate(shot, i, out: Path, backend: str, refs: list[Path], worker: str | None, defer: list | None = None) -> Path:
    dest = out / "plates" / f"{i + 1:02d}.png"
    if dest.exists():
        if defer is None:
            log(f"plate {i + 1:02d} {shot['rig']} / {shot['beat']} ready", True)
        return dest
    t = time.time()
    if shot.get("compose_prompt") and backend == "codex":
        # Keyframe start frame from a closed image model, locked to the fighter refs (Clash Anime's sharper look).
        lead = ("Image 1 is the hero" + ("; image 2 is the rival" if len(refs) > 1 else "") + ". Keep each fighter's exact face, hair, "
                "body, outfit and colors. One single frame, no panels, no text. ")
        plate_gen.generate_plate(lead + shot["compose_prompt"], dest, width=shot["plate_width"], height=shot["plate_height"], refs=refs)
        log(f"plate {i + 1:02d} {shot['rig']} start frame via Codex in {time.time() - t:.0f}s", True)
        return dest
    if shot.get("compose_prompt"):  # keyframe start frame: Z-Image follows pose and camera better than Qwen Edit on the ref sheets
        g = text_to_image(shot["compose_prompt"], width=shot["plate_width"], height=shot["plate_height"], seed=shot["seed"],
                          prefix="clash_rig/start")
        comfy.run_or_defer(defer, g, {"10": dest}, url=worker, label=f"start plate {i + 1}")
        if defer is None:
            log(f"plate {i + 1:02d} {shot['rig']} start frame (Z-Image Turbo) in {time.time() - t:.0f}s", True)
        return dest
    if backend == "codex":
        plate_gen.generate_plate(shot["plate_prompt"], dest, width=shot["plate_width"], height=shot["plate_height"], refs=refs)
        log(f"plate {i + 1:02d} ({shot['rig']} / {shot['beat']}) via Codex in {time.time() - t:.0f}s", True)
        return dest
    notes = ["image 1 is the hero fighter"] + (["image 2 is the rival fighter"] if len(refs) > 1 else [])
    prompt = ("A completely new image. " + "; ".join(notes).capitalize() + ". Keep each fighter's exact face, hair, body, outfit and "
              "colors, and keep the two fighters clearly different from each other. The camera and scene are: " + shot["plate_prompt"])
    g = qwen_edit(prompt, len(refs), seed=shot["seed"], width=shot["plate_width"], height=shot["plate_height"],
                  negative=shot["plate_negative"], prefix="clash_rig/plate")
    comfy.run_or_defer(defer, g, {"save": dest}, url=worker, label=f"plate {i + 1}", inputs={(f"img{n}", "image"): r for n, r in enumerate(refs, 1)})
    if defer is None:
        log(f"plate {i + 1:02d} {shot['rig']} / {shot['beat']} (Qwen Image Edit) in {time.time() - t:.0f}s", True)
    return dest


def end_plate_path(out: Path, i: int) -> Path:
    return out / "plates" / f"{i + 1:02d}_end.png"


def make_end_plate(shot, i, out: Path, start: Path, worker: str | None) -> Path:
    """Keyframe mode: the same shot a split second later, one edit command on the start plate so camera, scene and fighters stay put."""
    dest = end_plate_path(out, i)
    if dest.exists():
        log(f"end   {i + 1:02d} {shot['rig']} / {shot['beat']} ready", True)
        return dest
    t = time.time()
    g = qwen_edit(shot["end_prompt"], 1, seed=shot["seed"] + 1, width=shot["plate_width"], height=shot["plate_height"],
                  negative=shot["plate_negative"], prefix="clash_rig/end")
    comfy.run(g, {"save": dest}, url=worker, label=f"end plate {i + 1}", inputs={("img1", "image"): start})
    log(f"end   {i + 1:02d} {shot['rig']} (Qwen Image Edit) in {time.time() - t:.0f}s", True)
    return dest


def make_clip(shot, i, plate: Path, out: Path, worker: str | None, defer: list | None = None) -> Path:
    dest, raw = out / "clips" / f"{i + 1:02d}_shot.mp4", out / "clips" / f"{i + 1:02d}_raw.mp4"
    if dest.exists():
        if defer is None:
            log(f"clip  {i + 1:02d} {shot['rig']} / {shot['beat']} cached", True)
        return dest
    t = time.time()
    if not raw.exists():
        kw = dict(width=shot["width"], height=shot["height"], seconds=int(shot["seconds"]), fps=int(shot["fps"]), seed=shot["seed"],
                  negative=shot["video_negative"], prefix="clash_rig/raw", audio=True)
        inputs = {("img1", "image"): plate}
        if shot.get("end_prompt"):  # keyframe mode: LTX first + last frame
            g = ltx_flf(shot["motion_prompt"], end_strength=END_STRENGTH, **kw)
            inputs[("img2", "image")] = end_plate_path(out, i)
        else:
            g = ltx_i2v(shot["motion_prompt"], **kw)
        comfy.run_or_defer(defer, g, {"save": raw}, url=worker, label=f"shot {i + 1} {shot['rig']}", inputs=inputs)
        if defer is not None:
            return dest
    apply_fx_to_video(raw, dest, scale_fx(shot["fx"], FX_STRENGTH), fps=shot["fps"], seed=shot["seed"])
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


def main(argv=None, line=None, doc=None):
    """line=None is the full Clash Rig CLI; line="anime" / "real" is the Clash Anime / Clash Real runner (own fight styles,
    looks and defaults, keyframe mode on, six shots)."""
    ln = rigs.LINES[line] if line else None
    ap = argparse.ArgumentParser(description=doc or __doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", type=int, default=6 if ln else 8)
    fights = ln["fight_styles"] if ln else list(rigs.FIGHT_STYLES)
    ap.add_argument("--style-fight", default=ln["fight_style"] if ln else "anime_power", choices=fights, help=", ".join(fights))
    ap.add_argument("--style", default="auto", choices=["auto"] + (ln["styles"] if ln else list(rigs.STYLES)),
                    help="visual style; auto = " + (ln["style"] if ln else "the fight style's own"))
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
    ap.add_argument("--fx-strength", type=float, default=FX_STRENGTH, help="Impact FX overlay strength (0-1)")
    ap.add_argument("--drop", default="", help="comma list of shot numbers to leave out of the reel, e.g. 4")
    ap.add_argument("--seconds", type=float, default=0.0, help="per-shot seconds (0 = the rig's own 2-4 s)")
    ap.add_argument("--extra", default="")
    ap.add_argument("--aspect", default="16:9 landscape")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--plate-backend", default="local", choices=["local", "codex"], help="local = open weights (default); codex = optional closed model")
    ap.add_argument("--plates-only", action="store_true")
    ap.add_argument("--starts-only", action="store_true", help="keyframe mode: make the refs and start frames only, then stop")
    ap.add_argument("--end-strength", type=float, default=END_STRENGTH, help="keyframe mode: end-frame guide scale (lower = softer target)")
    ap.add_argument("--reseed", default="", help="comma list of shot numbers whose clips get a new seed, e.g. 1,4 (delete their clips first)")
    kf_help = "one move per shot between a start and an end plate (LTX first+last frame)"
    if ln:
        ap.add_argument("--keyframes", action=argparse.BooleanOptionalAction, default=True, help=kf_help)
    else:
        ap.add_argument("--keyframes", action="store_true", help=kf_help)
    ap.add_argument("--comfy", default=None, help="Comfy API v2 base URL (default: $COMFY_BASE_URL or http://127.0.0.1:8195)")
    ap.add_argument("--dry-run", action="store_true", help="build and save the real graphs, write placeholder outputs, contact no server")
    a = ap.parse_args(argv)
    if ln:
        a.style = rigs.line_style(line, a.style_fight, a.style)
        if a.end_strength == END_STRENGTH and a.keyframes:
            a.end_strength = 0.5  # soft end target: full strength holds the start frame and snaps to the end
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
                          seconds=a.seconds, extra=a.extra, shot_index=i, seed=a.seed, keyframes=a.keyframes) for i in range(a.shots)]
    for n in (int(x) for x in a.reseed.split(",") if x.strip()):
        shots[n - 1]["seed"] += 500
    globals()["END_STRENGTH"] = a.end_strength
    (out / "shots.json").write_text(json.dumps(shots, indent=1))
    wanted = [("hero", hero_photo, shots[0]["hero"])] + ([("rival", rival_photo, shots[0]["rival"])] if shots[0]["rival"] else [])
    comfy.emit("plan", total=len(wanted) + a.shots * ((1 if a.plates_only else 2) + (1 if a.keyframes else 0)) + (0 if a.plates_only else 1))
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

    if a.plate_backend == "local":  # all plates in one ComfyUI prompt
        batch: list = []
        for i, sh in enumerate(shots):
            make_plate(sh, i, out, a.plate_backend, refs, a.comfy, defer=batch)
        if batch:
            log(f"rendering {len(batch)} plates in one ComfyUI prompt")
            comfy.run_many(batch, chunk=len(batch))
    with ThreadPoolExecutor(3 if a.plate_backend == "codex" else 1) as pool:
        plates = [f.result() for f in [pool.submit(make_plate, sh, i, out, a.plate_backend, refs, a.comfy) for i, sh in enumerate(shots)]]
    sheet = out / "plates" / "contact_sheet.jpg"
    if a.starts_only:
        build_contact_sheet(plates, shots, refs, sheet)
        log(f"starts_only complete: {sheet}")
        return
    if a.keyframes:
        ends = [make_end_plate(sh, i, out, p, a.comfy) for i, (sh, p) in enumerate(zip(shots, plates))]
        pairs = [x for p, e, sh in zip(plates, ends, shots) for x in ((p, {"label": sh["label"] + "  START"}), (e, {"label": sh["label"] + "  END"}))]
        build_contact_sheet([p for p, _ in pairs], [sh for _, sh in pairs], refs, sheet)
    else:
        build_contact_sheet(plates, shots, refs, sheet)
    if a.plates_only:
        log(f"plates_only complete: {sheet}")
        return

    globals()["FX_STRENGTH"] = a.fx_strength
    batch = []
    for i, (sh, p) in enumerate(zip(shots, plates)):
        make_clip(sh, i, p, out, a.comfy, defer=batch)
    if batch:  # the whole reel in one ComfyUI prompt
        log(f"rendering {len(batch)} LTX clips in one ComfyUI prompt")
        comfy.run_many(batch, chunk=len(batch))
    clips = [make_clip(sh, i, p, out, a.comfy) for i, (sh, p) in enumerate(zip(shots, plates))]
    dropped = {int(x) for x in a.drop.split(",") if x.strip()}
    clips = [c for i, c in enumerate(clips, 1) if i not in dropped]
    reel = out / "reel.mp4"
    reel_lib.assemble(clips, reel, shots[0]["fps"], TRIM_FRAMES)
    log(f"reel: {reel} ({len(clips)} shots)", True)


if __name__ == "__main__":
    main(sys.argv[1:])
