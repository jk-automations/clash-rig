"""Clash Rig library: fight styles, camera rigs, arenas and beats for over-the-top fight scenes, compiled into prompts.

Pure Python (no ComfyUI imports), so the node pack, the batch runner and tests all share it.

    shot = compose(fight_style="anime_power", hero="", rival="", arena="floating sky islands",
                   rig="auto (fight sequence)", shot_index=0, intensity=0.85, seed=7)
    shot["plate_prompt"]   # first frame for Z-Image / Qwen Image Edit, camera description first
    shot["motion_prompt"]  # LTX-2.5 prompt: camera move, fight beat, impact cues and sound
    shot["fx"]             # Clash FX defaults for this rig (shake, flash, chroma, speed_lines, impact, ramp)

Fighters are original designs: no real people, no franchises, no brand gear.
"""
from __future__ import annotations

import random

NO_BRAND = ("Original fictional fighter designs, no real people, no brand logos, no sponsor wordmarks and no readable text on gear.")
PLATE_NEG = ("blurry, lowres, watermark, logo, brand logo, text, letters, extra limbs, extra arms, extra fingers, deformed hands, "
             "fused bodies, merged fighters, duplicate fighter, twisted limbs, melted face, crowd of fighters, gore, blood, "
             "split screen, collage, multiple panels, video game HUD, health bar, UI overlay")
LTX_NEG = ("static camera, still frame, frozen, freeze frame, slow motion, standing still, idle pose, text, watermark, logo, "
           "subtitles, video game, HUD, health bar, extra limbs, extra arms, morphing limbs, melting body, rubber arms, "
           "fighters merge together, fighters swap places, face changes, clothing changes, hair changes, brand logos, "
           "camera pulls back, zoom out, fighters leave the frame, gore, blood")

# ----------------------------------------------------------------------------------------------------- visual styles
STYLES = {
    "photoreal": dict(
        label="Ultra Realistic (Large-Format Cinema)",
        plate_desc="Award-winning photorealistic live-action fight cinematography, shot on a large-format cinema camera, gritty sports-drama color grade, authentic optical motion blur on fast limbs, tack-sharp skin and fabric texture",
        motion_desc="Cinematic live-action photorealism, real body weight and impact physics, natural motion blur",
        plate_neg="cartoon, anime, 3d render, cgi, illustration, drawing, painting, lowres",
        video_neg="cartoon, anime, 3d render, cgi, illustration, drawing, plastic skin, unrealistic physics",
        fx_tweak=dict(flash=0.7, chroma=1.0, speed_lines=0.15, impact=0.0, shake=1.0),
    ),
    "anime": dict(
        label="Japanese Anime (Sakuga Action)",
        plate_desc="High-octane Japanese anime aesthetic, dynamic sakuga keyframe animation, bold ink linework, vibrant multi-tone cel shading, hand-painted anime background art, dramatic manga action speed lines, extreme foreshortening",
        motion_desc="Dynamic Japanese anime sakuga animation, hand-drawn smears and multiples on fast limbs, exaggerated impact poses, anime speed streaks, dramatic keyframe action",
        plate_neg="photograph, photorealistic live-action, 3d cgi render, realistic human skin, live-action film",
        video_neg="photograph, photorealistic live-action, realistic 3d cgi, live-action film, realistic human skin",
        fx_tweak=dict(flash=1.3, chroma=1.5, speed_lines=1.4, impact=1.0, shake=1.1),
    ),
    "anime_clean": dict(
        label="Clean 2D Anime (TV Cel)",
        plate_desc="Clean modern 2D TV anime cel animation frame, crisp thin even line art, flat two-tone cel shading with a limited palette, simple uncluttered painted background with plenty of open space, both characters large, readable and clearly lit, no glow",
        motion_desc="Clean 2D anime key animation, snappy fast movement with a few smear frames on the strike, big readable full-body motion, the background stays simple and still",
        plate_neg="photograph, photorealistic live-action, 3d cgi render, realistic human skin, glow everywhere, bloom, lens flare, cluttered background",
        video_neg="photograph, photorealistic live-action, realistic 3d cgi, live-action film, bloom, glow everywhere, flicker",
        fx_tweak=dict(flash=0.6, chroma=0.5, speed_lines=1.0, impact=0.7, shake=1.0),
        calm=True,
    ),
    "cartoon_3d": dict(
        label="Stylized 3D Animation (Comic-Book CG)",
        plate_desc="Stylized 3D animated feature film aesthetic, comic-book CG look, tactile stylized surfaces, expressive exaggerated fighter proportions, volumetric studio lighting, rich saturated color palette",
        motion_desc="Exaggerated animated feature film motion, expressive squash-and-stretch punches, stylized puff impact clouds, playful high-energy pacing",
        plate_neg="photograph, live-action footage, gritty realism, grainy film",
        video_neg="photograph, live-action, gritty realism, grainy film, realistic human skin",
        fx_tweak=dict(flash=1.0, chroma=1.1, speed_lines=0.8, impact=0.3, shake=0.9),
    ),
    "synthwave_retro": dict(
        label="80s Retro Synthwave Arcade",
        plate_desc="1980s retro synthwave aesthetic, vibrant neon magenta and cyan rim light, chrome reflections, wireframe grid accents, glowing horizon sun, subtle VHS phosphor glow",
        motion_desc="High-energy retro 80s arcade brawl motion, glowing neon light streaks on every punch, synthwave aesthetic, pulsing rim light",
        plate_neg="dull colors, modern desaturated film, black and white, earthy tones",
        video_neg="dull colors, modern desaturated film, black and white",
        fx_tweak=dict(flash=1.2, chroma=2.0, speed_lines=0.8, impact=0.4, shake=1.0),
    ),
    "cyberpunk_anime": dict(
        label="Cyberpunk Anime (Neon City)",
        plate_desc="Cyberpunk anime aesthetic, neon-drenched rain reflections, dynamic glowing line accents, high-contrast dark futuristic anime, sharp cel shading",
        motion_desc="Hyper-kinetic cyberpunk anime animation, flashing neon bokeh, electric sparks and light trails on every strike",
        plate_neg="photograph, live-action, daylight countryside, pastel colors, vintage film",
        video_neg="photograph, live-action, realistic film, daylight rural",
        fx_tweak=dict(flash=1.3, chroma=1.8, speed_lines=1.2, impact=0.8, shake=1.1),
    ),
    "comic_graphic_novel": dict(
        label="Comic Book Graphic Novel (Noir / Pop-Art)",
        plate_desc="Stylized graphic novel comic book illustration, heavy black ink cross-hatching, halftone Ben-Day dot shading, dramatic high-contrast noir lighting, graphic pop-art color palette",
        motion_desc="Animated graphic novel motion, dynamic comic panel physics, bold ink motion smears, stylized graphic lighting contrasts",
        plate_neg="photograph, photorealism, soft blur, 3d cgi render",
        video_neg="photograph, photorealism, 3d cgi render, smooth gradients",
        fx_tweak=dict(flash=1.0, chroma=0.8, speed_lines=1.0, impact=0.9, shake=0.9),
    ),
}


def build_negative_prompt(base_neg: str, style_neg: str, style: str) -> str:
    terms = [t.strip() for t in base_neg.split(",") if t.strip()]
    drop = {"anime": ("cartoon", "anime", "illustration", "drawing"), "anime_clean": ("cartoon", "anime", "illustration", "drawing"), "cyberpunk_anime": ("cartoon", "anime", "illustration", "drawing"),
            "cartoon_3d": ("cartoon", "cgi", "3d"), "comic_graphic_novel": ("cartoon", "illustration", "drawing")}.get(style, ())
    terms = [t for t in terms if not any(w in t.lower() for w in drop)]
    return ", ".join(terms + [s for s in (t.strip() for t in style_neg.split(",")) if s and s not in terms])


# ----------------------------------------------------------------------------------------------------- fight styles
# beats: kind is hit | flurry | finisher | defend | react | clash. Rigs ask for kinds; beats name "the hero" and "the rival".
FIGHT_STYLES = {
    "boxing": dict(
        label="Boxing", style="photoreal", arena="boxing ring",
        hero="an original lean female boxer with a short silver-dyed crop and a taped nose bridge, a plain teal sports top, teal satin trunks "
             "with a plain gold waistband, "
             "white hand wraps under crimson gloves, sweat-slick shoulders",
        rival="an original towering bearded male heavyweight boxer with a shaved head and a full-sleeve tattoo of black waves, "
              "matte black trunks with a white stripe, scuffed gold gloves, thick scarred brows",
        sound="gloves thudding on flesh, sharp exhales, canvas shuffling, a roaring crowd, the ring bell clanging",
        hold="Both boxers stay inside the frame in the same fighting range, throwing real punches with correct boxing form; "
             "glove, fist and arm shapes never change.",
        beats={
            "jab cross combo": dict(kind="hit", plate="the hero snapping a stiff jab into the rival's guard with the cross cocked behind it, the rival's head rocking back, sweat spraying",
                                    motion="The hero fires a fast jab then a hard cross, the rival's head snaps back and sweat sprays off his face, then the rival answers with a looping hook the hero ducks under"),
            "body hook": dict(kind="hit", plate="the hero driving a left hook deep into the rival's ribs, the rival folding at the waist, sweat flying",
                              motion="The hero digs a brutal left hook into the rival's ribs, the rival folds and gasps, then straightens and throws a wild right that glances off the hero's shoulder"),
            "counter right hand": dict(kind="hit", plate="the hero slipping a punch and landing a counter right hand square on the rival's jaw, mouthguard edge showing",
                                       motion="The rival throws a big right, the hero slips under it and cracks a counter right hand onto the jaw, the rival's head whips sideways and sweat sprays in an arc"),
            "flurry on the ropes": dict(kind="flurry", plate="the rival pinned against the ropes while the hero unloads a blur of hooks and uppercuts, ropes shaking, gloves smeared by motion",
                                        motion="The hero hammers a nonstop blur of hooks and uppercuts into the pinned rival, the ropes whip and shake with every impact, sweat sprays, the crowd erupts"),
            "knockout haymaker": dict(kind="finisher", plate="a huge overhand right landing flush on the rival's jaw, mouthguard and sweat flying, the rival's legs starting to buckle",
                                      motion="The hero loads up and swings a huge overhand right that detonates on the jaw, sweat and the mouthguard fly out, the rival's eyes glaze and his legs buckle as he falls"),
            "slip and weave": dict(kind="defend", plate="the hero ducking under a swinging hook, torso bent low, the rival's glove cutting through the air above her head",
                                   motion="The rival whips a hook and a cross, the hero weaves under both with her torso, then pops back up with a sharp jab to the face"),
            "stagger and glare": dict(kind="react", plate="the rival reeling from a clean punch with his head turned, eyes wide and furious, sweat spraying off his face",
                                      motion="The rival reels from a clean punch, shakes his head, spits and glares back with furious eyes, sweat flying, then lunges forward"),
        },
        sequence=[("ringside low angle", "jab cross combo"), ("punch-cam", "body hook"), ("over-the-shoulder", "counter right hand"),
                  ("ground-level debris cam", "slip and weave"), ("overhead", "flurry on the ropes"), ("face close-up", "stagger and glare"),
                  ("impact crash zoom", "counter right hand"), ("slow-mo replay push-in", "knockout haymaker")],
    ),
    "muay_thai": dict(
        label="Muay Thai", style="photoreal", arena="boxing ring",
        hero="an original wiry female Muay Thai fighter with a tight black bun and a braided cord headband, bronze-and-black silk shorts, "
             "rope armbands, taped hands and shins, glistening oiled skin",
        rival="an original broad male Muay Thai fighter with a shaved head and a scar through one eyebrow, deep green silk shorts with silver "
              "piping, red wrapped hands, thick tape on his shins",
        sound="shin thwacks on ribs, sharp exhales, ringside drums and a screaming crowd, canvas thumping",
        hold="Both fighters stay inside the frame at kicking range, throwing real Muay Thai kicks, knees and elbows with correct form; "
             "limbs keep their shape.",
        beats={
            "roundhouse kick": dict(kind="hit", plate="the hero's shin smashing into the rival's ribs with a full-power roundhouse kick, the rival's body folding around it, sweat exploding off his skin",
                                    motion="The hero pivots and whips a full-power roundhouse kick into the rival's ribs, the shin thwacks and sweat explodes off his skin, the rival gasps and folds"),
            "elbow slash": dict(kind="hit", plate="the hero's elbow slashing across the rival's brow in close range, heads inches apart, sweat flying",
                                motion="In close range the hero whips a horizontal elbow slash across the rival's brow, his head snaps sideways, sweat flies, he answers with a knee to the hero's guard"),
            "clinch knees": dict(kind="hit", plate="the hero locked in the clinch gripping the rival's neck and driving a knee up into his gut, both fighters straining",
                                 motion="The hero locks the clinch around the rival's neck and drives knee after knee into his gut, the rival's body jerking with each one, the rival fights to break free"),
            "rapid low kicks": dict(kind="flurry", plate="the hero's legs a blur as she chops rapid low kicks into the rival's thigh, the rival hopping on his leg, canvas dust rising",
                                    motion="The hero chops a rapid blur of low kicks into the rival's lead thigh and follows with a teep to the chest, he hops, stumbles back and the canvas shakes"),
            "spinning elbow knockout": dict(kind="finisher", plate="a spinning elbow crashing onto the rival's chin mid-turn, sweat and spit flying, the rival's eyes rolling",
                                            motion="The hero spins a full turn and lands a spinning elbow on the rival's chin, his head rockets back and his body goes limp and drops to the canvas in a heap"),
            "teep kick": dict(kind="hit", plate="the hero's front teep kick planted in the charging rival's chest, the rival bent forward and stopped dead, rain spraying off him",
                              motion="The rival charges in, the hero lifts her knee and spears a front teep kick into his chest, stopping him dead and shoving him backward"),
            "check the kick": dict(kind="defend", plate="the hero lifting her shin to block a hard roundhouse, the two shins cracking together, sweat spraying",
                                   motion="The rival throws a hard roundhouse, the hero lifts her shin and checks it with a crack, then steps in and snaps a counter teep into his stomach"),
            "stunned reaction": dict(kind="react", plate="the rival staggering with a stunned look and his mouth open, chest heaving, sweat dripping off his chin",
                                     motion="The rival staggers back stunned, chest heaving, sweat dripping, then grits his teeth, raises both fists and charges back in"),
        },
        sequence=[("ringside low angle", "roundhouse kick"), ("punch-cam", "clinch knees"), ("whip-pan side profile", "rapid low kicks"),
                  ("over-the-shoulder", "check the kick"), ("handheld shoulder cam", "elbow slash"), ("face close-up", "stunned reaction"),
                  ("impact crash zoom", "roundhouse kick"), ("slow-mo replay push-in", "spinning elbow knockout")],
    ),
    "mma": dict(
        label="MMA", style="photoreal", arena="underground cage",
        hero="an original muscular female mixed martial artist with a thick dark braid and a split lip, charcoal fight shorts with a neon-orange "
             "stripe, a black sports top, fingerless fight gloves, tape on her wrists",
        rival="an original stocky male mixed martial artist with a buzz cut and a cauliflower ear, royal-blue fight shorts with a white lightning "
              "stripe, fingerless fight gloves, a bruised cheekbone",
        sound="fist thuds, bare feet slapping the mat, the chain-link cage rattling, a roaring crowd, heavy breathing",
        hold="Both fighters stay inside the frame in the same fighting range, striking and grappling with real mixed martial arts technique; "
             "bodies and limbs keep their shape.",
        kf_hold="There are exactly two fighters, one in charcoal shorts and one in royal-blue shorts. Every arm and leg keeps its shape "
                "and no third person appears.",
        beats={
            "jab into double-leg": dict(kind="hit", plate="the hero faking a jab and shooting a double-leg takedown, the rival's weight tipping backward off his feet",
                                        motion="The hero fires a jab, drops her level and shoots a double-leg, driving the rival off his feet and slamming him down while he scrambles"),
            "cage-wall knees": dict(kind="hit", plate="the rival pinned against the chain-link cage wall as the hero drives knees into his body, the fence bulging",
                                    motion="The hero pins the rival against the cage wall and drives knee after knee into his body, the chain-link bulges and rattles, he grabs her waist to survive"),
            "high kick": dict(kind="hit", plate="the hero's high kick snapping up and connecting with the rival's temple, the rival's head whipping sideways",
                              motion="The hero feints low then snaps a high kick that cracks into the rival's temple, his head whips sideways and he stumbles into the fence"),
            "ground and pound": dict(kind="flurry", plate="the hero mounted on the rival on the mat, raining fast strikes down on his guard, his forearms covering his face",
                                     motion="The hero mounts the rival and rains a blur of fast strikes down on his guard, his forearms shake as he bucks his hips and tries to roll her off"),
            "flying knee": dict(kind="finisher", plate="the hero leaping with a flying knee mid-air a hand's width from the rival's chin, her hair flying",
                                motion="The hero launches off the mat with a flying knee that crashes into the rival's chin, his head snaps back and he collapses against the cage as she lands in a crouch"),
            "sprawl": dict(kind="defend", plate="the hero sprawling her hips back to stop a takedown, her hands pushing down on the rival's shoulders, his face near the mat",
                           motion="The rival shoots for a takedown, the hero sprawls her hips back, stuffs it and spins behind him as he scrambles to his knees"),
            "gasp for air": dict(kind="react", plate="the rival on one knee with chest heaving, sweat dripping off his chin, jaw clenched, staring up with hate",
                                 motion="The rival drops to one knee gasping, sweat dripping off his chin, clenches his jaw and drags himself back to his feet"),
        },
        sequence=[("ringside low angle", "jab into double-leg"), ("handheld shoulder cam", "cage-wall knees"), ("punch-cam", "high kick"),
                  ("overhead", "ground and pound"), ("ground-level debris cam", "sprawl"), ("face close-up", "gasp for air"),
                  ("impact crash zoom", "high kick"), ("slow-mo replay push-in", "flying knee")],
    ),
    "bjj": dict(
        label="Brazilian Jiu-Jitsu", style="photoreal", arena="dojo",
        hero="an original compact female jiu-jitsu fighter with a high dark ponytail, a plain bright white gi and a black belt, barefoot",
        rival="an original big male jiu-jitsu fighter with a shaved head and a salt-and-pepper beard, a plain dark navy-blue gi and a brown belt, barefoot",
        sound="gi fabric snapping and ripping, mat thumps, labored breathing, sharp grunts, a hand slapping the mat for the tap",
        hold="Both grapplers stay inside the frame, tangled together, using real jiu-jitsu technique with correct grips and joint angles; "
             "arms and legs keep their shape and nothing fuses together.",
        kf_hold="There are exactly two grapplers, one in a white gi and one in a navy gi. The two gis never blend together, every arm and "
                "leg keeps its shape, and no third person appears.",
        beats={
            "double-leg takedown": dict(kind="hit", plate="the hero shooting in low and lifting the rival off his feet with a double-leg takedown, his back about to hit the mat",
                                        motion="The hero drops her level, shoots in, wraps both of the rival's legs and drives him off his feet onto his back on the mat"),
            "guard pull": dict(kind="defend", plate="the hero sitting down and pulling the rival into her closed guard, her legs locked around his waist",
                               motion="The hero grips the rival's collar and sleeve, sits to the mat and pulls him down into her closed guard, locking her legs around his waist"),
            "tap out": dict(kind="finisher", plate="the rival caught in an armbar, his face twisted in pain, his free hand slapping the mat",
                            motion="The hero arches her hips on the armbar, the rival's face twists in pain and he slaps the mat twice to tap out"),
            "guard pass": dict(kind="hit", plate="the hero driving through the rival's guard, shoulder pressed on his chest and his knees pinned to the mat, gi collars twisted in her fists",
                               motion="The hero grinds through the rival's guard, pins his knees to the mat and slides her shoulder across his chest, gi fabric twisting, the rival frantically frames against her"),
            "scissor sweep": dict(kind="hit", plate="the hero on her back sweeping the rival over with a scissor sweep, his body mid-flip over her legs",
                                  motion="From her back the hero scissors her legs, yanks the rival's sleeve and flips him over onto the mat, rolling up on top in a flash"),
            "armbar": dict(kind="finisher", plate="the hero wrapped around the rival's arm in a tight armbar, her legs clamped across his chest, his arm stretched and fist clenched",
                           motion="The hero clamps her legs across the rival's chest, pulls his arm straight and arches her hips, his face twists in pain, he slaps the mat twice to tap out"),
            "triangle choke": dict(kind="finisher", plate="the hero's legs locked in a triangle choke around the rival's neck and arm, his face red and eyes wide",
                                   motion="The hero locks the triangle around the rival's neck and arm and squeezes, his face flushes red as he struggles, then he slaps the mat in surrender"),
            "rolling scramble": dict(kind="flurry", plate="both grapplers rolling in a fast scramble across the mat, limbs and gi tangled, bodies blurred in motion",
                                     motion="Both grapplers explode into a fast rolling scramble, limbs and gi tangling, each fighting for the top position, flipping over each other with thumps on the mat"),
            "escape the hold": dict(kind="defend", plate="the hero bridging and twisting out from under the rival's side control, her hips high and one hand framing his neck",
                                    motion="The hero bridges her hips high, shrimps out from under the rival's side control and recovers her guard while he lunges after her"),
            "gasping reaction": dict(kind="react", plate="the rival's face twisted in a grimace, veins showing, teeth gritted, sweat dripping while he strains to hold on",
                                     motion="The rival grits his teeth, veins bulging, sweat dripping as he strains and fights to hold position, then explodes into a desperate scramble"),
        },
        sequence=[("ringside low angle", "guard pass"), ("overhead", "scissor sweep"), ("handheld shoulder cam", "rolling scramble"),
                  ("ground-level debris cam", "escape the hold"), ("bullet-time orbit", "triangle choke"), ("face close-up", "gasping reaction"),
                  ("impact crash zoom", "scissor sweep"), ("slow-mo replay push-in", "armbar")],
    ),
    "taekwondo": dict(
        label="Taekwondo", style="photoreal", arena="temple courtyard",
        hero="an original lean young male taekwondo fighter with a short black undercut tied in a small topknot, a plain white dobok with a "
             "black belt, barefoot",
        rival="an original tall athletic female taekwondo fighter with a sharp red bob, a plain black dobok with a red belt, barefoot",
        sound="sharp kicks snapping against bodies, dobok fabric cracking, bare feet sliding on stone, sharp kihap shouts",
        hold="Both fighters stay fully inside the frame from head to feet at kicking range, throwing real taekwondo kicks with correct form; "
             "legs, feet and arms keep their shape.",
        beats={
            "back kick": dict(kind="hit", plate="the hero's straight back kick buried in the rival's stomach, his head turned over his shoulder, the rival folding and sliding back",
                              motion="The hero spins and drives a straight back kick into the rival's stomach, she folds and slides backward"),
            "spinning hook kick": dict(kind="hit", plate="the hero's heel whipping across the rival's jaw in a spinning hook kick, her head snapping sideways",
                                       motion="The hero spins and whips a spinning hook kick, his heel clipping the rival's jaw and snapping her head sideways"),
            "double roundhouse": dict(kind="flurry", plate="the hero's roundhouse kick landing on the rival's ribs, his leg horizontal, her body bending sideways",
                                      motion="The hero fires two fast roundhouse kicks off the same leg, the second slapping into the rival's ribs"),
            "axe kick evade": dict(kind="defend", plate="the rival's axe kick crashing down an inch in front of the hero's face as he leans back out of range",
                                   motion="The rival raises her leg high and brings an axe kick crashing down, the hero sways back and it misses his face by inches"),
            "glare": dict(kind="react", plate="the rival turning back from a kick with her red hair flying and furious eyes",
                          motion="The rival turns back from the kick, breathing hard, hair settling, eyes furious"),
            "tornado kick": dict(kind="finisher", plate="the hero airborne in a spinning tornado kick, his foot smashing into the side of the rival's head, her body twisting away",
                                 motion="The hero leaps into a spinning tornado kick and his foot smashes into the side of the rival's head, she spins away and starts to fall"),
        },
        sequence=[("whip-pan side profile", "back kick"), ("ringside low angle", "spinning hook kick"), ("face close-up", "glare"),
                  ("bullet-time orbit", "axe kick evade"), ("whip-pan side profile", "double roundhouse"), ("slow-mo replay push-in", "tornado kick")],
    ),
    "kung_fu_wuxia": dict(
        label="Kung Fu / Wuxia Wire-Work", style="photoreal", arena="bamboo forest",
        hero="an original swift young swordless monk with a long white braid, flowing indigo robes with a gold sash and bare forearms wrapped in cloth",
        rival="an original tall masked wandering warrior in black-and-crimson layered robes with a wide straw hat, a long iron-tipped wooden staff and a scarf trailing in the wind",
        sound="whooshing robes, wooden staff cracks, palms slapping, bamboo creaking and snapping, wind chimes, a distant gong",
        hold="Both warriors stay inside the frame while leaping, spinning and striking with graceful real martial arts form and wire-work flight; "
             "robes flow but limbs and weapons keep their shape.",
        beats={
            "flying kick": dict(kind="hit", plate="the hero soaring through the air with a flying side kick across the swaying bamboo tops, robes streaming, the rival blocking with his staff",
                                motion="The hero leaps off a bamboo stalk and flies at the rival with a flying side kick, the rival blocks with his staff, the crack echoes and both spin away through the swaying bamboo"),
            "palm strike": dict(kind="hit", plate="the hero's palm striking the rival's chest and sending a ring of dust and leaves outward, the rival skidding backward",
                                motion="The hero strikes a palm to the rival's chest, a ring of leaves and dust bursts outward, and the rival skids backward on his heels through the fallen leaves"),
            "staff clash": dict(kind="clash", plate="the rival's staff and the hero's forearm locked in a clash with sparks of light, bamboo leaves exploding outward, both fighters leaning in",
                                motion="The rival sweeps his staff at the hero, who catches it on her forearm, the clash sends bursts of leaves outward and both spin, kick off the staff and trade rapid blows"),
            "wall-run flurry": dict(kind="flurry", plate="the hero running up a stone wall mid-flurry with the rival chasing on the opposite wall, kicks and palm strikes blurring between them",
                                    motion="The hero and the rival run up opposite walls trading a blur of kicks and palm strikes mid-air, robes whipping, then spin and leap from wall to wall in a rapid chase"),
            "rising crane kick": dict(kind="finisher", plate="the hero launching skyward with a rising crane kick that lifts the rival off the ground, a burst of dust and bamboo leaves beneath them",
                                      motion="The hero crouches, then launches upward in a rising kick that lifts the rival into the air, bamboo leaves explode outward, and the rival crashes down against a stalk"),
            "flowing block": dict(kind="defend", plate="the hero blocking a staff strike with flowing sleeves and a turning wrist, her body leaning away with the staff passing an inch from her cheek",
                                  motion="The rival jabs and sweeps the staff, the hero turns her wrists with flowing sleeves, deflects each strike, then spins inside and taps the rival's chest"),
            "stoic stare": dict(kind="react", plate="the rival's masked eyes narrowing in a cold stare, robes and scarf flying in a sudden gust, bamboo leaves swirling around him",
                                motion="The rival stands in a gust of wind, scarf and robes whipping, bamboo leaves swirling, narrowing his eyes, then spins his staff and charges"),
        },
        sequence=[("sky-high wide", "flying kick"), ("ringside low angle", "staff clash"), ("whip-pan side profile", "wall-run flurry"),
                  ("over-the-shoulder", "flowing block"), ("bullet-time orbit", "palm strike"), ("face close-up", "stoic stare"),
                  ("impact crash zoom", "flying kick"), ("slow-mo replay push-in", "rising crane kick")],
    ),
    "anime_power": dict(
        label="Anime Power Fight", style="anime", arena="floating sky islands",
        hero="an original young warrior with long swept-back silver hair, a torn black-and-gold battle coat with a high collar, bare scarred fists "
             "and a blazing electric-blue energy aura crackling around his whole body, glowing cyan eyes",
        rival="an original towering horned warlord with crimson skin, spiked black armor with glowing violet runes, a tattered cape and a "
              "roaring violet-and-magenta energy aura wreathing his body, burning gold eyes",
        sound="deafening shockwave booms, crackling energy, thunderous punches, rock slabs cracking and grinding, a rising electric roar",
        hold="Both warriors stay inside the frame, fighting hand to hand at insane speed with their auras blazing; they keep their exact faces, "
             "hair, armor, aura colors and proportions, and never merge together.",
        beats={
            "teleport punch flurry": dict(kind="flurry", plate="the hero vanishing and reappearing in blurred afterimages all around the rival, dozens of punches landing in one instant, a white shockwave ring blooming from every impact, speed lines everywhere",
                                          motion="The hero blinks around the rival in streaking afterimages, appearing on every side and landing dozens of punches in a single instant, each hit blooming a white shockwave ring and a flash, the rival's armor cracking, debris floating upward"),
            "beam clash": dict(kind="clash", plate="a huge blue beam from the hero and a huge violet beam from the rival colliding in the center in a blinding sphere of crackling light, the ground cracking, rocks levitating, both warriors screaming",
                               motion="The hero and the rival thrust their hands forward and fire opposing energy beams that crash together in a blinding sphere, the sphere swells and arcs lightning, the ground cracks, rocks levitate, then the blue beam surges forward and engulfs the rival in an explosion of white"),
            "crater impact slam": dict(kind="hit", plate="the hero slamming the rival into the ground with a downward punch, a deep crater bursting open with a circular shockwave, rock slabs and debris flying upward",
                                       motion="The hero dives like a comet and drives a punch into the rival, who slams into the ground, a crater blasts open with a ring of dust and a white flash, rock slabs and debris fly upward and hang in the air"),
            "shockwave punch trade": dict(kind="hit", plate="the hero's fist and the rival's fist colliding mid-air at the center of a giant shockwave ring that tears the clouds apart, white flash and speed lines, both warriors roaring",
                                          motion="The hero and the rival rocket toward each other and trade punches mid-air, each collision creating a giant shockwave ring that rips the clouds apart in a white flash, they bounce apart and slam together again"),
            "aura power-up": dict(kind="react", plate="the hero screaming as his blazing electric-blue aura erupts upward, hair and coat whipping, pebbles and rubble levitating, lightning arcing across the ground",
                                  motion="The hero screams and his blue aura erupts upward in a pillar of light, his hair and coat whip wildly, pebbles and slabs of rock levitate, lightning arcs along the ground and the whole island shakes as the sky darkens"),
            "launch uppercut chase": dict(kind="finisher", plate="the hero's rising uppercut launching the rival into the sky with a trail of light, the hero streaking up after him through torn clouds, speed lines and a shockwave ring below",
                                          motion="The hero's uppercut launches the rival skyward in a flash and a shockwave ring, the hero rockets after him leaving a trail of blue light, clouds tear apart, he catches up and hammers him with a kick that spins him through the air"),
            "energy blast finisher": dict(kind="finisher", plate="the hero firing a point-blank energy blast into the rival, the whole frame flooded with white light, a mushrooming explosion and a giant shockwave ring racing outward",
                                          motion="The hero cups his hands, gathers a glowing sphere and fires it point blank into the rival, the entire screen floods with white, a giant explosion mushrooms and a shockwave ring races across the sky, then the light fades on drifting embers"),
            "block and counter": dict(kind="defend", plate="the rival blocking the hero's strike on crossed forearms with ripples of energy exploding off the guard, his boots carving trenches into the rock as he skids back",
                                      motion="The hero's punch lands on the rival's crossed forearms in a ripple of energy, the rival skids back carving trenches into the rock, then bursts forward with a counter punch that sends the hero spinning backward"),
        },
        sequence=[("sky-high wide", "shockwave punch trade"), ("punch-cam", "teleport punch flurry"), ("ringside low angle", "aura power-up"),
                  ("ground-level debris cam", "crater impact slam"), ("bullet-time orbit", "beam clash"), ("face close-up", "aura power-up"),
                  ("impact crash zoom", "launch uppercut chase"), ("slow-mo replay push-in", "energy blast finisher")],
        fx_mult=dict(flash=1.25, speed_lines=1.25, impact=1.25, shake=1.15),
        energy=True,
    ),
}

# ----------------------------------------------------------------------------------------------------- arenas
ARENAS = {
    "boxing ring": dict(
        scene="a professional boxing ring under hard overhead spotlights, taut ropes, a worn canvas with scuff marks, and a dark smoky arena packed with a roaring crowd",
        light="hot white overhead ring lights, dark crowd beyond, haze in the light beams", sound="a roaring crowd"),
    "underground cage": dict(
        scene="a rusted chain-link fight cage in a concrete basement, bare bulbs, graffiti walls and a shouting crowd pressed against the fence",
        light="harsh swinging industrial bulbs, deep shadows, dust in the air", sound="a shouting crowd rattling the fence"),
    "dojo": dict(
        scene="a traditional wooden-floored dojo with paper screen walls, hanging scrolls, rows of wooden weapons on the wall and soft mats",
        light="warm lantern glow with sunlight streaming through paper screens", sound="quiet room echo"),
    "rooftop at night": dict(
        scene="a gravel rooftop at night above a glittering skyline, water tanks, antennas and flickering signage in the distance",
        light="cool moonlight with colored neon spill from below, wind-whipped", sound="city wind and distant traffic"),
    "rain alley": dict(
        scene="a narrow brick alley in a downpour, puddles reflecting neon signs, steam from vents, dumpsters and fire escapes",
        light="neon sign glow on wet bricks, heavy rain streaks, mist", sound="pouring rain and splashing puddles"),
    "volcanic wasteland": dict(
        scene="a black volcanic wasteland with rivers of glowing lava, jagged obsidian spires and a sky of ash and embers",
        light="orange lava glow from below, dark red sky, drifting embers", sound="rumbling earth and hissing lava"),
    "floating sky islands": dict(
        scene="a floating island of ancient stone ruins high above an ocean of clouds, with other islands drifting in the distance, waterfalls spilling into the sky and a vast sunset behind",
        light="blazing golden sunset, god rays through the clouds, dramatic orange and purple sky", sound="rushing wind and a distant rumble"),
    "desert canyon": dict(
        scene="a red sandstone desert canyon with towering cliffs, wind-carved arches and drifting sand",
        light="harsh low sun, long shadows, hot orange dust haze", sound="howling desert wind"),
    "neon city": dict(
        scene="a futuristic neon megacity street with towering holographic billboards, flying traffic overhead and rain-slick pavement",
        light="saturated magenta and cyan neon, reflective wet ground, light haze", sound="humming neon and distant sirens"),
    "temple courtyard": dict(
        scene="a wide open stone temple courtyard with a carved wooden gate, stone lanterns and misty mountains beyond",
        light="warm low golden-hour sun with long shadows", sound="wind and temple bells"),
    "bamboo forest": dict(
        scene="a misty bamboo forest with tall swaying green stalks, a stone path and fallen leaves, mountain peaks in the haze",
        light="soft green dawn light filtered through bamboo, drifting mist", sound="creaking bamboo and wind"),
    "ruined stadium": dict(
        scene="a collapsed concrete stadium with cracked terraces, twisted steel and rubble, open to a stormy sky",
        light="stormy grey light with shafts of sun through broken roofing, drifting dust", sound="distant thunder and falling rubble"),
}

LIGHTS = {
    "arena default": None,
    "golden hour": "golden hour, low warm sun, long shadows, lens flare",
    "blue hour": "blue hour dusk, deep blue sky, rim lights glowing",
    "night": "night, hard spotlights cutting through the dark, deep shadows",
    "midday": "bright midday sun, hard shadows, high contrast",
    "overcast": "soft overcast light, moody grey sky, rich colors",
    "storm": "storm light, flashes of lightning, rain streaks, dark clouds",
    "blood moon": "huge red moon, crimson rim light, ember sparks in the air",
}

# ----------------------------------------------------------------------------------------------------- camera rigs
# kinds: which beat kinds suit the rig. group picks the hold-subject wording. slow=True allows slow motion.
RIGS = {
    "ringside low angle": dict(
        group="wide", lens="24mm wide", kinds=["hit", "defend", "clash"],
        plate="Low-angle ringside shot from the floor looking up at the two fighters in mid exchange, the lens a foot above the ground, {arena}, {action}",
        motion="Low camera on the floor at ringside, tilted up at the two fighters. They trade violent blows above the lens, feet slamming into the ground, bodies looming huge, the camera shudders with each impact and tracks sideways with the exchange.",
        fx=dict(shake=0.55, flash=0.5, chroma=0.3, speed_lines=0.3, impact=0.3, ramp=0.0), seconds=3),
    "punch-cam": dict(
        group="mount", lens="ultra-wide action camera", kinds=["flurry", "hit"],
        plate="First-person punch-cam from a camera mounted on the hero's glove and forearm, the hero's fist and wrist large in the lower foreground flying toward the rival's face, ultra-wide lens, {arena}, {action}",
        motion="Camera mounted on the hero's fist. The fist hammers forward again and again into the rival's guard and face, the lens snapping toward the target with each punch, the background whirling, the frame lurching violently on every impact.",
        fx=dict(shake=0.85, flash=0.7, chroma=0.5, speed_lines=0.6, impact=0.5, ramp=0.0), seconds=3),
    "over-the-shoulder": dict(
        group="wide", lens="35mm", kinds=["hit", "defend", "flurry"],
        plate="Over-the-shoulder shot from behind the hero's shoulder, the back of the hero's head and shoulder large and out of focus on one side of the frame, the rival facing the lens ahead mid-exchange, {arena}, {action}",
        motion="Over-the-shoulder camera locked behind the hero. The hero's shoulder and head jerk with each throw, the rival lunges and reels in front of the lens, the camera lurches and bobs with the fighters, the exchange raw and fast.",
        fx=dict(shake=0.6, flash=0.5, chroma=0.3, speed_lines=0.3, impact=0.3, ramp=0.0), seconds=3),
    "impact crash zoom": dict(
        group="wide", lens="35mm to 85mm snap zoom", kinds=["hit", "finisher"],
        plate="Dramatic framing with both fighters at medium distance, the instant before impact, a punch frozen an inch from the rival's face, {arena}, {action}",
        motion="The camera snap-zooms violently into the point of impact as the blow lands, the frame jolts and shakes, the fighters recoil, the camera pushes in again on the next blow, the background streaking.",
        fx=dict(shake=0.7, flash=0.8, chroma=0.7, speed_lines=0.6, impact=0.7, ramp=0.4), seconds=3),
    "bullet-time orbit": dict(
        group="orbit", lens="28mm", kinds=["clash", "hit", "finisher"], slow=True,
        plate="Wide orbiting shot with both fighters frozen mid-strike in the center, a punch and a kick connecting, debris and sweat hanging in the air around them, the {arena} wrapping around them, {action}",
        motion="360-degree bullet-time orbit around the two fighters at the instant of impact, the camera circling smoothly around them at constant speed while the action plays out in slowed time: sweat, sparks and debris hang in the air as the strike lands and the fighters recoil, the background wrapping around.",
        fx=dict(shake=0.2, flash=0.6, chroma=0.5, speed_lines=0.2, impact=0.2, ramp=0.5), seconds=4),
    "overhead": dict(
        group="aerial", lens="24mm", kinds=["flurry", "hit", "finisher"],
        plate="Top-down overhead shot from directly above the two fighters, looking straight down, bodies and limbs radiating from the center of the fight on the {arena}, {action}",
        motion="Camera hanging directly above, looking straight down. The two fighters circle, lunge and grapple on the floor below, limbs whipping outward, the floor exploding with dust and scuffs, the camera rotating and drifting with the fight.",
        fx=dict(shake=0.4, flash=0.5, chroma=0.3, speed_lines=0.2, impact=0.3, ramp=0.0), seconds=3),
    "slow-mo replay push-in": dict(
        group="wide", lens="85mm", kinds=["finisher", "hit"], slow=True,
        plate="Replay-style tight shot on the decisive blow, a fist or foot landing on the rival with sweat and debris suspended in the air, both fighters filling the frame, shallow depth of field, {arena}, {action}",
        motion="Slow-motion replay with a steady push-in on the decisive blow. The strike lands and the rival's body ripples with the impact, sweat, dust and debris float and spin in the air, flashes of light ripple, then the rival falls away as the camera keeps pushing in.",
        fx=dict(shake=0.2, flash=0.9, chroma=0.7, speed_lines=0.3, impact=0.6, ramp=0.8), seconds=4),
    "sky-high wide": dict(
        group="wide", lens="18mm", kinds=["clash", "hit", "flurry"],
        plate="Epic sky-high wide shot from far above and behind, the two fighters as small figures colliding at the center of the frame, huge {arena} sweeping out below, {action}",
        motion="Epic wide camera high in the sky, tracking and swooping after the two tiny fighters as they collide, split apart and collide again at insane speed, every impact blasting an expanding shockwave ring across the landscape below, clouds and debris whipping past.",
        fx=dict(shake=0.5, flash=0.9, chroma=0.5, speed_lines=0.8, impact=0.6, ramp=0.0), seconds=4),
    "ground-level debris cam": dict(
        group="wide", lens="14mm ultra-wide", kinds=["hit", "defend", "finisher"],
        plate="Ground-level shot with the lens a few centimeters off the floor, dust, rubble and debris in the foreground, the two fighters in a violent exchange behind it, {arena}, {action}",
        motion="Camera skimming the ground. Boots slam down next to the lens, dust and rubble kick up and fly past the lens, shockwaves of grit roll along the ground, the fighters clash in the background, the camera shudders.",
        fx=dict(shake=0.7, flash=0.6, chroma=0.4, speed_lines=0.4, impact=0.4, ramp=0.0), seconds=3),
    "face close-up": dict(
        group="close", lens="85mm portrait", kinds=["react"],
        plate="Extreme close-up on the face of the rival, filling the frame, the hero's glove or fist entering the edge of the frame, sweat droplets and wide furious eyes, {arena} blurred behind, {action}",
        motion="Extreme close-up on a fighter's face. A blow lands out of frame, the head whips, cheeks ripple and sweat droplets spray across the lens, the eyes snap from shock to fury, the face comes back at the camera.",
        fx=dict(shake=0.5, flash=0.5, chroma=0.6, speed_lines=0.2, impact=0.3, ramp=0.2), seconds=2),
    "handheld shoulder cam": dict(
        group="wide", lens="28mm", kinds=["hit", "flurry", "defend"],
        plate="Handheld documentary shoulder-cam shot a few meters from the fight, slightly canted, both fighters tangled in a close exchange, {arena}, {action}",
        motion="Raw handheld shoulder camera dodging and weaving around the fight. The operator stumbles, whips toward each blow, reframes late, the lens catches sweat and dust, the fighters crash toward the camera.",
        fx=dict(shake=0.9, flash=0.5, chroma=0.4, speed_lines=0.2, impact=0.2, ramp=0.0), seconds=3),
    "hero low-angle upshot": dict(
        group="close", lens="24mm", kinds=["react", "hit", "finisher"],
        plate="Heroic low-angle upshot from the ground looking up at the hero in a power pose, the rival looming behind, the sky or ceiling above, {arena}, {action}",
        motion="Low heroic camera tilting up at the hero, who throws a savage strike, hair and clothes whipping, the camera pushing in with a shudder and tilting to follow the swing.",
        fx=dict(shake=0.5, flash=0.7, chroma=0.5, speed_lines=0.5, impact=0.4, ramp=0.0), seconds=3),
    "whip-pan side profile": dict(
        group="wide", lens="35mm", kinds=["flurry", "hit", "clash"],
        plate="Side-on profile shot of the two fighters at the same height in a dead-even exchange, a kick and a punch crossing in the center, {arena}, {action}",
        motion="Side-on tracking camera racing alongside the two fighters in profile, whip-panning to catch each blow, the fighters charge across the frame at speed trading kicks and punches, the background streaking in a smear.",
        fx=dict(shake=0.6, flash=0.5, chroma=0.4, speed_lines=0.7, impact=0.3, ramp=0.0), seconds=3),
    "rival POV": dict(
        group="mount", lens="14mm ultra-wide", kinds=["hit", "finisher"],
        plate="First-person shot from the rival's eyes, the hero's fist and snarling face rushing toward the lens, motion blur on the arm, {arena}, {action}",
        motion="Camera in the rival's point of view. The hero's fists and furious face rush at the lens, blows land on the camera with a jolt, the picture whips sideways, white flashes and ringing, then the rival swings back.",
        fx=dict(shake=0.9, flash=1.0, chroma=0.8, speed_lines=0.5, impact=0.6, ramp=0.0), seconds=3),
    "drone dive follow": dict(
        group="aerial", lens="ultra-wide FPV", kinds=["flurry", "clash", "hit"],
        plate="FPV drone shot diving fast toward the two fighters from above at an angle, ultra-wide lens with the fighters mid-strike at the center, {arena} rushing below, {action}",
        motion="FPV drone dives at the fighters, weaves around them as they clash, swoops through the gap between a punch and a kick, banks and loops around their exchange at breakneck speed, the surroundings smearing past.",
        fx=dict(shake=0.7, flash=0.6, chroma=0.5, speed_lines=0.7, impact=0.4, ramp=0.0), seconds=3),
}

HOLD = {
    "mount": "The camera is fixed to the fighter's fist or head, so the fist or the view stays locked in the same place in the frame; the camera never pulls back and never separates.",
    "wide": "Both fighters stay large in the frame the whole time, always in the same fighting range; the camera keeps pace, never falls behind and never loses them.",
    "close": "The face or the hero stays large in the frame the whole time; the camera never pulls back.",
    "orbit": "Both fighters stay in the center of the frame at the same size while the camera circles them.",
    "aerial": "Both fighters stay in the frame the whole time; the camera keeps pace, never pulls back and never loses them.",
}

SPEED = [
    (0.34, "fast", "", "hard hits"),
    (0.67, "brutal and very fast", "intense, ", "heavy, punishing hits"),
    (1.01, "insanely fast and violent", "violent, relentless, ", "bone-shaking, thunderous hits"),
]

ASPECTS = {
    "16:9 landscape": (768, 448, 1024, 576),
    "9:16 vertical": (448, 768, 576, 1024),
    "2.35:1 cinema": (896, 384, 1152, 512),
}

ENERGY_PLATE = "Blazing energy auras, glowing particles, shockwave rings, levitating debris, cracked ground and flares of white light. "
ENERGY_MOTION = ("Energy auras flicker and roar, every impact flashes white and blasts out a shockwave ring, debris levitates and flies, "
                 "stark impact frames and speed lines punctuate each hit. ")


# ----------------------------------------------------------------------------------------------------- keyframe mode
# Keyframe mode: every shot is one beat between a start plate and an end plate (LTX first+last frame), so the strike has
# somewhere to land. Free-running i2v smeared multi-punch combos and pulled the fighters into each other. Z-Image composes the
# start plate (it follows pose and camera; Qwen Edit with the ref sheets copied the refs' guard pose into every shot), then one
# short Qwen Edit command turns it into the end plate.
# beat -> (start plate: who is where doing what, the single motion, end plate edit command)
KF = {
    "boxing": {
        "jab cross combo": (
            "On the left, {hero}, in her stance with her left jab starting to extend toward the rival's face and her right glove at her chin. "
            "On the right, {rival}, in a high guard. Open space between them, only these two fighters.",
            "The hero snaps a jab into the rival's guard, then fires a hard right cross that lands on his chin; his head turns away from the punch and sweat sprays",
            "Make the woman on the left land a right cross: her right arm fully extended with her glove on the man's chin, his head turned away "
            "from the punch, sweat spraying off his face, her left glove back at her own chin."),
        "body hook": (
            "On the left, {hero}, crouched low with her left glove drawn back at her hip, about to throw a hook to the body. On the right, "
            "{rival}, standing tall with his gloves up by his face. Open space between them, only these two fighters.",
            "The hero dips and drives a left hook into the rival's ribs; he folds over the punch and his guard drops",
            "Make the woman on the left land her left hook to the body: her bent left arm driving her glove into the side of the man's ribs, "
            "the man folded forward over the punch with his gloves dropped and his mouth open in pain."),
        "counter right hand": (
            "On the right, {rival}, swinging a wide right hand at the head of the fighter on the left. On the left, {hero}, bending her knees "
            "to slip under it. Only these two fighters.",
            "The rival swings a wide right hand, the hero slips under it and comes up with a right hand that lands on his jaw; his head whips sideways",
            "Make the woman on the left counter: the man's right arm has swung past her head and missed, and her right glove lands on his jaw, "
            "his head whipped to the side."),
        "slip and weave": (
            "On the right, {rival}, throwing a looping left hook. On the left, {hero}, bending low at the knees and ducking under it. "
            "Only these two fighters.",
            "The rival throws a looping hook; the hero bends at the knees and rolls under it, his glove passing above her head, then she rises back into her stance",
            "Make the woman on the left rise back up into her stance after ducking under the hook, and make the man stumble off balance with "
            "his left arm swung across his own body."),
        "stagger and glare": (
            "of the face of {rival}, his head turned to the side from a punch, eyes squeezed shut, sweat flying off his beard, blurred ring "
            "lights behind him.",
            "The rival's head is turned from a punch; he slowly turns back to face the camera, breathing hard, sweat dripping, eyes furious",
            "Turn the man's head so he faces the camera straight on, jaw clenched, eyes wide open and furious, sweat dripping from his brow."),
        "knockout haymaker": (
            "On the left, {hero}, her right glove drawn far back behind her shoulder, ready to throw. On the right, {rival}, his gloves low "
            "and his chin exposed. Open space between them, only these two fighters.",
            "In slow motion the hero throws an overhand right that lands flush on the rival's jaw; his head turns, sweat sprays off his face and his knees start to give",
            "Make the woman's right hand land flush on the man's jaw: her right arm fully extended into his face, his head snapped to the "
            "side, a spray of sweat in the air, his knees buckling as he starts to fall."),
    },
    "anime_power": {
        "shockwave punch trade": (
            "On the left, {hero}, flying toward the right with his right fist drawn back. On the right, {rival}, flying toward the left with "
            "his fist drawn back. A wide gap of open sky between them, only these two warriors.",
            "The two warriors fly at each other and their fists meet in the middle; a ring-shaped shockwave bursts out from the point of contact and pushes the clouds back",
            "Make the two warriors' fists collide in the center of the frame: the left warrior's fist pressed against the right warrior's "
            "fist, a ring-shaped white shockwave bursting outward from the contact point and blowing the clouds back, both bodies still apart."),
        "aura power-up": (
            "On the left, {hero}, standing with his feet planted and his fists low, a faint blue glow around his body. On the right in the "
            "distance, {rival}, watching. Only these two warriors.",
            "The hero clenches his fists and his blue aura flares up around him; small rocks around his feet lift off the ground",
            "Make the left warrior clench his fists and scream, his blue aura blazing high above his head, small rocks floating up around his "
            "feet, his hair and coat whipping upward."),
        "block and counter": (
            "On the left, {hero}, throwing a straight punch. On the right, {rival}, raising crossed forearms to block it. Only these two warriors.",
            "The hero's punch hits the rival's crossed forearms; energy ripples off the block and the rival skids back across the rock",
            "Make the right warrior skid back several steps behind his crossed forearms, violet energy rippling on his guard, dust trailing "
            "behind his boots, the left warrior's fist still extended, open space between them."),
        "crater impact slam": (
            "Above, {hero}, diving down head first with his fist drawn back. Below, {rival}, on the rocky ground looking up. Only these two warriors.",
            "The hero drops from above and drives a downward punch into the rival's chest; the rival slams into the ground and a crater cracks open under him, rocks flying up",
            "Make the diving warrior's fist land in the chest of the warrior below, who is slammed onto his back into a fresh crater, rocks "
            "and dust flying up around them."),
        "launch uppercut chase": (
            "On the left, {hero}, crouched low under the chin of the warrior on the right, his right fist drawn down by his hip. On the right, "
            "{rival}. Only these two warriors.",
            "The hero drives an uppercut into the rival's chin and launches him upward, a trail of light following him into the sky",
            "Make the left warrior throw an uppercut: his fist raised high, and the right warrior launched upward near the top of the frame "
            "with a trail of light below him."),
        "energy blast finisher": (
            "On the left, {hero}, with both palms drawn back at his hip around a glowing blue sphere. On the right, {rival}, charging toward "
            "him. Only these two warriors.",
            "In slow motion the hero thrusts both palms forward and releases a blue energy blast that hits the rival in the chest and blows him backward",
            "Make the left warrior thrust both palms forward and fire a blue energy beam into the right warrior's chest, the right warrior bent "
            "backward and blown away, light flooding the right half of the frame while the left warrior stays clearly visible."),
    },
    "taekwondo": {
        "back kick": (
            "Full figures from head to bare feet. On the left, {hero}, turned with his back toward the woman on the right, looking at her "
            "over his shoulder, his right knee drawn up to his chest. On the right, {rival}, stepping in with her hands up. Open space "
            "between them, only these two fighters.",
            "The man spins and drives a straight back kick into the woman's stomach; she folds over and slides backward",
            "Make the man on the left land a back kick: his right leg fully extended straight back with his heel in the woman's stomach, "
            "his head turned looking over his shoulder, the woman folded forward and pushed back, her feet sliding."),
        "spinning hook kick": (
            "Full figures from head to bare feet. On the left, {hero}, mid-spin with his back half turned and his right leg starting to "
            "swing up behind him. On the right, {rival}, in a high guard. Open space between them, only these two fighters.",
            "The man finishes his spin and whips a spinning hook kick; his heel sweeps across and clips the woman's jaw and her head snaps sideways",
            "Make the man's spinning hook kick land: his right leg extended high with his heel at the woman's jaw, her head turned away "
            "from the kick and her red hair flying, his arms out for balance."),
        "glare": (
            "of the face of {rival}, her head turned to the side from a kick, eyes squeezed shut, red hair flying across her face.",
            "The woman's head is turned from the kick; she slowly turns back to face the camera, breathing hard, eyes furious",
            "Turn the woman's head so she faces the camera straight on, jaw clenched, eyes wide open and furious, her red hair settling."),
        "axe kick evade": (
            "Full figures from head to bare feet. On the right, {rival}, standing on one leg with her right leg raised straight up high "
            "above her head for an axe kick. On the left, {hero}, leaning back with his hands up. Only these two fighters.",
            "The woman brings an axe kick crashing down; the man sways back and her heel misses his face by inches and slams into the ground",
            "Make the woman's raised leg come down: her right heel now on the ground in front of the man after missing, the man leaning "
            "back out of range with his hands up, both fully visible and apart."),
        "double roundhouse": (
            "Full figures from head to bare feet. On the left, {hero}, balanced on his left leg with his right knee chambered at hip "
            "height, about to kick. On the right, {rival}, with her guard up. Open space between them, only these two fighters.",
            "The man snaps two fast roundhouse kicks off the same leg; the second one slaps into the woman's ribs",
            "Make the man's roundhouse kick land: his right leg straight and horizontal with his instep on the woman's ribs, the woman "
            "bending sideways away from the kick, her arms dropped."),
        "tornado kick": (
            "Full figures from head to bare feet. On the left, {hero}, launching into a jumping spin, both feet leaving the ground, his "
            "body turned. On the right, {rival}, in an open guard. Open space between them, only these two fighters.",
            "In slow motion the man leaps into a spinning tornado kick, his right foot swings round and smashes into the side of the woman's head, and she twists away and starts to fall",
            "Make the man's tornado kick land: he is in the air with his right leg extended and his foot on the side of the woman's head, "
            "the woman twisted and falling sideways, her red hair flying."),
    },
    "muay_thai": {
        "roundhouse kick": (
            "Full figures from head to feet. On the left, {hero}, pivoting on her left foot with her right shin swinging up toward the "
            "man's ribs. On the right, {rival}, with his hands up by his face. Open space between them, only these two fighters.",
            "The woman whips a full-power roundhouse kick; her shin slams into the man's ribs and he folds around it as water sprays off his skin",
            "Make the woman's roundhouse land: her right shin pressed into the man's ribs, her leg horizontal, the man folded sideways "
            "over the kick with his mouth open, water spraying off his body."),
        "check the kick": (
            "Full figures from head to feet. On the right, {rival}, swinging a roundhouse kick at the woman's thigh. On the left, {hero}, "
            "lifting her left knee to block it. Only these two fighters.",
            "The man's roundhouse kick crashes into the woman's raised shin; she checks it and his leg bounces off",
            "Make the woman check the kick: her raised left shin blocking the man's shin, the man's leg bounced back and his body off "
            "balance, both fully visible and apart except for the shins."),
        "elbow slash": (
            "On the left, {hero}, in close range with her right elbow raised high and pointed at the man's brow. On the right, {rival}, "
            "with his guard low. Waist-up framing, only these two fighters.",
            "The woman whips a horizontal elbow across the man's brow and his head snaps sideways",
            "Make the woman's elbow land: her right elbow across the man's brow, his head snapped to the side, water spraying off his face, "
            "her left hand still up at her own chin."),
        "stunned reaction": (
            "of the face of {rival}, staggering with his mouth open and eyes unfocused, rainwater dripping from his chin.",
            "The man blinks, shakes his head, grits his teeth and glares at the camera",
            "Make the man's face clench: teeth gritted, eyes focused and furious, looking straight at the camera."),
        "teep kick": (
            "Full figures from head to feet. On the left, {hero}, with her right knee lifted high at her chest, about to push-kick. On "
            "the right, {rival}, charging forward with his hands up. Open space between them, only these two fighters.",
            "The woman spears a front teep kick into the man's chest; he stops dead and is shoved backward",
            "Make the woman's teep land: her right leg straight forward with the sole of her foot in the man's chest, the man bent forward "
            "and pushed back, his feet sliding through a puddle."),
        "spinning elbow knockout": (
            "Full figures from head to feet. On the left, {hero}, mid-turn with her back toward the man and her right elbow raised. On "
            "the right, {rival}, stepping forward. Only these two fighters.",
            "In slow motion the woman spins and her elbow lands on the man's chin; his head snaps back and his knees give way",
            "Make the spinning elbow land: the woman's right elbow on the man's chin, his head snapped back, his knees buckling as he "
            "falls, water spraying."),
    },
    "mma": {
        "jab into double-leg": (
            "Full figures from head to feet. On the left, {hero}, dropping her level low with her hands reaching for the man's legs. On "
            "the right, {rival}, standing tall throwing a jab over her head. Only these two fighters.",
            "The woman shoots a double-leg, wraps both of the man's legs and slams him onto his back on the mat",
            "Make the woman finish the takedown: the man now flat on his back on the mat, the woman on her knees at his hips pinning his "
            "legs, her braid swinging."),
        "high kick": (
            "Full figures from head to feet. On the left, {hero}, balanced on her left leg with her right leg rising toward the man's "
            "head. On the right, {rival}, with his hands low. Open space between them, only these two fighters.",
            "The woman snaps a high kick; her shin cracks into the side of the man's head and his head whips sideways",
            "Make the woman's high kick land: her right shin on the side of the man's head, her leg straight and high, his head whipped "
            "sideways and his body tipping toward the cage."),
        "gasp for air": (
            "of the face of {rival}, down on one knee with his chest heaving, sweat dripping off his chin, jaw clenched.",
            "The man drags in a breath, clenches his jaw and lifts his eyes to the camera",
            "Make the man look straight at the camera with furious eyes, jaw clenched, sweat dripping."),
        "sprawl": (
            "Full figures from head to feet. On the right, {rival}, diving forward at the woman's legs for a takedown. On the left, "
            "{hero}, starting to throw her hips back. Only these two fighters.",
            "The man shoots for her legs; the woman sprawls her hips back and flattens him to the mat",
            "Make the woman sprawl: her hips thrown back and her legs stretched behind her, her chest pressing down on the man's shoulders, "
            "the man flattened face down on the mat."),
        "ground and pound": (
            "of {hero} sitting on top of {rival} in mount on the mat, seen from directly above, her right fist drawn back, his forearms "
            "up over his face. Only these two fighters.",
            "The woman drops a hard right hand down onto the man's guard; his forearms buckle and his head bounces on the mat",
            "Make the woman's right fist land on the man's forearms over his face, her arm extended downward, his head pushed back "
            "against the mat, seen from directly above."),
        "flying knee": (
            "Full figures from head to feet. On the left, {hero}, leaping off the mat with her right knee driving up. On the right, "
            "{rival}, stepping in with his chin up. Open space between them, only these two fighters.",
            "In slow motion the woman's flying knee crashes into the man's chin; his head snaps back and he falls back against the cage",
            "Make the flying knee land: the woman in the air with her right knee on the man's chin, his head snapped back and his arms "
            "flung out as he falls against the cage."),
    },
    "bjj": {
        "double-leg takedown": (
            "Full figures from head to bare feet, standing on the mats. On the left, {hero}, crouched low with her level dropped, about "
            "to shoot in at the man's legs. On the right, {rival}, standing tall and reaching for her collar. Open space between them, "
            "only these two grapplers.",
            "The woman shoots in, wraps both of the man's legs and drives him off his feet; he falls onto his back on the mat",
            "Make the woman finish a double-leg takedown: the man in the navy gi now flat on his back on the mat, the woman in the white "
            "gi kneeling at his hips with her arms around his legs."),
        "guard pull": (
            "Full figures from head to bare feet, standing on the mats. On the left, {hero}, gripping the man's collar and sleeve at "
            "arm's length. On the right, {rival}, gripping her collar. Only these two grapplers.",
            "The woman sits down to the mat and pulls the man down into her closed guard, locking her legs around his waist",
            "Make the woman pull guard: she is on her back on the mat with her legs locked around the waist of the man in the navy gi, "
            "who kneels upright between her legs, still gripping her collar."),
        "scissor sweep": (
            "of {hero} on her back on the mat with {rival} kneeling in her guard, both seen from directly above, the white gi and the "
            "navy gi clearly separate. Only these two grapplers.",
            "The woman scissors her legs and flips the man over onto his back, then rolls up on top of him",
            "Make the sweep complete: the man in the navy gi now on his back on the mat, the woman in the white gi sitting on top of his "
            "chest in mount, seen from directly above."),
        "gasping reaction": (
            "of the face of {rival}, lying on the mat with his cheek pressed to it, teeth gritted, sweat dripping, the collar of his navy gi "
            "twisted.",
            "The man strains, veins bulging, then lifts his head and stares at the camera with wide eyes",
            "Lift the man's head off the mat so he stares at the camera with wide desperate eyes, teeth still gritted."),
        "armbar": (
            "of {hero} sitting on top of {rival} in mount, both seen from directly above on the mat, her hands gripping his right wrist. "
            "Only these two grapplers.",
            "The woman swings her leg over the man's head and falls back into an armbar, pulling his arm straight",
            "Make an armbar seen from directly above: the woman in the white gi lying on her back at a right angle to the man, both her "
            "legs across his chest, his straight right arm held along her body with both her hands on his wrist."),
        "tap out": (
            "Full figures, side-on, low on the mat. {hero} lying on her back with both legs across the chest of {rival}, holding his "
            "straight arm in an armbar. Only these two grapplers.",
            "The woman arches her hips; the man's face twists in pain and he slaps the mat twice with his free hand",
            "Make the man tap: his free left hand flat on the mat mid-slap, his face twisted in pain, the woman's hips arched up under "
            "his straightened arm."),
    },
}
KF_SEQUENCE = {
    "taekwondo": [("whip-pan side profile", "back kick"), ("ringside low angle", "spinning hook kick"), ("face close-up", "glare"),
                  ("bullet-time orbit", "axe kick evade"), ("whip-pan side profile", "double roundhouse"), ("slow-mo replay push-in", "tornado kick")],
    "muay_thai": [("ringside low angle", "roundhouse kick"), ("whip-pan side profile", "check the kick"), ("impact crash zoom", "elbow slash"),
                  ("face close-up", "stunned reaction"), ("whip-pan side profile", "teep kick"), ("slow-mo replay push-in", "spinning elbow knockout")],
    "mma": [("ringside low angle", "jab into double-leg"), ("whip-pan side profile", "high kick"), ("face close-up", "gasp for air"),
            ("whip-pan side profile", "sprawl"), ("overhead", "ground and pound"), ("slow-mo replay push-in", "flying knee")],
    "bjj": [("whip-pan side profile", "double-leg takedown"), ("ringside low angle", "guard pull"), ("overhead", "scissor sweep"),
            ("face close-up", "gasping reaction"), ("overhead", "armbar"), ("slow-mo replay push-in", "tap out")],
    "boxing": [("ringside low angle", "jab cross combo"), ("whip-pan side profile", "body hook"), ("impact crash zoom", "counter right hand"),
               ("face close-up", "stagger and glare"), ("ringside low angle", "slip and weave"), ("slow-mo replay push-in", "knockout haymaker")],
    "anime_power": [("sky-high wide", "shockwave punch trade"), ("ringside low angle", "aura power-up"), ("whip-pan side profile", "block and counter"),
                    ("ground-level debris cam", "crater impact slam"), ("impact crash zoom", "launch uppercut chase"),
                    ("slow-mo replay push-in", "energy blast finisher")],
}
# Framing for the Z-Image start plate, and camera-only motion text (the rig motion texts also describe the fight, which fought the beat).
KF_FRAME = {
    "ringside low angle": "Low-angle shot from the floor looking up at two fighters in profile.",
    "whip-pan side profile": "Side-on shot at chest height of two fighters in profile, the background streaked with motion blur.",
    "impact crash zoom": "Tight side-on medium shot of two fighters from the waist up.",
    "face close-up": "Tight close-up",
    "slow-mo replay push-in": "Wide side-on shot at chest height of two fighters.",
    "sky-high wide": "Wide aerial shot high in the sky of two warriors among the clouds.",
    "ground-level debris cam": "Shot from the ground among the rubble, tilted up at two warriors.",
    "overhead": "Overhead shot looking straight down from above",
    "bullet-time orbit": "Wide three-quarter shot at waist height of two fighters.",
}
KF_CAMERA = {
    "ringside low angle": "Low camera at ringside a foot above the floor, tilted up at the two fighters, tracking slowly sideways.",
    "whip-pan side profile": "Side-on camera at waist height framing both fighters in profile, whip-panning a little with the strike.",
    "impact crash zoom": "Side-on camera framing both fighters that crash-zooms in on the moment of impact.",
    "face close-up": "Tight close-up on the face, the camera pushing in slowly.",
    "slow-mo replay push-in": "Slow-motion replay, the camera pushing in steadily on the two fighters.",
    "sky-high wide": "Wide aerial camera high in the sky, slowly circling the two fighters.",
    "ground-level debris cam": "Camera on the ground among the rubble, tilted up at the two fighters, shuddering on the impact.",
    "overhead": "Overhead camera looking straight down at the two fighters, rotating slowly.",
    "bullet-time orbit": "Slow-motion bullet-time camera drifting a few degrees sideways around the two fighters.",
}
KF_PLAIN = "Plain clothing, gloves and waistbands with no lettering, no logos and no text anywhere."  # Z-Image runs at cfg 1: no negative
KF_KEEP = "Keep the same camera angle, framing, scene, lighting, faces, hair, outfits and gloves."
KF_HOLD = ("There are exactly two fighters. They stay clearly separate; their bodies never overlap and only the striking fist touches "
           "the target.")
KF_ENERGY = "Their auras glow and crackle, sparks and debris drift in the air. "
KF_NEG = ("fighters overlap, bodies pass through each other, arm passes through body, third fighter, extra person, "
          "fighters swap sides, full screen white, washed out")

def fighter_ref_prompt(desc: str, style_label: str = "") -> str:
    return (f"Full-body character reference of {desc}, standing in a ready fighting stance facing three-quarters toward the camera, "
            f"{style_label + ', ' if style_label else ''}plain neutral studio backdrop with soft even light so the face, hair, body, outfit "
            f"colors and details are crystal clear. Original fictional character, no logos and no text.")


def rig_for(rig: str, shot_index: int, seed: int, fight_style: str = "boxing") -> str:
    if rig in RIGS:
        return rig
    seq = FIGHT_STYLES[fight_style]["sequence"]
    if rig.startswith("auto (fight"):
        return seq[shot_index % len(seq)][0]
    names = list(RIGS)
    if rig.startswith("auto"):
        return names[(seed + shot_index) % len(names)]
    if rig.startswith("random"):
        return random.Random(seed * 1009 + shot_index).choice(names)
    raise KeyError(f"unknown rig {rig!r}; one of {names}")


def beat_for(rig: str, rig_name: str, beat: str, shot_index: int, seed: int, fight_style: str, kinds=None) -> str:
    beats = FIGHT_STYLES[fight_style]["beats"]
    if beat in beats:
        return beat
    if rig.startswith("auto (fight"):
        return FIGHT_STYLES[fight_style]["sequence"][shot_index % len(FIGHT_STYLES[fight_style]["sequence"])][1]
    kinds = kinds or RIGS[rig_name]["kinds"]
    pool = [n for n, b in beats.items() if b["kind"] in kinds] or list(beats)
    return random.Random(seed * 7919 + shot_index).choice(pool)


def _fighters(fs, hero, rival):
    hero = (hero or "").strip() or fs["hero"]
    r = (rival or "").strip()
    return hero, ("" if r.lower() in ("none", "solo", "off") else r or fs["rival"])


def _arena(arena, arena_custom):
    if arena == "custom" or (arena_custom or "").strip():
        return dict(scene=arena_custom.strip() or ARENAS["boxing ring"]["scene"], light="cinematic dramatic light", sound="a roaring crowd")
    return ARENAS[arena] if arena in ARENAS else dict(scene=arena.strip(), light="cinematic dramatic light", sound="a roaring crowd")


def _build(r, fight_style, style, hero, rival, arena, arena_custom, light, beat_name, intensity, shot_index, seed, aspect,
           seconds, extra, rig_name, group_label, keyframes=False):
    fs = FIGHT_STYLES[fight_style]
    st = STYLES[style]
    energy = fs.get("energy") and not st.get("calm")  # calm styles (anime_clean) keep auras for the beats that call for them
    hero, rival = _fighters(fs, hero, rival)
    a = _arena(arena, arena_custom)
    light_text = LIGHTS.get(light) or a["light"]
    b = fs["beats"][beat_name]
    speed, edge, hits = next((s, e, n) for t, s, e, n in SPEED if intensity < t)
    cap = lambda t: t[:1].upper() + t[1:]
    cast = f"The hero is {hero}." + (f" The rival is {rival}." if rival else " The hero fights alone, shadow-boxing the air.")
    plate = r["plate"].format(arena=a["scene"], action=b["plate"])
    plate_prompt = (f"{cap(plate)}. {cast} {st['plate_desc']}. "
                    f"{ENERGY_PLATE if energy else ''}Motion blur on the fastest limbs while both fighters stay tack-sharp, readable as two clearly separate silhouettes. "
                    f"{cap(light_text)}. {NO_BRAND}")
    motion_prompt = (f"{r['motion']} {b['motion']}, {speed}, {st['motion_desc']}, in {a['scene']}. "
                     f"{cap(edge + 'non-stop fight choreography')}, {light_text}. {ENERGY_MOTION if energy else ''}"
                     f"The action never pauses: every limb is in constant violent motion and the camera never stops moving. "
                     f"Sound: {fs['sound']}, {a['sound']}, {hits}. {HOLD[r['group']]} {fs['hold']} "
                     f"Both fighters keep their exact faces, hair, outfits and body shapes the whole time.")
    if extra.strip():
        plate_prompt += " " + extra.strip()
        motion_prompt += " " + extra.strip()
    plate_neg = build_negative_prompt(PLATE_NEG, st["plate_neg"], style)
    video_neg = build_negative_prompt(LTX_NEG, st["video_neg"], style)
    if r.get("slow"):
        video_neg = ", ".join(t for t in (x.strip() for x in video_neg.split(",")) if t != "slow motion")
    end_prompt = compose_prompt = ""
    kf = KF.get(fight_style, {}).get(beat_name) if keyframes else None
    if kf:
        start, move, end = kf
        staged = r["group"] in ("wide", "aerial", "orbit")
        compose_prompt = (f"{KF_FRAME.get(rig_name, 'Side-on shot at chest height of two fighters.')} "
                          f"{start.format(hero=hero, rival=rival or 'a sparring partner')} In {a['scene']}, {light_text}. "
                          f"{st['plate_desc']}. {ENERGY_PLATE if energy else ''}{KF_PLAIN}")
        plate_prompt = compose_prompt
        motion_prompt = (f"{KF_CAMERA.get(rig_name, r['motion'])} {move}, {st['motion_desc']}, in {a['scene']}, {light_text}. "
                         f"{KF_ENERGY if energy else ''}Sound: {fs['sound']}, {a['sound']}, {hits}. "
                         f"{fs.get('kf_hold', KF_HOLD) + ' ' if staged else ''}Both fighters keep their exact faces, hair, outfits and body shapes the whole time.")
        end_prompt = f"{end} {KF_KEEP} {KF_PLAIN}"
        if extra.strip():
            compose_prompt += " " + extra.strip()
            plate_prompt += " " + extra.strip()
            motion_prompt += " " + extra.strip()
            end_prompt += " " + extra.strip()
        video_neg = video_neg + ", " + KF_NEG
    vw, vh, pw, ph = ASPECTS[aspect]
    secs = seconds or r["seconds"]
    tweak, mult = st["fx_tweak"], fs.get("fx_mult", {})
    fx = {k: round(min(1.0, v * tweak.get(k, 1.0) * mult.get(k, 1.0) * (0.5 + 0.5 * intensity)), 3) for k, v in r["fx"].items()}
    return dict(rig=rig_name, group=group_label, action=beat_name, beat=beat_name, hero=hero, rival=rival, fight_style=fight_style,
                style=style, arena=arena, plate_prompt=plate_prompt, motion_prompt=motion_prompt, plate_negative=plate_neg,
                video_negative=video_neg, end_prompt=end_prompt, compose_prompt=compose_prompt, width=vw, height=vh, plate_width=pw, plate_height=ph, seconds=secs, fps=24,
                frames=int(secs * 24) + 1, seed=seed * 1000 + shot_index, fx=fx,
                label=f"{shot_index + 1:02d} {rig_name} / {beat_name}")


def compose(hero: str = "", arena: str = "", rig: str = "auto (fight sequence)", *, fight_style: str = "anime_power",
            style: str = "auto", rival: str = "", arena_custom: str = "", light: str = "arena default", beat: str = "auto",
            intensity: float = 0.85, shot_index: int = 0, seed: int = 0, aspect: str = "16:9 landscape", seconds: float = 0,
            extra: str = "", keyframes: bool = False) -> dict:
    """Compile one shot. Returns prompts, sizes, the resolved rig/beat and Clash FX defaults."""
    fs = FIGHT_STYLES[fight_style]
    style = fs["style"] if style in ("auto", "", None) else style
    arena = arena or fs["arena"]
    rig_name = rig_for(rig, shot_index, seed, fight_style)
    r = RIGS[rig_name]
    beat_name = beat_for(rig, rig_name, beat, shot_index, seed, fight_style)
    if keyframes and rig.startswith("auto (fight") and fight_style in KF_SEQUENCE:
        rig_name, beat_name = KF_SEQUENCE[fight_style][shot_index % len(KF_SEQUENCE[fight_style])]
        r = RIGS[rig_name]
    return _build(r, fight_style, style, hero, rival, arena, arena_custom, light, beat_name, intensity, shot_index, seed, aspect,
                  seconds, extra, rig_name, GROUPS[r["group"]], keyframes)


# ----------------------------------------------------------------------------------------------------- the two lines
# Clash ships as two tighter workflows on this one library: Clash Anime (over-the-top power fights) and Clash Real
# (real-life combat sports). Each line has its own fight styles, looks, arenas and defaults; keyframe mode is on by default.
LINES = {
    "anime": dict(
        label="Clash Anime", fight_styles=["anime_power"], fight_style="anime_power",  # every style here has keyframe beats
        styles=["anime_clean", "anime", "cyberpunk_anime", "comic_graphic_novel", "cartoon_3d", "synthwave_retro"], style="anime_clean",
        arenas=["floating sky islands", "volcanic wasteland", "desert canyon", "ruined stadium", "neon city", "bamboo forest", "rooftop at night"],
        arena="floating sky islands",
        blurb="Over-the-top anime power fights: shockwave punch trades, aura power-ups, crater slams, launch uppercuts and energy-blast finishers.",
    ),
    "real": dict(
        label="Clash Real", fight_styles=["boxing", "mma", "muay_thai", "taekwondo", "bjj"], fight_style="boxing",
        styles=["photoreal"], style="photoreal",
        arenas=["boxing ring", "underground cage", "dojo", "temple courtyard", "rooftop at night", "rain alley", "neon city"],
        arena="boxing ring",
        blurb="Real-life fights shot like a sports broadcast and a fight film: boxing, MMA, Muay Thai, taekwondo and Brazilian jiu-jitsu, one clean technique per shot.",
    ),
}


def line_style(line: str, fight_style: str, style: str) -> str:
    """Resolve 'auto' for a line: Clash Anime draws every fight style in its anime look, Clash Real is always photoreal."""
    ln = LINES[line]
    if style not in ("auto", "", None):
        return style
    return ln["style"] if line == "anime" or FIGHT_STYLES[fight_style]["style"] not in ln["styles"] else FIGHT_STYLES[fight_style]["style"]


GROUPS = {"mount": "fist / POV mounted", "wide": "fight-side", "close": "close-up", "orbit": "orbit", "aerial": "aerial"}

# ----------------------------------------------------------------------------------------------------- custom rig builder
CUSTOM_ANCHORS = {
    "glove (punch-cam)": dict(group="mount", plate="camera mounted on the hero's glove and forearm, the fist large in the lower foreground flying at the rival",
                              motion="Camera strapped to the hero's fist, lunging forward with every punch and whipping back with every recoil"),
    "chest harness (fighter body-cam)": dict(group="mount", plate="camera on a chest harness on the hero looking forward at the rival, the hero's arms swinging in the lower corners of the frame",
                                             motion="Body-cam strapped to the hero's chest, bobbing and twisting with each step and punch, the rival lunging and reeling ahead"),
    "corner post": dict(group="wide", plate="camera on the corner post at head height looking diagonally across at both fighters",
                        motion="Camera fixed on the corner post, panning and tilting to follow the fighters across the arena"),
    "floor (ground-level)": dict(group="wide", plate="camera on the floor a few centimeters up, boots and debris in the foreground, the fighters behind",
                                 motion="Camera on the floor, boots stomping past the lens and dust kicking up as the fighters clash behind"),
    "overhead boom": dict(group="aerial", plate="camera on an overhead boom looking down at the fighters from above",
                          motion="Overhead boom camera swinging in a steady arc above the fighters"),
    "drone (free flight)": dict(group="aerial", plate="FPV drone in flight swooping close to the two fighters",
                                motion="FPV drone weaving around the fighters, diving and banking through every strike"),
}
CUSTOM_PITCHES = {"level": "level horizon", "low tilt-up hero": "tilted up from below", "high tilt-down": "tilted down from above",
                  "dutch tilt": "canted 20-degree dutch angle", "reverse facing": "facing back toward the camera operator"}
CUSTOM_LENSES = {"14mm fisheye": "14mm fisheye", "24mm wide": "24mm wide", "35mm doc": "35mm documentary", "50mm anamorphic": "50mm anamorphic",
                 "85mm portrait": "85mm portrait", "135mm telephoto": "135mm telephoto"}
CUSTOM_STABILITY = {"rigid": ("rigidly fixed, shuddering with every impact", 0.8), "damped": ("damped, with a slight shock-absorbed wobble", 0.45),
                    "gimbal": ("on a 3-axis gimbal, smooth but fast", 0.2), "handheld": ("raw handheld, shaking and lurching", 0.95)}


def compose_custom_rig(*, fight_style: str = "anime_power", style: str = "auto", mount_anchor: str = "glove (punch-cam)",
                       camera_pitch: str = "level", lens_profile: str = "24mm wide", mount_stability: str = "rigid", beat: str = "auto",
                       hero: str = "", rival: str = "", arena: str = "", arena_custom: str = "", light: str = "arena default",
                       intensity: float = 0.85, shot_index: int = 0, seed: int = 0, aspect: str = "16:9 landscape",
                       seconds: float = 0, extra: str = "") -> dict:
    fs = FIGHT_STYLES[fight_style]
    style = fs["style"] if style in ("auto", "", None) else style
    an = CUSTOM_ANCHORS[mount_anchor]
    lens = CUSTOM_LENSES[lens_profile]
    stab, shake = CUSTOM_STABILITY[mount_stability]
    pitch = CUSTOM_PITCHES[camera_pitch]
    r = dict(group=an["group"], lens=lens, slow=False, seconds=3,
             plate=f"{lens} lens, {an['plate']}, {pitch}, {{arena}}, {{action}}",
             motion=f"{an['motion']}, {pitch}, {stab}.",
             fx=dict(shake=shake, flash=0.7, chroma=0.5, speed_lines=0.5, impact=0.4, ramp=0.0))
    kinds = ["hit", "flurry", "clash"]
    b = beat_for("custom", "", beat, shot_index, seed, fight_style, kinds=kinds)
    return _build(r, fight_style, style, hero, rival, arena or fs["arena"], arena_custom, light, b, intensity, shot_index, seed,
                  aspect, seconds, extra, f"custom: {mount_anchor}", GROUPS[an["group"]])


def shot_list(n: int, **kw) -> list[dict]:
    return [compose(shot_index=i, **kw) for i in range(n)]
