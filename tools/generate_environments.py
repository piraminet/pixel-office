#!/usr/bin/env python3
"""Generate original isometric environment packs for Pixel Startup.

Each pack = assets/environments/<id>/ with manifest.json (schema 1, validated
by `environments.js`) and background.png (640x800). Backgrounds are rendered
from the manifest geometry itself (collision grid, rooms, workstations,
furniture, interactions) with a shared isometric tile renderer -- art is
original programmatic work, not copied production artwork.

Usage:
  python3 tools/generate_environments.py [--check] [--only <id>]

The render is deterministic: fixed geometry + palettes -> identical output on
every run (safe to regenerate and diff).
"""

import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)

# ---------------------------------------------------------------- constants
CANVAS_W, CANVAS_H = 640, 800
TILE_W, TILE_H = 28, 14  # 2:1 isometric diamond
GRID_COLS, GRID_ROWS = 18, 22
SCHEMA_VERSION = 1
WALL_HEIGHT = 126
ORIGIN_X, ORIGIN_Y = 338, 320

FURNITURE_H = {
    'desk': 48, 'console': 42, 'counter': 52, 'bar': 52, 'crate': 38,
    'barrel': 32, 'planter': 32, 'lantern': 42, 'helmsman': 58,
    'perch': 42, 'rope': 26, 'rudder': 60, 'sign': 56, 'partition': 96,
}
TALL_KINDS = {'wall', 'shelf', 'elevator', 'medallion', 'arch'}
FURNITURE_KINDS = sorted(set(FURNITURE_H) | TALL_KINDS | {'plant', 'tree'})


def shade(rgb, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


def project(tx, ty):
    """Top vertex of tile (tx,ty)'s diamond in screen space."""
    return (ORIGIN_X + (tx - ty) * (TILE_W // 2),
            ORIGIN_Y + (tx + ty) * (TILE_H // 2))


def diamond(sx, sy, y=0):
    """Corners of tile diamond with top vertex at (sx, sy), offset by y."""
    return [(sx, sy + y),
            (sx + TILE_W // 2, sy + y + TILE_H // 2),
            (sx, sy + y + TILE_H),
            (sx - TILE_W // 2, sy + y + TILE_H // 2)]


# ---------------------------------------------------------------- palettes

PALETTE = {
    'continental': {
        'sky_top': (12, 14, 26), 'sky_bottom': (34, 34, 62),
        'floor': (233, 224, 202), 'floor_inset': (219, 209, 183),
        'floor_border': (201, 162, 39),
        'top': (34, 37, 48), 'left': (78, 82, 98), 'right': (30, 32, 42),
        'trim': (201, 162, 39), 'wall_dark': (40, 43, 56), 'accent': (42, 182, 165),
        'desk_top': (54, 58, 70), 'desk_side': (32, 34, 44),
        'chair': (42, 182, 165), 'chair_frame': (23, 112, 102),
        'leaf': (46, 128, 96), 'leaf2': (34, 98, 74), 'wood': (94, 66, 48),
        'glass': (168, 214, 220), 'lamp': (255, 224, 130),
        'medallion': (201, 162, 39), 'label': (238, 228, 200),
        'label_plate': (20, 22, 30),
    },
    'mechanic-shop': {
        'sky_top': (16, 16, 18), 'sky_bottom': (52, 30, 14),
        'floor': (118, 116, 122), 'floor_inset': (98, 96, 102),
        'floor_border': (232, 130, 30),
        'top': (64, 64, 68), 'left': (94, 94, 100), 'right': (42, 42, 46),
        'trim': (232, 130, 30), 'wall_dark': (40, 43, 56), 'accent': (240, 190, 40),
        'desk_top': (108, 110, 116), 'desk_side': (68, 70, 76),
        'chair': (200, 60, 40), 'chair_frame': (58, 58, 62),
        'leaf': (96, 110, 84), 'leaf2': (70, 82, 62), 'wood': (92, 62, 40),
        'glass': (200, 210, 220), 'lamp': (255, 214, 120),
        'medallion': (240, 190, 40), 'label': (230, 230, 232),
            'label_plate': (18, 18, 24),
    },
    'pirate-ship': {
        'sky_top': (14, 34, 58), 'sky_bottom': (64, 106, 130),
        'floor': (176, 136, 88), 'floor_inset': (148, 112, 72),
        'floor_border': (94, 62, 40),
        'top': (104, 74, 48), 'left': (140, 102, 66), 'right': (74, 52, 34),
        'trim': (222, 190, 120), 'wall_dark': (40, 43, 56), 'accent': (60, 96, 150),
        'desk_top': (120, 88, 56), 'desk_side': (84, 60, 40),
        'chair': (128, 92, 58), 'chair_frame': (70, 50, 34),
        'leaf': (40, 108, 74), 'leaf2': (30, 84, 58), 'wood': (110, 78, 50),
        'glass': (210, 230, 240), 'lamp': (255, 226, 150),
        'medallion': (222, 190, 120), 'label': (238, 230, 206),
            'label_plate': (18, 18, 24),
    },
    'lost-boys-treehouse': {
        'sky_top': (20, 42, 26), 'sky_bottom': (74, 118, 62),
        'floor': (196, 168, 118), 'floor_inset': (170, 142, 98),
        'floor_border': (88, 132, 70),
        'top': (112, 84, 52), 'left': (148, 112, 68), 'right': (84, 62, 40),
        'trim': (110, 150, 78), 'wall_dark': (40, 43, 56), 'accent': (86, 152, 210),
        'desk_top': (128, 96, 60), 'desk_side': (92, 68, 44),
        'chair': (104, 128, 64), 'chair_frame': (66, 82, 44),
        'leaf': (62, 130, 74), 'leaf2': (44, 100, 58), 'wood': (124, 90, 55),
        'glass': (200, 226, 226), 'lamp': (255, 232, 160),
        'medallion': (110, 150, 78), 'label': (240, 234, 210),
            'label_plate': (18, 18, 24),
    },
}

# ---------------------------------------------------------------- layouts


def _rect(c, x0, y0, x1, y1, v):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c[y][x] = v


def continental_layout():
    """Original art-deco concierge HQ on an 18x22 grid.

    Collision: 0 floor, 1 solid, 2 door, 3 chair. Far edge at the top
    (small tx+ty), main entrance at the bottom.
    """
    c = [[0] * GRID_COLS for _ in range(GRID_ROWS)]
    # border ring + back shelf row hugging the far wall
    _rect(c, 0, 0, 17, 0, 1)
    _rect(c, 0, 21, 17, 21, 1)
    for y in range(GRID_ROWS):
        c[y][0] = 1
        c[y][17] = 1
    _rect(c, 1, 1, 16, 1, 1)
    # main entrance doors in the bottom border
    c[21][4] = 2
    c[21][5] = 2
    # archives reading tables (far half) + chairs tucked in front
    _rect(c, 2, 3, 4, 3, 1)
    _rect(c, 13, 3, 15, 3, 1)
    for x in (2, 3, 4, 13, 14, 15):
        c[4][x] = 3
    # reception counter island + staff seats
    _rect(c, 4, 7, 9, 7, 1)
    for x in range(4, 10):
        c[8][x] = 3
    # vault partition (right half)
    for y in (14, 15, 16):
        c[y][9] = 1
    # meeting table + chairs
    _rect(c, 12, 13, 15, 13, 1)
    for x in range(12, 16):
        c[14][x] = 3
    # workstation pods (left-bottom quadrant)
    _rect(c, 2, 11, 6, 11, 1)
    for x in range(2, 7):
        c[12][x] = 3
    _rect(c, 2, 15, 6, 15, 1)
    for x in range(2, 7):
        c[16][x] = 3
    # lounge armchairs (waiting area)
    for x in (3, 6, 12, 14):
        c[10][x] = 3
    # bar counter + stools (foyer, right edge)
    for y in (17, 18, 19):
        c[y][16] = 1
        c[y][15] = 3
    # lobby info stand (solid prop, no interaction needed)
    c[19][12] = 1
    # corner planters
    for x, y in ((1, 6), (15, 6), (1, 19), (13, 20)):
        c[y][x] = 1

    rooms = [
        {'id': 'reception', 'name': 'Reception Hall', 'kind': 'reception',
         'rect': [2, 6, 16, 10], 'anchor': [6, 9],
         'color': '#2ab6a5', 'label': 'Concierge'},
        {'id': 'workstations', 'name': 'Workstations', 'kind': 'workstations',
         'rect': [1, 11, 8, 17], 'anchor': [4, 12],
         'color': '#c9a227', 'label': 'Desks'},
        {'id': 'archives', 'name': 'Archives', 'kind': 'archives',
         'rect': [1, 1, 16, 5], 'anchor': [8, 3],
         'color': '#8ea3b8', 'label': 'Archives'},
        {'id': 'foyer', 'name': 'Foyer Bar', 'kind': 'lounge',
         'rect': [14, 16, 17, 20], 'anchor': [15, 17],
         'color': '#b98ccf', 'label': 'Bar'},
        {'id': 'meeting', 'name': 'Meeting Room', 'kind': 'meeting',
         'rect': [10, 11, 17, 16], 'anchor': [13, 14],
         'color': '#d08a5a', 'label': 'Meeting'},
        {'id': 'lounge', 'name': 'Waiting Lounge', 'kind': 'lounge',
         'rect': [2, 9, 13, 10], 'anchor': [9, 10],
         'color': '#7fb8a6', 'label': 'Lounge'},
        {'id': 'entrance', 'name': 'Entrance', 'kind': 'entrance',
         'rect': [3, 18, 6, 20], 'anchor': [4, 20],
         'color': '#98a7b8', 'label': 'Entrance'},
    ]

    seat_faces = (
        [(x, 12, 'up') for x in range(2, 7)] + [(x, 16, 'up') for x in range(2, 7)]
        + [(x, 8, 'up') for x in range(4, 10)]
        + [(x, 14, 'up') for x in range(12, 16)]
        + [(x, 4, 'down') for x in (2, 3, 4, 13, 14, 15)]
        + [(15, y, 'left') for y in (17, 18, 19)]
        + [(x, 10, 'up') for x in (3, 6, 12, 14)]
    )
    workstations = [
        {'id': f'desk-{i + 1:02d}', 'name': f'Seat {i + 1:02d}',
         'tile': {'x': x, 'y': y}, 'face': face, 'action': 'working'}
        for i, (x, y, face) in enumerate(seat_faces)
    ]

    interactions = [
        {'id': 'spawn-doormat', 'name': 'Doormat', 'tile': {'x': 4, 'y': 20},
         'action': 'idle'},
        {'id': 'watercooler', 'name': 'Watercooler', 'tile': {'x': 1, 'y': 10},
         'action': 'drinking'},
        {'id': 'front-desk-phone', 'name': 'Front Desk Phone',
         'tile': {'x': 10, 'y': 7}, 'action': 'phone'},
        {'id': 'archive-book', 'name': 'Reading Table', 'tile': {'x': 8, 'y': 4},
         'action': 'reading'},
    ]

    furniture = (
        [{'kind': 'shelf', 'tiles': [{'x': x, 'y': 1} for x in range(1, 17)]},
         {'kind': 'counter', 'tiles': [{'x': x, 'y': 7} for x in range(4, 10)]},
         {'kind': 'desk', 'tiles': [{'x': x, 'y': 3} for x in (2, 3, 4)]},
         {'kind': 'desk', 'tiles': [{'x': x, 'y': 3} for x in (13, 14, 15)]},
         {'kind': 'desk', 'tiles': [{'x': x, 'y': 13} for x in range(12, 16)]},
         {'kind': 'desk', 'tiles': [{'x': x, 'y': 11} for x in range(2, 7)]},
         {'kind': 'desk', 'tiles': [{'x': x, 'y': 15} for x in range(2, 7)]},
         {'kind': 'bar', 'tiles': [{'x': 16, 'y': y} for y in (17, 18, 19)]},
         {'kind': 'perch', 'tiles': [{'x': 12, 'y': 19}]},
         {'kind': 'plant', 'tiles': [{'x': 1, 'y': 6}, {'x': 15, 'y': 6},
                                     {'x': 1, 'y': 19}, {'x': 13, 'y': 20}]},
         {'kind': 'partition', 'tiles': [{'x': 9, 'y': y} for y in (14, 15, 16)]},
         {'kind': 'elevator', 'tiles': [{'x': x, 'y': 0}
                                        for x in (3, 4, 5, 12, 13, 14)]}]
    )

    return c, rooms, workstations, interactions, furniture, {'x': 4, 'y': 20}


LAYOUTS = {'continental': continental_layout}


# ---------------------------------------------------------------- renderer


def _font(px, bold=False):
    path = None
    for c in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
              if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if os.path.exists(c):
            path = c
            break
    try:
        return (ImageFont.truetype(path, px) if path
                else ImageFont.load_default())
    except Exception:
        return ImageFont.load_default()


def _chair(d, sx, sy, pal, face):
    d.polygon(diamond(sx, sy + 3, -6), fill=pal['chair_frame'])
    d.polygon(diamond(sx, sy, -6), fill=pal['chair'])
    if face == 'up':
        d.polygon(diamond(sx, sy + 2, -15), fill=pal['chair_frame'])
    elif face == 'down':
        d.line([sx - 5, sy + 3, sx + 5, sy + 3], fill=pal['chair_frame'], width=2)
    else:
        bx = sx + 6 if face == 'right' else sx - 6
        d.line([bx, sy - 3, bx, sy + 7], fill=pal['chair_frame'], width=3)


def _prop_decals(d, sx, sy, pal, action):
    cx, cy = sx, sy + 8
    if action == 'drinking':
        d.rectangle([cx - 4, cy - 11, cx + 4, cy - 2], fill=pal['glass'],
                    outline=shade(pal['glass'], 0.6))
        d.ellipse([cx - 5, cy - 13, cx + 5, cy - 9], fill=pal['accent'])
    elif action == 'phone':
        d.rectangle([cx - 6, cy - 8, cx + 6, cy - 2], fill=shade(pal['desk_top'], 0.9))
        d.ellipse([cx - 4, cy - 6, cx + 4, cy - 2], fill=pal['lamp'])
        d.line([cx + 3, cy - 7, cx + 8, cy - 3], fill=pal['trim'], width=2)
    elif action == 'reading':
        d.polygon([(cx - 7, cy - 5), (cx, cy - 8), (cx + 7, cy - 5), (cx, cy - 2)],
                  fill=pal['label'])
        d.line([cx, cy - 8, cx, cy - 2], fill=pal['floor_inset'])
    elif action == 'waiting':
        d.rectangle([cx - 5, cy - 12, cx + 5, cy - 2], fill=pal['wood'],
                    outline=pal['trim'])
        d.ellipse([cx - 4, cy - 10, cx + 4, cy - 4], fill=pal['accent'])


def render_environment(colls, furniture, spawn, interactions, rooms, pal,
                       out_png):
    img = Image.new('RGB', (CANVAS_W, CANVAS_H), pal['sky_top'])
    d = ImageDraw.Draw(img)

    # backdrop: concentric ellipses from dark top toward horizon glow
    for i in range(200, 0, -1):
        f = i / 200.0
        col = tuple(int(pal['sky_top'][k] * f + pal['sky_bottom'][k] * (1 - f))
                    for k in range(3))
        d.ellipse([CANVAS_W // 2 - i * 5, CANVAS_H // 2 - i * 4,
                   CANVAS_W // 2 + i * 5, CANVAS_H // 2 + i * 4], fill=col)

    # furniture kind per solid tile
    solid = {}
    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            if colls[y][x] == 1:
                solid[(x, y)] = 'wall'
    for fr in furniture:
        for t in fr['tiles']:
            solid[(t['x'], t['y'])] = fr['kind']

    def room_for(tx, ty):
        for r in rooms:
            x0, y0, x1, y1 = r['rect']
            if x0 <= tx <= x1 and y0 <= ty <= y1:
                return r
        return None

    def tint(r):
        col = r.get('color', '#3b82f6').lstrip('#')
        rgb = tuple(int(col[i:i + 2], 16) for i in (0, 2, 4))
        return tuple(int(b * 0.55 + c * 0.45) for b, c in zip(pal['floor'], rgb))

    walkable = (0, 2, 3)

    # floor pass
    for ty in range(GRID_ROWS):
        for tx in range(GRID_COLS):
            v = colls[ty][tx]
            sx, sy = project(tx, ty)
            r = room_for(tx, ty)
            if v in walkable:
                base = tint(r) if r else pal['floor']
                d.polygon(diamond(sx, sy), fill=base)
                if r is None and (tx + ty) % 4 == 0:
                    d.polygon(diamond(sx, sy), fill=pal['floor_inset'])
                if v == 2:
                    d.polygon(diamond(sx, sy), fill=shade(pal['floor_inset'], 0.62))

    # painter pass: cubes + chairs together, far -> near
    items = []
    for (x, y), kind in solid.items():
        items.append(((x + y, x), 'solid', x, y, kind))
    for y in range(GRID_ROWS):
        for x in range(GRID_COLS):
            if colls[y][x] == 3:
                items.append(((x + y, x), 'chair', x, y, 'up'))
    items.sort(key=lambda it: it[0])

    # cutaway: the two camera-facing border edges (x = COLS-1, y = ROWS-1)
    # render as a low gold curb only, keeping the floor plan readable.
    for _, tag, x, y, kind in items:
        sx, sy = project(x, y)
        if tag == 'chair':
            _chair(d, sx, sy, pal, kind)
            continue
        if x == GRID_COLS - 1 or y == GRID_ROWS - 1:
            d.line([diamond(sx, sy)[3], diamond(sx, sy)[2]],
                   fill=shade(pal['floor_border'], 0.85), width=2)
            continue
        if kind == 'plant':
            d.polygon(diamond(sx, sy, -10), fill=pal['wood'])
            d.polygon(diamond(sx, sy, -11), outline=pal['trim'])
            d.ellipse([sx - 11, sy - 34, sx + 11, sy - 12], fill=pal['leaf'])
            d.ellipse([sx - 15, sy - 26, sx - 3, sy - 12], fill=pal['leaf2'])
            d.ellipse([sx + 3, sy - 28, sx + 15, sy - 14], fill=pal['leaf'])
            continue
        h = WALL_HEIGHT if kind in TALL_KINDS else FURNITURE_H.get(kind, WALL_HEIGHT)
        tall = h == WALL_HEIGHT
        # exposed faces: neighbor +x (down-right) and +y (down-left)
        exp_a = not (x + 1 < GRID_COLS and colls[y][x + 1] not in walkable)
        exp_b = not (y + 1 < GRID_ROWS and colls[y + 1][x] not in walkable)
        d.polygon(diamond(sx, sy, -h),
                  fill=pal['top'] if tall else pal['desk_top'])
        if exp_a:
            d.polygon([(sx, sy - h + TILE_H),
                       (sx + TILE_W // 2, sy + TILE_H // 2 - h),
                       (sx + TILE_W // 2, sy + TILE_H // 2),
                       (sx, sy + TILE_H)],
                      fill=pal['right'] if tall else pal['desk_side'])
        if exp_b:
            d.polygon([(sx - TILE_W // 2, sy + TILE_H // 2 - h),
                       (sx, sy - h + TILE_H),
                       (sx, sy + TILE_H),
                       (sx - TILE_W // 2, sy + TILE_H // 2)],
                      fill=pal['wall_dark' if tall else 'desk_side'])
        tops = diamond(sx, sy, -h)
        if tall:
            # slim ziggurat inset on the wall cap (Art Deco stepped parapet)
            d.polygon([(tops[0][0] + 5, tops[0][1] + 2),
                       (tops[1][0] - 5, tops[1][1] + 2),
                       (tops[2][0], tops[2][1] - 2), (tops[3][0], tops[3][1] + 2)],
                      outline=shade(pal['trim'], 0.45))
        else:
            # thin lacquer/gold edge on low furniture
            d.line([tops[3], tops[2]], fill=pal['trim'], width=1)
            d.line([tops[1], tops[2]], fill=pal['trim'], width=1)
        if kind == 'elevator':
            d.rectangle([sx - 8, sy - h + 20, sx + 8, sy - 2], fill=pal['glass'],
                        outline=pal['trim'], width=2)
            d.line([sx, sy - h + 20, sx, sy - 2], fill=pal['trim'], width=1)

    # continuous cornice along both back wall cap runs (single clean line)
    d.line([project(0, 0)[0] - TILE_W // 2,
            project(0, 0)[1] - WALL_HEIGHT + TILE_H // 2,
            project(0, GRID_ROWS - 1)[0] - TILE_W // 2,
            project(0, GRID_ROWS - 1)[1] - WALL_HEIGHT + TILE_H // 2],
           fill=pal['trim'], width=3)
    d.line([project(0, 0)[0] + TILE_W // 2,
            project(0, 0)[1] - WALL_HEIGHT + TILE_H // 2,
            project(GRID_COLS - 1, 0)[0] + TILE_W // 2,
            project(GRID_COLS - 1, 0)[1] - WALL_HEIGHT + TILE_H // 2],
           fill=pal['trim'], width=3)

    # props: interaction decals + spawn mat + room labels billboards
    for it in interactions:
        sx, sy = project(it['x'], it['y'])
        _prop_decals(d, sx, sy, pal, it['action'])
    sx, sy = project(spawn['x'], spawn['y'])
    d.polygon(diamond(sx, sy, 1), fill=pal['accent'], outline=pal['trim'])

    def _label(text, cx, cy, dy=-34):
        fnt = _font(12, True)
        w = d.textlength(text, font=fnt)
        pad = 4
        box = [cx - w / 2 - pad, cy + dy - 16, cx + w / 2 + pad,
               cy + dy - 4]
        d.polygon([((box[0] + box[2]) / 2, box[3]), (box[0] + 3, box[3] - 1),
                   (box[2] - 3, box[3] - 1)], fill=pal['label_plate'])
        d.rounded_rectangle(box, radius=6, fill=pal['label_plate'])
        d.rounded_rectangle(box, radius=6, outline=shade(pal['trim'], 0.6))
        d.text((cx - w / 2, cy + dy - 14), text, font=fnt, fill=pal['label'])

    for r in rooms:
        ax, ay = r['anchor']
        sx, sy = project(ax, ay)
        _label(r['label'], sx + 12, sy, dy=-34 if ay > 11 else 2)

    img.save(out_png)


# ---------------------------------------------------------------- manifest


def build_continental_manifest():
    """Returns ({manifest}, raw_rooms) — raw rooms carry rect/color for the
    background renderer; the manifest carries the schema-1 room shape."""
    c, rooms, workstations, interactions, furniture, spawn = continental_layout()
    # flatten to the schema-1 shape (validated by environments.js):
    # rooms carry [x,y] tile lists, workstations/interactions flat tiles,
    # spawn an [x,y] pair.
    tiles_of = {}
    for r in rooms:
        x0, y0, x1, y1 = r['rect']
        t = [[x, y] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
             if c[y][x] in (0, 2, 3)]
        tiles_of[r['id']] = t
    manifest_rooms = []
    for r in rooms:
        entry = {'id': r['id'], 'name': r['name'], 'anchor': r['anchor'],
                 'tiles': tiles_of[r['id']], 'label': r['label']}
        if r['kind'] in ('reception', 'workstations', 'archives'):
            entry['slot'] = r['kind']
        manifest_rooms.append(entry)
    ws = workstations[:16]
    manifest_workstations = [{'id': w['id'], 'x': w['tile']['x'],
                              'y': w['tile']['y'], 'face': w['face'],
                              'name': w['name'], 'action': w['action']}
                             for w in ws]
    manifest_interactions = [{'id': i['id'], 'x': i['tile']['x'],
                              'y': i['tile']['y'], 'action': i['action'],
                              'name': i['name']} for i in interactions]
    return {
        'id': 'continental',
        'name': 'Continental',
        'schema': SCHEMA_VERSION,
        'style': 'art-deco',
        'blurb': 'Art Deco concierge headquarters — brass, teal velvet '
                 'and black lacquer around a marble concierge hall.',
        'atmosphere': {'mood': 'Art Deco concierge headquarters'},
        'grid': {'cols': GRID_COLS, 'rows': GRID_ROWS, 'tile': 32},
        'presentation': {
            'projection': 'isometric', 'tileW': TILE_W, 'tileH': TILE_H,
            'origin': [ORIGIN_X, ORIGIN_Y], 'wallHeight': WALL_HEIGHT,
        },
        'collision': c,
        'rooms': manifest_rooms,
        'workstations': manifest_workstations,
        'interactions': manifest_interactions,
        'furniture': furniture,
        'placement': {'reception': 'reception', 'workstations': 'workstations',
                      'archives': 'archives'},
        'spawn': [spawn['x'], spawn['y']],
        'assets': {'background': '/assets/environments/continental/background.png'},
        'sprites': {'sheet': '/assets/characters/char_0.png'},
    }, rooms


def write_pack(manifest, raw_rooms, check_only=False):
    pack_dir = os.path.join(_root, 'assets', 'environments', manifest['id'])
    manifest_path = os.path.join(pack_dir, 'manifest.json')
    bg_path = os.path.join(pack_dir, 'background.png')
    if check_only:
        ok = os.path.exists(manifest_path) and os.path.exists(bg_path)
        return 'ok' if ok else 'missing'
    os.makedirs(pack_dir, exist_ok=True)
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')
    render_environment(manifest['collision'], manifest['furniture'],
                       {'x': manifest['spawn'][0], 'y': manifest['spawn'][1]},
                       manifest['interactions'], raw_rooms,
                       PALETTE[manifest['id']], bg_path)
    return 'written'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--only', default=None, help='pack id to build/check')
    args = ap.parse_args()
    only = args.only
    counts = []
    for pack_id in sorted(LAYOUTS):
        if only and pack_id != only:
            continue
        if pack_id == 'continental':
            m, raw_rooms = build_continental_manifest()
        else:
            print(f"skipping {pack_id}: layout builder not wired yet")
            continue
        status = write_pack(m, raw_rooms, check_only=args.check)
        print(f"{pack_id}: {status}")
        counts.append((pack_id, status))
    if not counts:
        print('nothing to process')
        return 1 if only else 0
    if args.check:
        missing = [pid for pid, s in counts if s != 'ok']
        if missing:
            print(f"check FAILED: {', '.join(missing)}")
            return 1
        print('check ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
