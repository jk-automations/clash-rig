"""Clash Rig app config: controls, library and shot preview. The generic engine is server.py."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "custom_nodes" / "comfyui-clash-rig"
MODULE = "clashrig"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"clash_rig_{name}", PACK / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rigs = _load("rigs")
MODEL_PATTERNS = [("ltx-2.5", "LTX-2.5 22B distilled"), ("z_image_turbo", "Z-Image Turbo"), ("qwen_image_edit", "Qwen Image Edit 2511"),
                  ("lightning", "Qwen Lightning 4-step LoRA"), ("gemma", "Gemma text encoder"), ("qwen_3_4b", "Qwen3 4B (Z-Image text encoder)"),
                  ("qwen_2.5_vl", "Qwen2.5-VL 7B (Qwen Edit text encoder)")]

CONFIG = {
    "name": "Clash Rig",
    "tagline": "Fight-scene cinematography for LTX-2.5: fight styles, arenas, camera rigs and impact FX. Two identity refs keep both fighters the same in every shot; everything runs on open weights through Comfy API v2.",
    "topline": "Open weights by default  /  ComfyUI graphs  /  Comfy API v2",
    "accent": "#ff3d5a", "accent_ink": "#1f0309", "port": 8812, "plan": True, "render_label": "Render fight",
    "node_classes": ["^Clash"],
    "models": [{"name": n, "match": [p]} for p, n in MODEL_PATTERNS],
    "stack": [
        {"stage": "Shot planning", "model": "Clash Rig node", "nodes": "ClashRig / ClashRigBuilder", "why": "Fight style + beat + rig + arena -> first-frame prompt, LTX motion prompt, FX defaults."},
        {"stage": "Fighter sheets", "model": "Z-Image Turbo (bf16)", "nodes": "UNETLoader · CLIPLoader(qwen_3_4b) · KSampler", "why": "One character sheet per fighter, or your own photo."},
        {"stage": "Plates", "model": "Qwen Image Edit 2511 + Lightning 4-step LoRA", "nodes": "TextEncodeQwenImageEditPlus · LoraLoaderModelOnly · KSampler", "why": "Both sheets go into every plate so faces and outfits do not drift."},
        {"stage": "Video + audio", "model": "LTX-2.5 22B distilled", "nodes": "LTXVImgToVideoInplace · LTXVDualCFGGuider · LTXVLatentUpsampler · LTXVAudioVAEDecode", "why": "Two-stage image-to-video with synchronized impact audio; Gemma text encoder."},
        {"stage": "Impact FX", "model": "Clash FX node", "nodes": "ClashFX", "why": "Hit flashes, shake, chromatic punch, speed lines, impact frames, speed ramp."},
        {"stage": "Reel", "model": "Clash Reel node", "nodes": "ClashReel", "why": "Hard cuts, wake-up frames trimmed, LTX audio kept."},
    ],
    "nodes": [{"name": "Clash Rig", "what": "preset rig -> prompts, sizes, FX"}, {"name": "Clash Rig Builder", "what": "mount, pitch, lens, stability"},
              {"name": "Clash Rig Library", "what": "library as text"}, {"name": "Clash FX", "what": "impact effects"}, {"name": "Clash Reel", "what": "stitch shots"},
              {"name": "Clash Plate (Codex, optional)", "what": "closed-model first frame"}],
    "uploads": [
        {"id": "hero_photo", "label": "Hero photo (you, or anyone you have rights to)", "flag": "--hero-photo", "help": "Optional. Becomes the hero identity ref."},
        {"id": "rival_photo", "label": "Rival photo", "flag": "--rival-photo", "help": "Optional."},
    ],
    "controls": [
        {"id": "title", "label": "Run name", "type": "text", "default": "", "group": "Fight", "placeholder": "optional"},
        {"id": "fight_style", "label": "Fight style", "type": "select", "options": "fight_styles", "default": "anime_power", "flag": "--style-fight", "group": "Fight"},
        {"id": "arena", "label": "Arena", "type": "select", "options": "arenas", "default": "", "flag": "--arena", "group": "Fight"},
        {"id": "rig", "label": "Camera rig", "type": "select", "options": "rigs", "default": "auto (fight sequence)", "flag": "--rig", "group": "Fight"},
        {"id": "beat", "label": "Fight beat", "type": "select", "options": "beats", "default": "auto", "flag": "--beat", "group": "Fight"},
        {"id": "shots", "label": "Shots", "type": "number", "min": 1, "max": 12, "step": 1, "default": 4, "flag": "--shots", "group": "Fight"},
        {"id": "seconds", "label": "Seconds per shot (0 = rig default)", "type": "number", "min": 0, "max": 8, "step": 1, "default": 0, "flag": "--seconds", "group": "Fight"},
        {"id": "style", "label": "Visual style", "type": "select", "options": "styles", "default": "auto", "flag": "--style", "group": "Look"},
        {"id": "light", "label": "Light", "type": "select", "options": "lights", "default": "arena default", "flag": "--light", "group": "Look"},
        {"id": "aspect", "label": "Aspect", "type": "select", "options": "aspects", "default": "16:9 landscape", "flag": "--aspect", "group": "Look"},
        {"id": "intensity", "label": "Impact intensity", "type": "range", "min": 0, "max": 1, "step": 0.05, "default": 0.85, "flag": "--intensity", "group": "Look"},
        {"id": "seed", "label": "Seed", "type": "number", "min": 0, "max": 2147483647, "default": 7, "flag": "--seed", "group": "Look"},
        {"id": "plate_backend", "label": "Plate backend", "type": "select", "options": [{"v": "local", "l": "local: Z-Image Turbo + Qwen Image Edit (open weights)"}, {"v": "codex", "l": "codex: optional closed model, needs the Codex CLI"}],
         "default": "local", "flag": "--plate-backend", "group": "Look", "wide": True},
        {"id": "hero", "label": "Hero fighter", "type": "textarea", "default": "", "flag": "--hero", "group": "Fighters", "wide": True, "placeholder": "blank = the fight style's original default"},
        {"id": "rival", "label": "Rival fighter", "type": "textarea", "default": "", "flag": "--rival", "group": "Fighters", "wide": True, "placeholder": "blank = default rival, 'none' = solo"},
        {"id": "arena_custom", "label": "Custom arena", "type": "text", "default": "", "flag": "--arena-custom", "group": "Fighters", "wide": True},
        {"id": "extra", "label": "Extra detail", "type": "text", "default": "", "flag": "--extra", "group": "Fighters", "wide": True},
        {"id": "plates_only", "label": "Plates only", "type": "toggle", "default": False, "flag": "--plates-only", "group": "Run", "help": "Stop after the plates and contact sheet (about 1 min per plate on an M3 Ultra)."},
    ],
}


def library():
    r = rigs
    beats = sorted({b for f in r.FIGHT_STYLES.values() for b in f["beats"]})
    return {
        "fight_styles": [{"v": k, "l": v["label"]} for k, v in r.FIGHT_STYLES.items()],
        "arenas": [{"v": "", "l": "(the fight style's own)"}] + [{"v": k, "l": k} for k in r.ARENAS],
        "styles": [{"v": "auto", "l": "auto (the fight style's own)"}] + [{"v": k, "l": v["label"]} for k, v in r.STYLES.items()],
        "rigs": [{"v": k, "l": k} for k in ("auto (fight sequence)", "auto (cycle by shot)", "random")] + [{"v": k, "l": f"{k}  ({r.GROUPS[v['group']]}, {v['seconds']} s)"} for k, v in r.RIGS.items()],
        "beats": [{"v": "auto", "l": "auto"}] + [{"v": b, "l": b} for b in beats],
        "lights": [{"v": k, "l": k} for k in r.LIGHTS], "aspects": [{"v": k, "l": k} for k in r.ASPECTS],
    }


def plan(p: dict):
    n = max(1, min(12, int(p.get("shots") or 4)))
    kw = dict(hero=p.get("hero") or "", rival=p.get("rival") or "", arena=p.get("arena") or "", arena_custom=p.get("arena_custom") or "",
              fight_style=p.get("fight_style") or "anime_power", style=p.get("style") or "auto", rig=p.get("rig") or "auto (fight sequence)",
              beat=p.get("beat") or "auto", light=p.get("light") or "arena default", intensity=float(p.get("intensity") or 0.85),
              aspect=p.get("aspect") or "16:9 landscape", seconds=float(p.get("seconds") or 0), extra=p.get("extra") or "", seed=int(p.get("seed") or 7))
    return [{k: s[k] for k in ("label", "rig", "beat", "seconds", "motion_prompt")} for s in (rigs.compose(shot_index=i, **kw) for i in range(n))]
