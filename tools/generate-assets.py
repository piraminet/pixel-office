#!/usr/bin/env python3
"""Generate shipped pixel assets: office background + custom Charon sprite.

- assets/oficina-placeholder.png  640x800 (= gameCanvas size; TILE_SIZE=32 => 20x25)
  Drawn from the default COLLISION_MAP in index.html (0=floor, 1=wall/furniture,
  2=door, 3=chair). A 1-component touching the map border is wall; interior
  1-islands are furniture styled by nearest room anchor (counter/desk/shelf).
- assets/characters/char_2.png    Charon custom (hooded, cyan glow) palette swap.

Deterministic (seeded). Re-run after editing the collision/room layout.
Keep assets/characters/char_2_original.png = intact pre-customization sheet.
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
TILE = 32
COLS, ROWS = 20, 25

# Default collision matrix (keep in sync with index.html default_COLLISION_MAP)
COLLISION = [
    [1]*20, [1]*20,
    [1,0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0,0,1],
    [1,0,0,0,0,0,1,1,0,0,0,0,0,1,0,0,0,0,0,1],
    [1,0,0,0,0,0,1,0,3,1,1,3,0,1,0,0,0,0,0,1],
    [1,0,0,0,0,0,1,0,3,1,1,3,0,1,0,0,0,0,0,1],
    [1,0,0,0,0,0,1,0,3,1,1,3,0,1,0,0,0,0,0,1],
    [1,0,0,0,0,0,1,0,0,0,0,0,0,1,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,1,1,1,1,1,1,1,0,0,0,3,1,1,3,0,1],
    [1,0,0,3,0,0,3,0,0,3,0,0,1,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,1,0,3,1,1,3,0,1],
    [1,0,0,0,1,1,1,1,0,0,1,0,1,0,0,0,0,0,0,1],
    [1,0,0,3,0,0,3,0,0,3,0,0,1,0,1,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,2,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,0,0,1,1,1,1,2,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,0,0,1,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,1],
    [1,0,0,0,1,1,1,1,0,0,0,0,1,0,1,1,1,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,3,0,0,0,1],
    [1,0,1,1,0,0,0,0,0,0,0,0,0,1,0,0,0,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]

ANCHORS = {"Reception": (10, 6), "Workstations": (10, 13), "Archives": (10, 21)}
FURNITURE_STYLE = {"Reception": "counter", "Workstations": "desk", "Archives": "shelf"}

# Palette (dashboard slate UI + cyan brand accent)
WALL = (35, 43, 58)
WALL_HI = (58, 70, 94)
WALL_MORTAR = (27, 34, 48)
FLOOR_A = (44, 52, 70)
FLOOR_B = (47, 56, 75)
SEAM = (32, 40, 57)
DESK_TOP = (74, 59, 47)
DESK_HI = (92, 74, 58)
DESK_SIDE = (36, 28, 21)
SHELF_WOOD = (58, 47, 36)
BOOK = [(120, 53, 47), (168, 104, 42), (64, 96, 122), (90, 118, 74)]
CHAIR_SEAT = (51, 65, 85)
CHAIR_BACK = (46, 58, 76)
CHAIR_FRAME = (148, 163, 184)
CYAN = (34, 211, 238)
CYAN_HI = (183, 249, 255)
DOOR_FRAME = (66, 78, 104)
LEAF = (63, 143, 95)
LEAF_HI = (84, 176, 106)
POT = (124, 74, 45)

import random
rng = random.Random(42)


def components():
    """Split 1-tiles into (wall_set, islands). Wall = component touching border."""
    seen = [[False]*COLS for _ in range(ROWS)]
    walls, islands = set(), []
    for y in range(ROWS):
        for x in range(COLS):
            if COLLISION[y][x] != 1 or seen[y][x]:
                continue
            comp, stack = [], [(x, y)]
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < COLS and 0 <= ny < ROWS and not seen[ny][nx] and COLLISION[ny][nx] == 1:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if any(px in (0, COLS-1) or py in (0, ROWS-1) for px, py in comp):
                walls.update(comp)
            else:
                islands.append(comp)
    return walls, islands


def nearest_anchor(comp):
    cx = sum(p[0] for p in comp) / len(comp)
    cy = sum(p[1] for p in comp) / len(comp)
    return min(ANCHORS, key=lambda n: (ANCHORS[n][0]-cx)**2 + (ANCHORS[n][1]-cy)**2)


def brick_wall(d, px, py):
    d.rectangle([px, py, px+TILE-1, py+TILE-1], fill=WALL)
    for band in range(2):
        by = py + band*16
        for bx in range(-(8 if band else 0) % 16 and -(8 if band else 0) or 0, TILE, 16):
            x0 = max(px, px+bx)
            x1 = min(px+TILE-1, px+bx+15)
            d.rectangle([x0, by, x1, by+14], outline=WALL_MORTAR)
            d.line([x0, by, x1, by], fill=WALL_HI)
        d.line([px, by+15, px+TILE-1, by+15], fill=WALL_MORTAR)


def floor_tile(d, px, py):
    checker = ((px//TILE) + (py//TILE)) % 2
    d.rectangle([px, py, px+TILE-1, py+TILE-1], fill=FLOOR_A if checker else FLOOR_B)
    for _ in range(6):
        c = (52, 62, 82) if rng.random() < 0.5 else (40, 47, 63)
        d.point((px + rng.randrange(TILE), py + rng.randrange(TILE)), fill=c)
    d.line([px, py, px+TILE-1, py], fill=SEAM)
    d.line([px, py, px, py+TILE-1], fill=SEAM)


def desk_tile(d, px, py, style):
    if style == "counter":
        top, hi, side = (61, 75, 99), (79, 95, 124), (43, 53, 71)
    elif style == "shelf":
        top, hi, side = SHELF_WOOD, (72, 58, 45), (32, 25, 19)
    else:
        top, hi, side = DESK_TOP, DESK_HI, DESK_SIDE
    d.rectangle([px+1, py+4, px+TILE-2, py+24], fill=top)
    d.line([px+1, py+4, px+TILE-2, py+4], fill=hi)
    d.rectangle([px+1, py+25, px+TILE-2, py+TILE-2], fill=(30, 37, 52))
    d.line([px+1, py+4, px+1, py+24], fill=side)
    if style == "counter":
        d.line([px+3, py+6, px+TILE-4, py+6], fill=CYAN)
    if style == "shelf":
        for i, book in enumerate(BOOK):
            bx = px + 3 + (i % 2)*9
            d.rectangle([bx, py+9, bx+6, py+19], fill=book)


def chair_tile(d, px, py):
    floor_tile(d, px, py)
    d.rectangle([px+10, py+2, px+21, py+10], fill=CHAIR_BACK)     # backrest
    d.line([px+10, py+2, px+21, py+2], fill=CHAIR_FRAME)
    d.rectangle([px+8, py+10, px+23, py+18], fill=CHAIR_SEAT)     # seat
    d.line([px+11, py+19, px+11, py+26], fill=CHAIR_FRAME)
    d.line([px+20, py+19, px+20, py+26], fill=CHAIR_FRAME)
    d.line([px+9, py+27, px+22, py+27], fill=CHAIR_FRAME)


def door_tile(d, px, py):
    d.rectangle([px, py, px+TILE-1, py+TILE-1], fill=FLOOR_A)
    d.line([px+2, py+1, px+2, py+TILE-2], fill=DOOR_FRAME)
    d.line([px+TILE-3, py+1, px+TILE-3, py+TILE-2], fill=DOOR_FRAME)
    d.rectangle([px+6, py+10, px+TILE-7, py+22], outline=(96, 112, 140))


def plant(d, px, py):
    d.ellipse([px+6, py+4, px+25, py+23], fill=LEAF)
    d.ellipse([px+10, py+7, px+21, py+17], fill=LEAF_HI)
    d.rectangle([px+10, py+22, px+21, py+29], fill=POT)


def tint(img, anchor, color, alpha):
    ax, ay = anchor
    x0, y0 = (ax-2)*TILE, (ay-3)*TILE
    w, h = 5*TILE, 6*TILE
    overlay = Image.new("RGBA", (w, h), color + (alpha,))
    img.alpha_composite(overlay, (x0, y0))


walls, islands = components()
tile_furniture = {}
for comp in islands:
    style = FURNITURE_STYLE[nearest_anchor(comp)]
    for (x, y) in comp:
        tile_furniture[(x, y)] = style

base = Image.new("RGBA", (COLS*TILE, ROWS*TILE))
d = ImageDraw.Draw(base)

for y in range(ROWS):
    for x in range(COLS):
        px, py = x*TILE, y*TILE
        v = COLLISION[y][x]
        if (x, y) in walls:
            brick_wall(d, px, py)
        elif v == 0:
            floor_tile(d, px, py)
        elif v == 2:
            door_tile(d, px, py)
        elif v == 3:
            chair_tile(d, px, py)
        else:  # island furniture
            desk_tile(d, px, py, tile_furniture[(x, y)])

tint(base, ANCHORS["Reception"], (34, 150, 200), 34)
tint(base, ANCHORS["Workstations"], (120, 160, 110), 20)
tint(base, ANCHORS["Archives"], (170, 110, 60), 20)
d = ImageDraw.Draw(base)  # redraw after compositing tints

for tx, ty in [(1, 9), (18, 9), (1, 19), (17, 3), (18, 23)]:
    if COLLISION[ty][tx] == 0:
        plant(d, tx*TILE, ty*TILE)

for tx, ty in [(0, 6), (19, 6), (0, 13), (19, 13), (0, 21), (19, 21)]:
    px, py = tx*TILE, ty*TILE
    d.rectangle([px+13, py+10, px+18, py+15], fill=CYAN)
    d.rectangle([px+14, py+11, px+17, py+14], fill=CYAN_HI)

out = os.path.join(ASSETS, "oficina-placeholder.png")
base.convert("RGB").save(out, optimize=True)
print("background ->", out, base.size)


# ---------- Charon custom: hooded, cyan accents (palette swap) ----------
CHARON_MAP = {
    (246, 125, 32): (26, 44, 60),   # torso orange -> charcoal cloak
    (225, 114, 29): CYAN,           # highlight -> cyan glow trim
    (200, 100, 30): (40, 70, 92),
    (86, 17, 14): (12, 22, 32),     # deep reds -> cold slate
    (139, 26, 22): (36, 78, 102),
    (17, 21, 40): (20, 34, 52),
    (24, 22, 22): (26, 28, 38),
    (34, 30, 30): (32, 35, 47),
    (27, 26, 25): (29, 31, 41),
    (40, 36, 35): (36, 39, 51),
    (35, 30, 29): (31, 34, 45),
    (43, 40, 39): (37, 40, 53),
    (37, 33, 32): (33, 36, 48),
    (18, 3, 8): (44, 22, 58),       # hood lining hint
    (95, 65, 50): (86, 64, 68),     # muted skin
    (73, 50, 39): (66, 49, 55),
}

src_path = os.path.join(ASSETS, "characters", "char_2_original.png")
src = Image.open(src_path).convert("RGBA")
dst = Image.new("RGBA", src.size)
out_px = []
for (r, g, b, a) in src.getdata():
    if a == 0:
        out_px.append((r, g, b, a))
        continue
    if (r, g, b) in CHARON_MAP:
        out_px.append(CHARON_MAP[(r, g, b)] + (a,))
    elif r >= 140 and g >= 60 and r - b >= 50:  # stray warm stragglers -> cool
        c = (150, 226, 238) if g >= 110 else (52, 84, 108)
        out_px.append(c + (a,))
    else:
        out_px.append((r, g, b, a))
dst.putdata(out_px)
out2 = os.path.join(ASSETS, "characters", "char_2.png")
dst.save(out2, optimize=True)
print("charon ->", out2)
