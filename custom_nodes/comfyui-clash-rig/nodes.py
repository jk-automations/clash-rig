"""Clash Rig nodes for ComfyUI.

Clash Anime Rig    over-the-top anime power fights (keyframe mode): start-frame prompt, end-frame edit, LTX motion prompt, FX
Clash Real Rig     real-life fights: boxing, MMA, Muay Thai, taekwondo, BJJ (keyframe mode), same outputs
Clash Rig          fight style + hero + rival + arena + camera rig -> first-frame prompt, LTX motion prompt, sizes, frames, seed, FX
Clash Rig Builder  build your own camera rig: mount, pitch, lens, stability
Clash Plate        optional off-GPU first frame via the Codex CLI (hero & rival reference images)
Clash Rig Library  every fight style, beat, rig and arena as text
Clash FX           hit flashes, camera shake, chromatic punch, speed lines, impact frames, speed ramp on the decoded frames
Clash Reel         stitch the last N saved shots into one hard-cut reel with their LTX audio
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from . import rigs

CAT = "Clash Rig"
RIG_CHOICES = ["auto (fight sequence)", "auto (cycle by shot)", "random"] + list(rigs.RIGS)
BEAT_CHOICES = ["auto"] + sorted({b for f in rigs.FIGHT_STYLES.values() for b in f["beats"]})
RET_TYPES = ("STRING", "STRING", "STRING", "STRING", "INT", "INT", "INT", "INT", "INT", "INT", "INT", "FLOAT", "INT", "STRING", "STRING")
RET_NAMES = ("plate_prompt", "motion_prompt", "plate_negative", "video_negative", "plate_width", "plate_height",
             "width", "height", "half_width", "half_height", "frames", "fps", "seed", "fx", "label")


def _out(s):
    return (s["plate_prompt"], s["motion_prompt"], s["plate_negative"], s["video_negative"], s["plate_width"], s["plate_height"],
            s["width"], s["height"], s["width"] // 2, s["height"] // 2, s["frames"], float(s["fps"]), s["seed"],
            json.dumps(s["fx"]), s["label"])


def _common(builder=False):
    req = {
        "fight_style": (list(rigs.FIGHT_STYLES), {"default": "anime_power", "tooltip": "boxing, muay_thai, mma, bjj, taekwondo, kung_fu_wuxia or the anime_power flagship."}),
        "style": (["auto"] + list(rigs.STYLES), {"default": "auto", "tooltip": "Visual style. auto = the fight style's own (photoreal; anime for anime_power)."}),
    }
    return req


def _tail(req):
    req.update({
        "beat": (BEAT_CHOICES, {"default": "auto", "tooltip": "Fight beat; auto picks one that suits the rig. A beat from another fight style falls back to auto."}),
        "arena": (list(rigs.ARENAS) + ["custom"], {"default": "floating sky islands"}),
        "light": (list(rigs.LIGHTS), {"default": "arena default"}),
        "intensity": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 1.0, "step": 0.05, "tooltip": "Violence words in the prompt and strength of the rig's FX."}),
        "aspect": (list(rigs.ASPECTS), {"default": "16:9 landscape"}),
        "seconds": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 8.0, "step": 1.0, "tooltip": "0 = the rig's suggested length (2-4 s)."}),
        "shot_index": ("INT", {"default": 0, "min": 0, "max": 999, "control_after_generate": True,
                               "tooltip": "Set to 'increment' and queue N times for N consecutive shots of the fight."}),
        "seed": ("INT", {"default": 7, "min": 0, "max": 2**31 - 1}),
    })
    return req


OPTIONAL = {
    "hero": ("STRING", {"multiline": True, "default": "", "tooltip": "Describe your hero, or 'the fighter in image 1' when using photo refs. Blank = the fight style's original default."}),
    "rival": ("STRING", {"multiline": True, "default": "", "tooltip": "Describe the rival. Blank = default, 'none' = solo."}),
    "arena_custom": ("STRING", {"multiline": True, "default": "", "tooltip": "Your own location; overrides the arena preset when filled."}),
    "extra": ("STRING", {"multiline": True, "default": "", "tooltip": "Appended to both prompts."}),
}


class ClashRig:
    CATEGORY = CAT
    FUNCTION = "run"
    DESCRIPTION = ("Pick a fight style, a hero, a rival, an arena and a camera rig; get the first-frame prompt and the LTX motion "
                   "prompt that shoot it like an over-the-top fight scene. 'auto (fight sequence)' walks a curated 8-shot arc for the "
                   "fight style (opening exchange -> punch-cam -> power moment -> crater/ground -> orbit -> reaction -> crash zoom -> slow-mo finisher).")
    RETURN_TYPES = RET_TYPES
    RETURN_NAMES = RET_NAMES

    @classmethod
    def INPUT_TYPES(cls):
        req = _common()
        req["rig"] = (RIG_CHOICES, {"default": "auto (fight sequence)", "tooltip": "Camera rig, or an auto mode."})
        return {"required": _tail(req), "optional": dict(OPTIONAL)}

    def run(self, fight_style, style, rig, beat, arena, light, intensity, aspect, seconds, shot_index, seed,
            hero="", rival="", arena_custom="", extra=""):
        return _out(rigs.compose(hero=hero, rival=rival, arena=arena, rig=rig, fight_style=fight_style, style=style,
                                 arena_custom=arena_custom, light=light, beat=beat, intensity=intensity, shot_index=shot_index,
                                 seed=seed, aspect=aspect, seconds=seconds, extra=extra))


def _line_node(line):
    ln = rigs.LINES[line]

    class _LineRig:
        CATEGORY = CAT
        FUNCTION = "run"
        DESCRIPTION = (f"{ln['label']}: {ln['blurb']} Keyframe mode (on by default): every shot is one move between a start frame "
                       "and an end frame (end_prompt = one image-edit command on the start frame), rendered with LTX-2.5 first+last frame, "
                       "so strikes land and the fighters stay separate. 'auto (fight sequence)' walks the style's six-shot fight.")
        RETURN_TYPES = RET_TYPES + ("STRING",)
        RETURN_NAMES = RET_NAMES + ("end_prompt",)

        @classmethod
        def INPUT_TYPES(cls):
            req = {
                "fight_style": (ln["fight_styles"], {"default": ln["fight_style"]}),
                "style": (["auto"] + ln["styles"], {"default": "auto", "tooltip": f"Visual style. auto = {ln['style']}."}),
                "rig": (RIG_CHOICES, {"default": "auto (fight sequence)", "tooltip": "Camera rig, or an auto mode."}),
                "keyframes": ("BOOLEAN", {"default": True, "tooltip": "One move per shot between a start and an end frame (LTX first+last frame)."}),
            }
            req = _tail(req)
            req["arena"] = (ln["arenas"] + ["custom"], {"default": ln["arena"]})
            return {"required": req, "optional": dict(OPTIONAL)}

        def run(self, fight_style, style, rig, keyframes, beat, arena, light, intensity, aspect, seconds, shot_index, seed,
                hero="", rival="", arena_custom="", extra=""):
            s = rigs.compose(hero=hero, rival=rival, arena=arena, rig=rig, fight_style=fight_style,
                             style=rigs.line_style(line, fight_style, style), arena_custom=arena_custom, light=light, beat=beat,
                             intensity=intensity, shot_index=shot_index, seed=seed, aspect=aspect, seconds=seconds, extra=extra,
                             keyframes=keyframes)
            return _out(s) + (s["end_prompt"],)

    _LineRig.__name__ = f"Clash{line.title()}Rig"
    return _LineRig


ClashAnimeRig = _line_node("anime")
ClashRealRig = _line_node("real")


class ClashRigBuilder:
    CATEGORY = CAT
    FUNCTION = "run"
    DESCRIPTION = "Build your own camera rig: mount anchor, camera pitch, lens and mount stability, for any fight style and visual style."
    RETURN_TYPES = RET_TYPES
    RETURN_NAMES = RET_NAMES

    @classmethod
    def INPUT_TYPES(cls):
        req = _common()
        req.update({
            "mount_anchor": (list(rigs.CUSTOM_ANCHORS), {"default": "glove (punch-cam)"}),
            "camera_pitch": (list(rigs.CUSTOM_PITCHES), {"default": "level"}),
            "lens_profile": (list(rigs.CUSTOM_LENSES), {"default": "24mm wide"}),
            "mount_stability": (list(rigs.CUSTOM_STABILITY), {"default": "rigid", "tooltip": "rigid shudders most; gimbal is smooth; handheld is raw."}),
        })
        return {"required": _tail(req), "optional": dict(OPTIONAL)}

    def run(self, fight_style, style, mount_anchor, camera_pitch, lens_profile, mount_stability, beat, arena, light, intensity,
            aspect, seconds, shot_index, seed, hero="", rival="", arena_custom="", extra=""):
        return _out(rigs.compose_custom_rig(
            fight_style=fight_style, style=style, mount_anchor=mount_anchor, camera_pitch=camera_pitch, lens_profile=lens_profile,
            mount_stability=mount_stability, beat=beat, hero=hero, rival=rival, arena=arena, arena_custom=arena_custom, light=light,
            intensity=intensity, shot_index=shot_index, seed=seed, aspect=aspect, seconds=seconds, extra=extra))


class ClashPlate:
    CATEGORY = CAT
    FUNCTION = "run"
    DESCRIPTION = ("Optional closed-model first frame (Codex CLI), off-GPU so the whole GPU stays free for LTX-2.5. "
                   "Pass hero_ref and rival_ref to lock both fighters. The open-weights workflows use Z-Image / Qwen Image Edit instead.")
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "plate_prompt": ("STRING", {"multiline": True, "forceInput": True}),
                "width": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
                "height": ("INT", {"default": 576, "min": 256, "max": 2048, "step": 64}),
                "backend": (["codex"], {"default": "codex"}),
                "seed": ("INT", {"default": 7, "min": 0, "max": 2**31 - 1}),
            },
            "optional": {"hero_ref": ("IMAGE",), "rival_ref": ("IMAGE",)},
        }

    def run(self, plate_prompt, width, height, backend="codex", seed=7, hero_ref=None, rival_ref=None):
        import numpy as np
        import torch
        from PIL import Image

        from . import plate_gen
        cache = Path(tempfile.gettempdir()) / "clash_rig_plates"
        cache.mkdir(parents=True, exist_ok=True)
        refs = []
        for tag, tensor in (("hero", hero_ref), ("rival", rival_ref)):
            if tensor is not None:
                arr = (tensor[0].detach().cpu().numpy().clip(0, 1) * 255).astype(np.uint8)
                p = cache / f"ref_{tag}_{hashlib.sha1(arr.tobytes()).hexdigest()[:10]}.png"
                if not p.exists():
                    Image.fromarray(arr).save(p)
                refs.append(p)
        key = hashlib.sha1(f"{plate_prompt}|{width}x{height}|{backend}|{seed}|{[r.name for r in refs]}".encode()).hexdigest()[:12]
        dest = cache / f"plate_{key}.png"
        plate_gen.generate_plate(plate_prompt, dest, width=width, height=height, refs=refs, backend=backend)
        with Image.open(dest) as im:
            return (torch.from_numpy(np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0).unsqueeze(0),)


class ClashRigList:
    CATEGORY = CAT
    FUNCTION = "run"
    DESCRIPTION = "Every fight style with its beats and sequence, camera rig and arena in the library, as text."
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("library",)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    def run(self):
        lines = []
        for k, f in rigs.FIGHT_STYLES.items():
            lines.append(f"FIGHT STYLE {k}: {f['label']} (default arena: {f['arena']})")
            lines += [f"  {i:02d}. {r} -> {b}" for i, (r, b) in enumerate(f["sequence"], 1)]
            lines += [f"  - beat [{b['kind']}] {n}" for n, b in f["beats"].items()]
        lines += ["", "CAMERA RIGS"] + [f"- {n} [{rigs.GROUPS[r['group']]}, {r['seconds']} s]: {r['motion'].split('.')[0]}." for n, r in rigs.RIGS.items()]
        lines += ["", "ARENAS"] + [f"- {k}: {v['scene']}" for k, v in rigs.ARENAS.items()]
        return ("\n".join(lines),)


class ClashFX:
    CATEGORY = CAT
    FUNCTION = "run"
    DESCRIPTION = ("Impact effects on decoded frames: hit flashes, camera shake and jolts, chromatic punch, radial speed lines, anime "
                   "impact frames and a speed ramp. Connect the rig's fx output for its defaults; any slider >= 0 overrides. "
                   "Frame count is unchanged, so audio stays in sync.")
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)

    @classmethod
    def INPUT_TYPES(cls):
        ov = lambda tip: ("FLOAT", {"default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05, "tooltip": tip})
        return {
            "required": {
                "images": ("IMAGE",),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05, "tooltip": "Scales every effect. 0 = bypass."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**31 - 1}),
            },
            "optional": {
                "fx": ("STRING", {"forceInput": True}),
                "fps": ("FLOAT", {"forceInput": True}),
                "shake": ov("-1 = rig default"), "flash": ov("hit flash. -1 = rig default"), "impact": ov("anime impact frame. -1 = rig default"),
                "chroma": ov("-1 = rig default"), "speed_lines": ov("-1 = rig default"), "ramp": ov("speed ramp. -1 = rig default"),
            },
        }

    def run(self, images, strength, seed, fx="", fps=24.0, **overrides):
        from . import fx as clash_fx
        base = json.loads(fx) if fx else {}
        amt = {}
        for k in clash_fx.KEYS:
            v = overrides.get(k, -1.0)
            amt[k] = (v if v is not None and v >= 0 else float(base.get(k, 0.0))) * strength
        if strength <= 0 or not any(amt.values()):
            return (images,)
        return (clash_fx.apply(images, seed=seed, fps=fps or 24.0, **amt),)


class ClashReel:
    CATEGORY = CAT
    FUNCTION = "run"
    OUTPUT_NODE = True
    DESCRIPTION = ("Stitch the last N shots saved under a prefix (oldest first) into one reel: hard cuts, the first frames of each "
                   "shot trimmed, LTX audio kept. Queue your shots first, then run this on its own.")
    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("reel", "shots")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prefix": ("STRING", {"default": "clash_rig/shot", "tooltip": "SaveVideo filename_prefix of the shots."}),
            "count": ("INT", {"default": 8, "min": 1, "max": 64}),
            "trim_frames": ("INT", {"default": 6, "min": 0, "max": 48, "tooltip": "Frames cut from the start of each shot."}),
            "fps": ("INT", {"default": 24, "min": 1, "max": 60}),
        }}

    @classmethod
    def IS_CHANGED(cls, **kw):
        return float("nan")

    def run(self, prefix, count, trim_frames, fps):
        import time

        import folder_paths
        from comfy_api.input_impl import VideoFromFile

        from . import reel
        out = Path(folder_paths.get_output_directory())
        sub, stem = (out / prefix).parent, Path(prefix).name
        clips = sorted(sub.glob(f"{stem}_*.mp4"), key=lambda p: p.stat().st_mtime)[-count:]
        if not clips:
            raise FileNotFoundError(f"no shots matching {sub}/{stem}_*.mp4: queue some Clash Rig shots first")
        dest = Path(tempfile.gettempdir()) / f"clash_reel_{int(time.time())}.mp4"
        reel.assemble(clips, dest, fps=fps, trim_frames=trim_frames)
        return (VideoFromFile(str(dest)), "\n".join(c.name for c in clips))


NODE_CLASS_MAPPINGS = {"ClashAnimeRig": ClashAnimeRig, "ClashRealRig": ClashRealRig, "ClashRig": ClashRig, "ClashRigBuilder": ClashRigBuilder, "ClashPlate": ClashPlate,
                       "ClashRigList": ClashRigList, "ClashFX": ClashFX, "ClashReel": ClashReel}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ClashAnimeRig": "Clash Anime Rig (anime power fights)", "ClashRealRig": "Clash Real Rig (boxing, MMA, Muay Thai, taekwondo, BJJ)",
    "ClashRig": "Clash Rig (preset rig)", "ClashRigBuilder": "Clash Rig Builder (custom mount & lens)",
    "ClashPlate": "Clash Plate (closed partner models, optional)", "ClashRigList": "Clash Rig Library",
    "ClashFX": "Clash FX (impact)", "ClashReel": "Clash Reel (stitch shots)",
}
