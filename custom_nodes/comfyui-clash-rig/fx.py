"""Clash FX: in-camera impact effects for a decoded clip (IMAGE batch, T x H x W x C, 0..1).

shake        camera vibration (multi-frequency jitter + roll) with a kick on every hit
flash        hit flash: the frame blows out to white on each hit and decays over a few frames, with a small punch-in
impact       anime impact frame on each hit: one frame of stark inverted high-contrast ink
chroma       lens chromatic fringing toward the edges, stronger on hits
speed_lines  radial speed lines streaming out from the center, flickering every frame, pulsing on hits
ramp         speed ramp with the same frame count: fast in, slow in the middle, fast out
All amounts are 0..1. Frame count never changes, so LTX's audio stays in sync. Hit times come from the seed.
"""
from __future__ import annotations

import math

import torch
import torch.nn.functional as F

KEYS = ("shake", "flash", "impact", "chroma", "speed_lines", "ramp")


def hit_frames(T: int, flash: float, impact: float, seed: int) -> list[int]:
    n = round(1 + 3 * max(flash, impact))
    if T < 8 or max(flash, impact) <= 0:
        return []
    rng = torch.Generator().manual_seed(int(seed) & 0x7FFFFFFF)
    lo, hi = int(T * 0.15), int(T * 0.92)
    slots = torch.linspace(lo, hi, n + 1)[:-1] + torch.rand(n, generator=rng) * ((hi - lo) / (n + 1))
    return sorted({int(s) for s in slots})


def _warp_time(x: torch.Tensor, ramp: float) -> torch.Tensor:
    t = x.shape[0]
    if ramp <= 0 or t < 3:
        return x
    u = torch.linspace(0, 1, t)
    src = (u + 0.6 * min(ramp, 1.0) * torch.sin(2 * math.pi * u) / (2 * math.pi)).clamp(0, 1) * (t - 1)
    lo = src.floor().long().clamp(0, t - 1)
    hi = (lo + 1).clamp(max=t - 1)
    w = (src - lo.float()).view(-1, 1, 1, 1)
    return x[lo] * (1 - w) + x[hi] * w


def _sample(x, scale, tx, ty, rot):
    inv = 1.0 / scale
    cos, sin = torch.cos(rot) * inv, torch.sin(rot) * inv
    theta = torch.stack([torch.stack([cos, -sin, tx], -1), torch.stack([sin, cos, ty], -1)], 1)
    grid = F.affine_grid(theta, list(x.shape), align_corners=False)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=False)


def apply(images: torch.Tensor, shake=0.0, flash=0.0, impact=0.0, chroma=0.0, speed_lines=0.0, ramp=0.0, seed=0,
          fps=24.0, chunk=8) -> torch.Tensor:
    if images.ndim != 4 or images.shape[0] == 0:
        return images
    T, H, W, _ = images.shape
    x = _warp_time(images.float(), ramp)
    g = torch.Generator().manual_seed(int(seed) & 0x7FFFFFFF)
    t = torch.arange(T, dtype=torch.float32) / float(fps)
    hits = hit_frames(T, flash, impact, seed)
    fr = torch.arange(T, dtype=torch.float32)
    kick = torch.zeros(T)  # 1 on a hit frame, decaying over ~4 frames
    for h in hits:
        kick = torch.maximum(kick, torch.where(fr >= h, torch.exp(-(fr - h) / 1.6), torch.zeros(T)))
    hit_mask = torch.zeros(T)
    for h in hits:
        hit_mask[h] = 1.0

    scale = 1.0 + 0.04 * shake + 0.07 * min(1.0, flash + 0.3 * shake) * kick
    tx = torch.zeros(T); ty = torch.zeros(T); rot = torch.zeros(T)
    if shake > 0:
        for hz, amp in ((2.3, 1.0), (5.1, 0.6), (11.7, 0.35), (17.9, 0.2)):
            ph = torch.rand(3, generator=g) * 2 * math.pi
            tx += amp * torch.sin(2 * math.pi * hz * t + ph[0])
            ty += amp * torch.sin(2 * math.pi * hz * 1.13 * t + ph[1])
            rot += amp * torch.sin(2 * math.pi * hz * 0.87 * t + ph[2])
        jolt = kick * torch.sign(torch.sin(fr * 5.3))  # sharp alternating jolt right after each hit
        tx = tx * 0.012 * shake + jolt * 0.03 * shake
        ty = ty * 0.016 * shake - kick * 0.02 * shake
        rot = rot * math.radians(0.5) * shake + jolt * math.radians(1.2) * shake

    yy, xx = torch.meshgrid(torch.linspace(-1, 1, H), torch.linspace(-1, 1, W), indexing="ij")
    r = torch.sqrt((xx * W / H) ** 2 + yy ** 2) / math.sqrt((W / H) ** 2 + 1)
    edge = (r / 0.75).clamp(0, 1) ** 1.6
    ang = torch.atan2(yy, xx * W / H)
    vignette = 1.0 - 0.15 * (r.clamp(0, 1) ** 2)
    nbins = 160
    ring = ((r - 0.22) / 0.5).clamp(0, 1)
    ring = ring * ring * (3 - 2 * ring)

    out = []
    for s in range(0, T, chunk):
        e = min(T, s + chunk)
        c = x[s:e].permute(0, 3, 1, 2)
        base = _sample(c, scale[s:e], tx[s:e], ty[s:e], rot[s:e])
        k = kick[s:e].view(-1, 1, 1, 1)
        if chroma > 0:
            d = 0.003 * chroma * (1 + 2.5 * k.view(-1))
            rch = _sample(c[:, :1], scale[s:e] * (1 + d), tx[s:e], ty[s:e], rot[s:e])
            bch = _sample(c[:, 2:3], scale[s:e] * (1 - d), tx[s:e], ty[s:e], rot[s:e])
            w = (edge + 0.5 * k.view(-1, 1, 1)).clamp(0, 1)
            base = torch.cat([base[:, :1] + (rch - base[:, :1]) * w[:, None], base[:, 1:2],
                              base[:, 2:3] + (bch - base[:, 2:3]) * w[:, None]], 1)
        base = base * vignette
        if speed_lines > 0:
            tab = torch.rand(e - s, nbins, generator=g)
            bins = ((ang + math.pi) / (2 * math.pi) * nbins).long().clamp(0, nbins - 1)
            lines = (tab[:, bins] > (0.9 - 0.12 * speed_lines)).float() * ring
            gain = (0.35 + 0.65 * k.view(-1, 1, 1)).clamp(0, 1) * min(1.0, 0.4 + speed_lines)
            base = base + (1.0 - base) * (lines * gain)[:, None] * 0.85
        if impact > 0:
            hm = hit_mask[s:e].view(-1, 1, 1, 1) * min(1.0, impact * 1.5)
            if hm.any():
                lum = base.mean(1, keepdim=True)
                ink = ((1.0 - lum) * 2.2 - 0.55).clamp(0, 1)
                ink = ink + 0.9 * (ring * (tab[:, bins] > 0.82).float() if speed_lines > 0 else ring * 0)[:, None]
                base = base * (1 - hm) + hm * ink.clamp(0, 1).expand(-1, 3, -1, -1)
        if flash > 0:
            fl = (k * min(1.0, flash)).clamp(0, 1) * 0.9
            base = base + (1.0 - base) * fl
        out.append(base.permute(0, 2, 3, 1))
    return torch.cat(out, 0).clamp(0, 1).to(images.dtype)
