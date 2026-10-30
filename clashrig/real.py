"""Clash Real: real-life fights shot like a fight film: boxing, MMA, Muay Thai, taekwondo and Brazilian jiu-jitsu, one clean
technique per shot. Keyframe mode is on: each shot is one move between a start frame and an end frame, rendered with LTX-2.5
first+last frame and LTX audio, then Clash FX and a stitched reel. Shares the Clash Rig engine.

    python -m clashrig.real --style-fight taekwondo --seed 7 --out runs/clash-real/tkd1
        [--style-fight boxing|mma|muay_thai|taekwondo|bjj] [--arena "rain alley"] [--hero "an original ..."] [--rival "..."]
        [--hero-photo me.png] [--plate-backend local|codex] [--drop 3] [--reseed 2] [--dry-run]
"""
import sys

from clashrig.runner import main

if __name__ == "__main__":
    main(sys.argv[1:], line="real", doc=__doc__)
