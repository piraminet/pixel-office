#!/usr/bin/env python3
"""G22 — isometric environment pack generator.

Generates environment packs under assets/environments/<id>/:
  manifest.json   (schema 1, validated by environments.js on the server)
  background.png  (640x800 scene render; pack-unique, original art)

Usage:
  python3 tools/generate_environments.py                # build all packs
  python3 tools/generate_environments.py --only continental
  python3 tools/generate_environments.py --check        # validate on-disk packs

Batch 1 ships the pack library + the Continental pack, whose collision matrix
is an exact replica of the canonical default office (index.html default_COLLISION_MAP
/ live map.json). Rooms, workstations, interactions, spawn and placement are
derived from that geometry. Later batches add the other three packs and the
original background art.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV_ROOT = REPO / "assets" / "environments"

# Tile values (shared with index.html COLLISION_MAP + environments.js GRID_VALUES):
# 0=floor 1=wall/solid 2=door 3=chair
WALKABLE = {0, 2, 3}

# ---------------------------------------------------------------------------
# Canonical default-office collision (verbatim from index.html default_COLLISION_MAP).
# The Continental pack intentionally preserves it: the existing office layout,
# painted dashboard edits and door/carpet behavior keep working unchanged.
# ---------------------------------------------------------------------------
DEFAULT_OFFICE_COLLISION = [
    [1] * 20,
    [1] * 20,
    [1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 3, 1, 1, 3, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 3, 1, 1, 3, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 3, 1, 1, 3, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 3, 1, 1, 3, 0, 1],
    [1, 0, 0, 3, 0, 0, 3, 0, 0, 3, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 3, 1, 1, 3, 0, 1],
    [1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 3, 0, 0, 3, 0, 0, 3, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 2, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 3, 0, 0, 0, 1],
    [1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1],
    [1] * 20,
]


def box_tiles(collision, box):
    x0, x1, y0, y1 = box
    tiles = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if y < len(collision) and x < len(collision[y]) and collision[y][x] in WALKABLE:
                tiles.append([x, y])
    return tiles


def make_rooms(collision, specs):
    """specs: list of (id, name, box, slot, anchor)."""
    rooms = []
    for room_id, name, box, slot, anchor in specs:
        room = {"id": room_id, "name": name, "tiles": box_tiles(collision, box)}
        if slot is not None:
            room["slot"] = slot
        if anchor is not None:
            room["anchor"] = list(anchor)
        rooms.append(room)
    return rooms


def build_continental():
    collision = [row[:] for row in DEFAULT_OFFICE_COLLISION]
    rooms = make_rooms(collision, [
        # id, name, (x0, x1, y0, y1), slot, anchor
        ("reception", "Reception", (8, 12, 3, 7), "reception", (10, 7)),
        ("foyer", "Foyer Bar", (1, 5, 2, 7), None, (3, 4)),
        ("deco-lounge", "Deco Lounge", (14, 18, 2, 7), None, (16, 4)),
        ("workstations", "Workstations", (1, 11, 10, 16), "workstations", (10, 14)),
        ("annex", "Reading Annex", (13, 18, 10, 17), None, (16, 13)),
        ("archives", "Archives", (1, 11, 19, 23), "archives", (10, 21)),
        ("stacks", "Archive Stacks", (13, 18, 19, 23), None, (15, 20)),
    ])
    workstations = [
        # Reception concierge chairs (face the counter islands x9-x10)
        {"id": "reception-a", "x": 8, "y": 4, "face": "right"},
        {"id": "reception-b", "x": 11, "y": 4, "face": "left"},
        {"id": "reception-c", "x": 8, "y": 5, "face": "right"},
        {"id": "reception-d", "x": 11, "y": 5, "face": "left"},
        {"id": "reception-e", "x": 8, "y": 6, "face": "right"},
        {"id": "reception-f", "x": 11, "y": 6, "face": "left"},
        # Main desk island (row 12 desks, chairs row 13)
        {"id": "desk-a", "x": 3, "y": 13, "face": "up"},
        {"id": "desk-b", "x": 6, "y": 13, "face": "up"},
        {"id": "desk-c", "x": 9, "y": 13, "face": "up"},
        # South desk island (row 15 desks, chairs row 16)
        {"id": "desk-d", "x": 3, "y": 16, "face": "up"},
        {"id": "desk-e", "x": 6, "y": 16, "face": "up"},
        {"id": "desk-f", "x": 9, "y": 16, "face": "up"},
        # Annex desk pods (rows 12/14 desk islands x15-x16)
        {"id": "annex-a", "x": 14, "y": 12, "face": "right"},
        {"id": "annex-b", "x": 17, "y": 12, "face": "left"},
        {"id": "annex-c", "x": 14, "y": 14, "face": "right"},
        {"id": "annex-d", "x": 17, "y": 14, "face": "left"},
    ]
    interactions = [
        {"id": "bar-sip", "x": 15, "y": 3, "action": "drinking", "face": "down"},
        {"id": "phone-annex", "x": 15, "y": 13, "action": "phone", "face": "right"},
        {"id": "read-stacks", "x": 5, "y": 20, "action": "reading", "face": "up"},
    ]
    return {
        "schema": 1,
        "id": "continental",
        "name": "Continental HQ",
        "style": "art-deco",
        "blurb": "Art Deco concierge headquarters — brass, marble and neon.",
        "default": True,
        "grid": {"cols": 20, "rows": 25, "tile": 32},
        "assets": {
            "background": "/assets/environments/continental/background.png"
        },
        "collision": collision,
        "rooms": rooms,
        "workstations": workstations,
        "interactions": interactions,
        "spawn": [10, 10],
        "placement": {
            "reception": "reception",
            "workstations": "workstations",
            "archives": "archives"
        }
    }


# --- pack registry: id -> (builder, background producer) -------------------
# Background producers receive (pack_dir) and write background.png in place.
# Batch 2+ replace the placeholder copy with original painted renders.
PACKS = {
    "continental": (build_continental, None),
}


def check_dirs(collision):
    assert len(collision) == 25 and all(len(r) == 20 for r in collision), "collision grid must be 20x25"


def write_pack(env_id, builder, bg_writer, force=False):
    pack_dir = ENV_ROOT / env_id
    manifest = builder()
    check_dirs(manifest["collision"])
    if manifest["id"] != env_id:
        raise SystemExit(f"manifest id {manifest['id']!r} != pack dir {env_id!r}")
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = pack_dir / "manifest.json"
    if manifest_path.exists() and not force:
        existing = json.loads(manifest_path.read_text())
        if existing != manifest:
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(f"  {env_id}: manifest updated")
        else:
            print(f"  {env_id}: manifest unchanged")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"  {env_id}: manifest written")
    bg_path = pack_dir / "background.png"
    if bg_writer is not None:
        bg_writer(pack_dir)
        print(f"  {env_id}: background rendered -> {bg_path.name}")
    elif not bg_path.exists() and env_id == "continental":
        # Batch 1: ship the current office view until the Art Deco render lands (G22 B2).
        src = REPO / "assets" / "oficina-placeholder.png"
        if src.exists():
            import shutil
            shutil.copyfile(src, bg_path)
            print(f"  {env_id}: background staged (placeholder copy) -> {bg_path.name}")
        else:
            print(f"  {env_id}: WARNING no source background found; pack ships without background.png", file=sys.stderr)


def check_packs():
    """Light structural validation of on-disk packs (authoritative checks live in
    environments.js and run in the node test suite, G22 B7)."""
    ok = True
    for pack_dir in sorted(p for p in ENV_ROOT.iterdir() if p.is_dir()) if ENV_ROOT.exists() else []:
        mpath = pack_dir / "manifest.json"
        env_id = pack_dir.name
        if not mpath.exists():
            print(f"CHECK {env_id}: FAIL (no manifest.json)")
            ok = False
            continue
        m = json.loads(mpath.read_text())
        problems = []
        if m.get("schema") != 1:
            problems.append("schema != 1")
        if m.get("id") != env_id:
            problems.append("id/dir mismatch")
        col = m.get("collision") or []
        if len(col) != m.get("grid", {}).get("rows"):
            problems.append("collision rows != grid.rows")
        bg = pack_dir / "background.png"
        if not bg.exists():
            problems.append("background.png missing")
        for room in m.get("rooms", []):
            for x, y in room.get("tiles", []):
                if (m["collision"][y][x] if y < len(col) and x < len(col[y]) else 1) == 1:
                    problems.append(f"room {room['id']} tile {x},{y} not walkable")
                    break
        if problems:
            ok = False
            print(f"CHECK {env_id}: FAIL — " + "; ".join(problems))
        else:
            print(f"CHECK {env_id}: OK ({len(m.get('rooms', []))} rooms, "
                  f"{len(m.get('workstations', []))} workstations)")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None, metavar="ENV_ID")
    ap.add_argument("--force", action="store_true", help="rewrite manifest even if unchanged")
    ap.add_argument("--check", action="store_true", help="validate on-disk packs and exit")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if check_packs() else 1)

    wanted = args.only if args.only else list(PACKS)
    unknown = [w for w in wanted if w not in PACKS]
    if unknown:
        raise SystemExit(f"unknown environment id(s): {', '.join(unknown)}")
    for env_id in wanted:
        builder, bg_writer = PACKS[env_id]
        write_pack(env_id, builder, bg_writer, force=args.force)
    print("done.")


if __name__ == "__main__":
    main()
