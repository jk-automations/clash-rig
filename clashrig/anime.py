"""Clash Anime: over-the-top anime power fights (shockwave punch trades, aura power-ups, crater slams, launch uppercuts,
energy-blast finishers) in a clean 2D anime look. Keyframe mode is on: each shot is one move between a start frame and an end
frame, rendered with LTX-2.5 first+last frame and LTX audio, then Clash FX and a stitched reel. Shares the Clash Rig engine.

    python -m clashrig.anime --seed 7 --out runs/clash-anime/fight1
        [--style anime_clean|anime|cyberpunk_anime|comic_graphic_novel|cartoon_3d|synthwave_retro]
        [--hero "an original ..."] [--rival "..."] [--arena "volcanic wasteland"] [--light midday]
        [--plate-backend local|codex] [--drop 3] [--reseed 2] [--dry-run]
"""
import sys

from clashrig.runner import main

if __name__ == "__main__":
    main(sys.argv[1:], line="anime", doc=__doc__)
