"""Blur save file (blursave) <-> readable JSON.

usage:
  python blursave.py unpack  <blursave> <out.json>
  python blursave.py pack    <in.json>  <out_blursave>
  python blursave.py check   <blursave>            (unpack + pack in memory, compares the data)

File format: u32 magic 0xABCDE337, u32 uncompressed size, u32 compressed size, then one zlib stream that ends with a
sync flush (no final block). The data is a binary profile with no field names; many fields are 32-bit database IDs
(vehicles, events, routes, drivers ...), which blursave_names.json (from gamedata\\xt\\*.bin) resolves to names.

JSON (what each field means, how well it is checked, and what is still unknown: see BLURSAVE_FORMAT.md next to this file):
  "profile":   fan_level, fans, last_vehicle (the car driven last), lights (campaign progress, e.g. 350 of 450) and
               stat_4d1751a5 (unknown, read only).
  "campaign":  the 9 tiers (bosses) with their 7 events each, the boss demand counters and the tier state; each event has
               "flags" = [status, place, difficulty, tunnel] and a read-only "decoded" reading incl. its lights.
               "lights_from_events" is their sum (the "lights" counter in "profile" can lag one save behind).
               The info_* fields are not understood and are not written back.
  "fan_ranks": read-only table: fans needed per level and the cars each level unlocks (singleplayer.bin).
  "vehicles":  one record per vehicle with its class (A-D) and "state": only the garage's "seen" flag (2 = seen, 0 or 1 =
               not seen). It does NOT lock or unlock a car.
  "blocks":    every run of non-zero bytes {"offset", "hex"}; all bytes in between are 0. Edit the hex (same length
               per block; to move data change "offset") - the file keeps its size.
  "known_ids": every 32-bit value that is a known database ID {"offset", "id", "type", "name"}.
               Change "name" (or "id") to put another vehicle/event/... there; the bytes are patched when packing.
               A name has to be unique within its type; otherwise use "id".
Many bytes are still not understood. Back up the save first and close the game before replacing it."""
import json
import os
import re
import struct
import sys
import zlib

MAGIC = 0xABCDE337
HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = os.path.join(HERE, "blursave_names.json")
MIN_ID = 0x10000           # smaller values are ordinary numbers, not database IDs
GAP = 16                   # zero bytes that separate two blocks


def read_save(path):
    raw = open(path, "rb").read()
    magic, usz, csz = struct.unpack_from("<III", raw, 0)
    if magic != MAGIC:
        raise SystemExit("not a Blur save (magic %#x)" % magic)
    data = zlib.decompressobj().decompress(raw[12:])
    if len(data) != usz or csz != len(raw) - 12:
        raise SystemExit("unexpected sizes: header says %d/%d, found %d/%d" % (usz, csz, len(data), len(raw) - 12))
    return data


def write_save(path, data):
    c = zlib.compressobj(9)
    stream = c.compress(data) + c.flush(zlib.Z_SYNC_FLUSH)         # the game's files end like this
    with open(path, "wb") as f:
        f.write(struct.pack("<III", MAGIC, len(data), len(stream)) + stream)


def load_names():
    """{id: {type, name, file}} of the game database; empty without blursave_names.json (the shared editor does not ship
    it: the editor needs only the vehicle, rank and campaign tables, `known_ids` is for the unpack/pack command line)"""
    if not os.path.exists(NAMES):
        return {}, {}
    t = json.load(open(NAMES))
    by_id = {int(k, 16): v for k, v in t.items()}
    by_name = {}
    for i, v in by_id.items():
        if v["name"]:
            by_name.setdefault((v["type"], v["name"]), []).append(i)
    return by_id, by_name


def blocks_of(data):
    out, s, last = [], None, None
    for i, b in enumerate(data):
        if b:
            if s is None:
                s = i
            elif i - last > GAP:
                out.append((s, last + 1))
                s = i
            last = i
    if s is not None:
        out.append((s, last + 1))
    return [{"offset": a, "hex": data[a:b].hex(" ")} for a, b in out]


VEHICLES = os.path.join(HERE, "blursave_vehicles.json")
RANKS = os.path.join(HERE, "blursave_ranks.json")
FAN_SIGNATURE = re.compile(rb"\xff\xff\xff\xff\x00{9}(.{4})(.{4})\x00{4}", re.S)   # then: fan level, fans (u32 each)
STATE_HINT = ("'seen' flag, NOT the unlock: 2 = seen (no symbol); 0 and 1 = not seen yet (symbol shown once the car "
              "is unlocked). Tested in the game with an unlocked car: 0 and 1 both show the symbol, the car stays usable. "
              "Where the unlock itself is stored is not known yet.")


def load_vehicles():
    return {int(k, 16): v for k, v in json.load(open(VEHICLES)).items()}


FAN_ANCHOR_TIER_ID = 1058515315        # the first record of the tier table; the fan level is 60 bytes before it


def find_fans(data):
    """offset of the fan level (u32); the fan count follows. Anchored at the tier table and checked against the rank
    table (fans must give the stored level); falls back to a byte pattern. None if neither is unique."""
    i = data.find(struct.pack("<I", FAN_ANCHOR_TIER_ID))
    if i >= 60 and data.find(struct.pack("<I", FAN_ANCHOR_TIER_ID), i + 1) < 0 and os.path.exists(RANKS):
        lvl, fans = struct.unpack_from("<II", data, i - 60)
        ranks = json.load(open(RANKS))
        if lvl == max(r["rank"] for r in ranks if r["fans"] <= fans):
            return i - 60
    hits = [m.start(1) for m in FAN_SIGNATURE.finditer(data)]
    return hits[0] if len(hits) == 1 else None


def find_vehicle_table(data, veh):
    """(offset, count) of the longest run of 8-byte records: vehicle ID (u32), state (u8), 3 constant bytes"""
    best, i, n = None, 0, len(data) - 8
    while i < n:
        if struct.unpack_from("<I", data, i)[0] in veh:
            k = 0
            while i + 8 * k + 4 <= len(data) and struct.unpack_from("<I", data, i + 8 * k)[0] in veh:
                k += 1
            if k >= 20 and (best is None or k > best[1]):
                best = (i, k)
            i += 8 * k if k else 1
        else:
            i += 1
    if best:                       # the real table is sorted by ID; the car ID + flags at the end of the event record
        i, k = best                # before it (e.g. T7E2) looks like a record and would be a bogus first one
        while k > 1 and struct.unpack_from("<I", data, i)[0] > struct.unpack_from("<I", data, i + 8)[0]:
            i, k = i + 8, k - 1
        best = (i, k)
    return best


STATS_SIGNATURE = re.compile(rb"(.{4})\x1c\x00\x00\x00(.{4})\x1d\x00\x00\x00(.{4})\x1e\x00\x00\x00(.{4})\x1f\x00\x00\x00", re.S)
LIGHTS_TOTAL = re.compile(rb"\xa5\x51\x17\x4d(.{4})", re.S)     # ID 4d1751a5 + u32 = 450 in the three saves checked


def find_lights(data):
    """(offset of the lights counter as float32, offset of the unknown stat 4d1751a5) - both unique, else None"""
    a = [m.start(3) for m in STATS_SIGNATURE.finditer(data)]
    b = [m.start(1) for m in LIGHTS_TOTAL.finditer(data)]
    return (a[0], b[0]) if len(a) == 1 and len(b) == 1 else None


MODS_SEEN = {24: "Quadshock", 25: "Overbolt", 26: "Titanium Shield", 27: "Fan Nitro", 28: "Nitro Rift",
             29: "Armor Plating", 30: "Scatter Shot", 31: "Super Shunt"}        # all eight mods the game offers in single player


def find_mod(data):
    """offset of the selected-mod byte: 5 bytes behind the last entry (index 0x75) of the 8-byte stat table [u16 index][pad][float].
    The two bytes behind the table are ff 3f in a played save and d8 05 in an early one (one rival beaten); then 00 00 follow, then one
    byte that is 01 in the saves written by the game here and 00 in the two downloaded ones (checked in 37 saves). The mod byte is ff in the
    early save: no mod chosen yet."""
    for s in range(1000, len(data) - 8 * 0x77 - 8):
        if all(struct.unpack_from("<H", data, s + 8 * i)[0] == i for i in range(6)) \
                and struct.unpack_from("<H", data, s + 8 * 0x75)[0] == 0x75 \
                and data[s + 8 * 0x76 + 2:s + 8 * 0x76 + 4] == b"\x00\x00":
            return s + 8 * 0x76 + 5
    return None


CAMPAIGN = os.path.join(HERE, "blursave_campaign.json")
CAMPAIGN_HINT = ("tier 'state': 2 = seen, 1 = new (shows the symbol); events 'flags' = [status, place, difficulty, "
                 "tunnel] (status 0 locked, 1 available/new, 2 played; place 3 = 1st, 2 = 2nd, 1 = 3rd; difficulty 3 = hardest, 2 = medium, "
                 "1 = probably easy; tunnel 1 = fan tunnel driven); 'decoded' shows the reading incl. the event's lights; "
                 "'lights_from_events' is their sum - the 'lights' counter in 'profile' can lag one event behind; boss 'counters' = progress of the 4 boss demands (see 'demands'); "
                 "a counter can hold a float32 bit pattern (tier 6 drift = 1500.0 shows as 1153138688); "
                 "'status' [b0,b1,b2,b3]: b0 = 1 once all four demands are met (boss event available), b1 = 1 once the "
                 "boss is beaten (observed at Tier 8), b2 = 174 always.")


def _find_id(data, uid, check=None):
    """offset of the 4-byte id; it has to occur once (after the optional check has sorted out look-alikes)"""
    key, hits, i = struct.pack("<I", uid), [], -1
    while True:
        i = data.find(key, i + 1)
        if i < 0:
            break
        if check is None or check(i):
            hits.append(i)
    return hits[0] if len(hits) == 1 else None


PLACE_LIGHTS = {3: 5, 2: 4, 1: 3, 0: 0}


def event_summary(e, flags, fans):
    """Read-only reading of an event record. flags = [status, place, difficulty, tunnel]:
    status 0 locked / 1 available / 2 played; place 3 = 1st, 2 = 2nd, 1 = 3rd; difficulty 3 = hardest and 2 = medium
    (both tested in the game), 1 = probably easy (not tested); tunnel 1 = fan tunnel driven. The fan target is not a flag: fans >= the database's target.
    Lights = place (5/4/3) + 1 for the fan target + 1 for the tunnel; a won boss event = 8. This sum matched the
    lights of four saves exactly (159, 350, 450, 450); the lights counter in the file can lag one event behind."""
    st, place, diff, tun = flags
    if st != 2:
        return {"status": ["locked", "available"][st] if st in (0, 1) else st}
    out = {"status": "played", "place": {3: 1, 2: 2, 1: 3}.get(place), "difficulty": diff, "fans": fans}
    if e["type"] == "BossEvent":
        out["lights"] = 8 if place == 3 else None
    else:
        reached = fans >= e["fan_par"]
        out.update({"fan_target": e["fan_par"], "fan_target_reached": reached, "tunnel": bool(tun),
                    "lights": PLACE_LIGHTS.get(place, 0) + int(reached) + int(tun)})
    return out


FLOAT_DEMANDS = {"Tier_Drift"}      # boss demands whose counter is a float32 (drift points: 0.0 ... 1500.0), the others are u32


def _counters(data, bp, demands):
    raw = struct.unpack_from("<4I", data, bp + 4)
    return [struct.unpack("<f", struct.pack("<I", c))[0] if d in FLOAT_DEMANDS else c for c, d in zip(raw, demands)]


def _boss_at(data, boss_id):
    """offset of a boss record: the id that is followed by a status [.,.,174,.]; a record the game has not initialised yet (a new profile)
    has no 174, then the id alone is used (it occurs once)"""
    return _find_id(data, boss_id, lambda p: p + 24 <= len(data) and data[p + 22] == 174) or _find_id(data, boss_id)


def extend_campaign(data):
    """The save game of a new profile already holds the records of all 9 groups, their bosses and 63 events (the game keeps room for them),
    but not initialised: the status of the bosses lacks the constant 174 and the group state has stray bytes next to it ("01 7f 00 00").
    The game fills them in when the campaign is played. This does the same: the group state keeps its low byte, the boss status gets the
    174. Returns (data, number of records changed); the data are unchanged (0) if the save has no such records or they are in order."""
    if not os.path.exists(CAMPAIGN):
        return data, 0
    data, n = bytearray(data), 0
    camp = json.load(open(CAMPAIGN))
    found = []
    for t in camp:
        tp = _find_id(bytes(data), t["id"])
        bp = _boss_at(bytes(data), t["boss_id"])
        if tp is None or bp is None or bp + 24 > len(data) or any(_find_id(bytes(data), e["id"]) is None for e in t["events"]):
            return bytes(data), 0
        found.append((tp, bp))
    for tp, bp in found:
        if struct.unpack_from("<I", data, tp + 4)[0] > 2:               # stray bytes behind the state byte
            data[tp + 5:tp + 8] = b"\0\0\0"
            n += 1
        if data[bp + 22] != 174:
            data[bp + 22] = 174
            n += 1
    return bytes(data), n


def decode_campaign(data):
    if not os.path.exists(CAMPAIGN):
        return {}
    out = []
    for t in json.load(open(CAMPAIGN)):
        tp = _find_id(data, t["id"])
        bp = _find_id(data, t["boss_id"], lambda p: p + 24 <= len(data) and data[p + 22] == 174)   # status [.,.,174,.]
        if tp is None or bp is None:
            return {}
        events = []
        for e in t["events"]:
            ep = _find_id(data, e["id"])
            if ep is None:
                return {}
            a, b, f, car = struct.unpack_from("<IIfI", data, ep + 4)
            flags = list(data[ep + 20:ep + 24])
            events.append({"offset": ep, "name": e["name"], "type": e["type"], "flags": flags,
                           "decoded": event_summary(e, flags, a),
                           "info_a": a, "info_float": round(f, 3) if f == f else None, "info_car_id": "%08x" % car})
        out.append({"tier": t["tier"], "state": {"offset": tp + 4, "value": struct.unpack_from("<I", data, tp + 4)[0]},
                    "lights_needed_to_unlock": t["lights_needed_to_unlock"],
                    "boss": {"offset": bp, "demands": t["boss_demands"], "targets": t["boss_demand_targets"],
                             "float": [d in FLOAT_DEMANDS for d in t["boss_demands"]],
                             "counters": _counters(data, bp, t["boss_demands"]),
                             "status": list(data[bp + 20:bp + 24])},
                    "events": events})
    total = sum((e["decoded"].get("lights") or 0) for t in out for e in t["events"])
    return {"campaign_hint": CAMPAIGN_HINT, "lights_from_events": total, "campaign": out}


# Game options kept in the save (found by changing them in the game and comparing the saves, 2026-11-01). The audio block sits
# right in front of the bytes 00 00 70 43 00 00 96 43 ... (floats 240, 300, 20, 160); `a` is the offset of the byte in front
# of that pattern, the Brightness Adjust byte (stored as brightness + 1, so it must not be part of the pattern):
SETTINGS_AUDIO_ANCHOR = bytes.fromhex("00 00 70 43 00 00 96 43 00 00 a0 41 00 00 20 43")
SETTINGS_KEYS_ANCHOR = bytes.fromhex("0f0000001d0000007d0000006a000000")      # key table; the u32 in front of it = keyboard layout
SETTINGS_KEYS_SECOND = 169                    # a second copy of the keyboard layout, this many bytes behind the first
AUDIO_FIELDS = [    # (name, offset relative to the anchor, maximum value); all one byte
    ("quality", -11, 2), ("sfx", -10, 9), ("licensed", -9, 1), ("music", -8, 9), ("menu_music", -6, 9),
    ("output", -5, 1), ("room_size", -4, 3), ("dynamic_range", -3, 1), ("music_mode", -2, 2), ("lfe_boost", -1, 9)]
SETTINGS_HINT = ("audio: quality 0 Low, 1 Medium, 2 High; sfx/music/menu_music/lfe_boost 0-9; licensed 0 Off, 1 On; output 0 Stereo, "
                 "1 Surround; room_size 0 Small, 1 Medium, 2 Large (guess), 3 Auditorium; dynamic_range 0 TV, 1 Home theater; "
                 "music_mode 0 Stereo, 1 Quad, 2 Surround. Dynamic range is a basic audio option; room_size, music_mode and lfe_boost (Advanced Audio) are shown only with output Surround. "
                 "controller_layout 0-2 (Layout 1-3), keyboard_layout 0-1 (Layout 1-2). difficulty (the selected difficulty, the byte at "
                 "anchor-15) 0 Easy (default, never chosen), 1 Easy, 2 Medium, 3 Hard; the byte at anchor-7 is unknown. "
                 "brightness (Brightness Adjust) 0-9, stored as value + 1; region_rule (Multiplayer Options) 0 Any Region, 1 Local Region Preferred, 2 Local Region Only.")


def decode_settings(data):
    """the game options stored in the save; {} when the byte patterns are not found"""
    a = data.find(SETTINGS_AUDIO_ANCHOR) - 1
    k = data.find(SETTINGS_KEYS_ANCHOR)
    if a < 15 or k < 4:
        return {}
    audio = {n: {"offset": a + off, "value": data[a + off], "max": mx} for n, off, mx in AUDIO_FIELDS}
    kb = k - 4
    second = kb + SETTINGS_KEYS_SECOND
    out = {"settings": {"hint": SETTINGS_HINT, "audio": audio,
                        "controller_layout": {"offset": a - 13, "value": data[a - 13], "max": 2},
                        "difficulty": {"offset": a - 15, "value": data[a - 15], "max": 3},
                        "brightness": {"offset": a, "value": max(0, data[a] - 1), "max": 9, "bias": 1},
                        "keyboard_layout": {"offset": kb, "offset2": second, "value": data[kb], "max": 1}}}
    a2 = data.find(SETTINGS_AUDIO_ANCHOR, a + 1 + len(SETTINGS_AUDIO_ANCHOR))
    if a2 > 0:
        r = a2 + len(SETTINGS_AUDIO_ANCHOR)
        out["settings"]["region_rule"] = {"offset": r, "value": data[r], "max": 2}
    return out


# Paint jobs (Respray), found by respraying cars in the game and comparing the saves, 2026-11-01. A table of 12-byte entries
# [vehicle id][paint id][index] with a u32 count in front; directly behind it the last chosen [paint id][index]. The colour
# picker is a hexagon of 37 cells (rows of 4, 5, 6, 7, 6, 5, 4; index 0-36 in reading order) with 4 brightness levels:
# level 1 (black) is always the paint "Picker_Black", levels 2, 3, 4 are R<row>C<column> + c, b, a. The index is the cell.
PAINTS = os.path.join(HERE, "blursave_paints.json")      # {"paints": {id: name}, "respray": [ids of the cars that can be resprayed]}
PAINT_ROWS = (4, 5, 6, 7, 6, 5, 4)
PAINT_LEVELS = ("c", "b", "a")                          # brightness levels 2, 3, 4
PAINT_BLACK = "Picker_Black"


def load_paints():
    d = json.load(open(PAINTS))
    return {int(k, 16): v for k, v in d["paints"].items()}, set(d["respray"])


def paint_cell(index):
    """(row, column), both counted from 1, of a hexagon cell"""
    for row, n in enumerate(PAINT_ROWS, 1):
        if index < n:
            return row, index + 1
        index -= n
    raise ValueError("cell index out of range")


FINISHES = {"": "Standard", "P_": "Pearlescent (P_)", "C_": "Candy (C_)", "M_": "Metallic (M_)"}
# The game has three more sets of paints with these prefixes (found in the database; only the brightest level exists; the game hid the
# brightness selector for P_ and C_ but not for M_). Candy (Camaro SS) and a pearl-like sheen (M3 E92 Drift) were seen in the game; the look of
# Metallic is not confirmed. P_ has two ids for cell R2C1 and none for R2C2, which belongs to which is not known.
UNSURE_PAINT = "P_R2C1a|R2C2a"


def paint_name(level, index, finish=""):
    if finish:
        row, col = paint_cell(index)
        return "%sR%dC%da" % (finish, row, col)
    if level == 1:
        return PAINT_BLACK
    row, col = paint_cell(index)
    return "R%dC%d%s" % (row, col, PAINT_LEVELS[level - 2])


def paint_id(level, index, finish=""):
    """id of a paint; KeyError when the game has none for that cell (C_ lacks R3C5, M_ lacks R2C5, P_ R2C1/R2C2 are unsure)"""
    names = {v: k for k, v in load_paints()[0].items() if v != UNSURE_PAINT}
    return names[paint_name(level, index, finish)]


def paint_level(paint):
    """brightness level (1-4) of a paint id; None if unknown"""
    n = load_paints()[0].get(paint)
    if n == PAINT_BLACK:
        return 1
    return 2 + PAINT_LEVELS.index(n[-1]) if n else None


def paint_colour(row, col, level, finish=""):
    """"#rrggbb" of a cell of the colour picker at a brightness level (raw first colour of the paint in the game database)"""
    d = json.load(open(PAINTS))
    by_name = {n: d["colours"][k] for k, n in d["paints"].items() if "|" not in n and k in d.get("colours", {})}
    return "#" + by_name.get(paint_name(level, (sum(PAINT_ROWS[:row - 1]) + col - 1), finish), "000000")


def paint_colour_of(paint):
    """"#rrggbb" of a paint id (its first colour in the game database); None if unknown"""
    c = json.load(open(PAINTS)).get("colours", {}).get("%08x" % paint)
    return "#" + c if c else None


def paint_finish(paint):
    """prefix of a paint id: "" standard, "P_", "C_" or "M_" """
    n = load_paints()[0].get(paint) or ""
    return n[:2] if n[:2] in FINISHES else ""


def decode_paints(data):
    """the paint table; {} when it is not found (a save without any resprayed car has none)"""
    if not os.path.exists(PAINTS):
        return {}
    paints, respray = load_paints()
    veh = load_vehicles()
    for o in range(4, len(data) - 12):
        if struct.unpack_from("<I", data, o)[0] in veh and struct.unpack_from("<I", data, o + 4)[0] in paints:
            break
    else:
        return {}
    start = o - 4
    n = struct.unpack_from("<I", data, start)[0]
    if not 0 < n < 200 or start + 4 + 12 * n + 8 > len(data):
        return {}
    entries = []
    for k in range(n):
        v, p, i = struct.unpack_from("<III", data, start + 4 + 12 * k)
        if v not in veh or p not in paints or i > 36:
            return {}
        entries.append({"vehicle": "%08x" % v, "name": veh[v]["name"], "paint": "%08x" % p, "index": i})
    p, i = struct.unpack_from("<II", data, start + 4 + 12 * n)
    if p not in paints or i > 36:
        return {}
    return {"paints": {"offset": start, "length": 4 + 12 * n + 8, "entries": entries,
                       "last": {"paint": "%08x" % p, "index": i}}}


def encode_paints(pt):
    out = struct.pack("<I", len(pt["entries"]))
    for e in pt["entries"]:
        if not 0 <= e["index"] <= 36:
            raise SystemExit("paint index of %s out of range (0-36)" % e["name"])
        out += struct.pack("<III", int(e["vehicle"], 16), int(e["paint"], 16), e["index"])
    return out + struct.pack("<II", int(pt["last"]["paint"], 16), pt["last"]["index"])



def decode_profile(data):
    out = {}
    at = find_fans(data)
    if at is not None:
        lvl, fans = struct.unpack_from("<II", data, at)
        out["profile"] = {"fan_level": {"offset": at, "value": lvl}, "fans": {"offset": at + 4, "value": fans}}
        veh_now = load_vehicles()
        uid = struct.unpack_from("<I", data, at + 20)[0]
        if uid in veh_now:
            out["profile"]["last_vehicle"] = {"offset": at + 20, "id": "%08x" % uid, "name": veh_now[uid]["name"],
                                              "note": "the car driven last (menu background, car preselected for "
                                                      "the event); change the name to set another car"}
        lt = find_lights(data)
        if lt:
            out["profile"]["lights"] = {"offset": lt[0], "value": struct.unpack_from("<f", data, lt[0])[0]}
            out["profile"]["stat_4d1751a5"] = {"offset": lt[1], "value": struct.unpack_from("<I", data, lt[1])[0],
                                               "note": "unknown, read only. NOT the lights maximum: it is 450 in "
                                                       "three saves of one player and 300055 in a downloaded 100% save"}
        md = find_mod(data)
        if md:
            out["profile"]["mod"] = {"offset": md, "value": data[md], "name": MODS_SEEN.get(data[md]),
                                     "note": "selected boss mod, written after the next finished race. Known values: " +
                                             ", ".join("%d = %s" % kv for kv in sorted(MODS_SEEN.items())) +
                                             "; Modkit (multiplayer only) and other numbers are unverified"}
    if "profile" in out and os.path.exists(RANKS):
        ranks = json.load(open(RANKS))
        fans = out["profile"]["fans"]["value"]
        out["fan_ranks_info"] = ("READ ONLY, from the game database: the fan level and the cars it unlocks follow "
                                 "from the fan count. 'current' marks the level the fans give right now.")
        cur = max(r["rank"] for r in ranks if r["fans"] <= fans)
        out["fan_ranks"] = [dict(r, current=(r["rank"] == cur)) for r in ranks]
    veh = load_vehicles()
    t = find_vehicle_table(data, veh)
    if t:
        rows = []
        for j in range(t[1]):
            o = t[0] + 8 * j
            uid = struct.unpack_from("<I", data, o)[0]
            rows.append({"offset": o, "id": "%08x" % uid, "name": veh[uid]["name"], "class": veh[uid]["class"],
                         "state": data[o + 4]})
        out["vehicles_state_hint"] = STATE_HINT
        out["vehicles"] = sorted(rows, key=lambda r: (r["class"], r["name"]))
    return out


STAT_COUNT = 0x76                                  # entries of the statistics table (the counters of the stickers)
STATS = os.path.join(HERE, "blursave_stats.json")
STATS_HINT = ("the counters behind the stickers (achievements): 118 entries [index u16][00 00][float32]; the entry of index i belongs to "
              "the sticker goal in blursave_stats.json; an entry whose index reads ffff is marked unavailable by the game (Blur.exe does that on "
              "loading for 7 and 99); a goal is reached when the value is at least its goal")


def stat_table(data):
    """offset of the first entry of the statistics table, found through the mod byte (5 bytes behind the last entry); None if there is none"""
    md = find_mod(data)
    return None if md is None else md - 5 - 8 * STAT_COUNT


def decode_stats(data):
    s = stat_table(data)
    if s is None or s < 0:
        return {}
    entries = []
    for i in range(STAT_COUNT):
        idx = struct.unpack_from("<H", data, s + 8 * i)[0]
        entries.append({"index": i, "available": idx == i, "value": struct.unpack_from("<f", data, s + 8 * i + 4)[0]})
    seen = struct.unpack_from("<I", data, s - 8)[0]               # bit mask in front of the count 0x76: videos / hints the player has seen
    return {"stats_info": STATS_HINT, "stats": {"offset": s, "entries": entries, "seen_mask": seen}}


def make_doc(data):
    """the decoded, editable form of a save (what `unpack` writes as JSON); `build(doc)` turns it back into bytes"""
    by_id, _ = load_names()
    known = []
    for i in range(len(data) - 3):
        v = struct.unpack_from("<I", data, i)[0]
        if v >= MIN_ID and v in by_id:
            e = by_id[v]
            known.append({"offset": i, "id": "%08x" % v, "type": e["type"], "name": e["name"]})
    doc = {"format": "blursave-json 1", "size": len(data)}
    doc.update(decode_profile(data))
    doc.update(decode_campaign(data))
    doc.update(decode_settings(data))
    doc.update(decode_paints(data))
    doc.update(decode_stats(data))
    doc.update({"blocks": blocks_of(data), "known_ids": known})
    return doc


def unpack(src, dst):
    data = read_save(src)
    doc = make_doc(data)
    json.dump(doc, open(dst, "w", encoding="utf-8"), indent=1)
    print("unpacked %d bytes, %d blocks, %d known IDs -> %s" % (len(data), len(doc["blocks"]), len(doc["known_ids"]), dst))
    if "profile" in doc:
        p = doc["profile"]
        print("fan level %d, fans %d, %d vehicle records" % (p["fan_level"]["value"], p["fans"]["value"],
                                                           len(doc.get("vehicles", []))))


def build(doc):
    by_id, by_name = load_names()
    data = bytearray(doc["size"])
    for b in doc["blocks"]:
        raw = bytes.fromhex(b["hex"])
        data[b["offset"]:b["offset"] + len(raw)] = raw
    for k in doc["known_ids"]:
        at = k["offset"]
        cur = struct.unpack_from("<I", data, at)[0]
        want = int(k["id"], 16)
        if "%08x" % cur == k["id"] and k["name"]:            # id untouched: the name decides
            ids = by_name.get((k["type"], k["name"]))
            if ids is None:
                ids = [i for (t, n), l in by_name.items() if n == k["name"] for i in l]
            if not ids:
                raise SystemExit("unknown name %r at offset %d" % (k["name"], at))
            if cur not in ids:
                if len(ids) > 1:
                    raise SystemExit("name %r is not unique, set \"id\" instead (offset %d)" % (k["name"], at))
                want = ids[0]
            else:
                want = cur
        if by_id and want not in by_id:
            raise SystemExit("id %08x at offset %d is not in the game database" % (want, at))
        struct.pack_into("<I", data, at, want)
    for key in ("fan_level", "fans"):                       # decoded fields: patched only where they differ
        f = doc.get("profile", {}).get(key)
        if f:
            if not 0 <= f["value"] <= 0xFFFFFFFF:
                raise SystemExit("%s out of range" % key)
            struct.pack_into("<I", data, f["offset"], f["value"])
    lv = doc.get("profile", {}).get("last_vehicle")
    if lv:
        veh_all = load_vehicles()
        cur = struct.unpack_from("<I", data, lv["offset"])[0]
        if lv["id"] == "%08x" % cur and lv["name"] != veh_all.get(cur, {}).get("name"):      # name edited
            ids = [u for u, v in veh_all.items() if v["name"] == lv["name"]]
            if len(ids) != 1:
                raise SystemExit("unknown or ambiguous vehicle name %r" % lv["name"])
            struct.pack_into("<I", data, lv["offset"], ids[0])
        elif lv["id"] != "%08x" % cur:                                                        # id edited
            if int(lv["id"], 16) not in veh_all:
                raise SystemExit("id %s is not a vehicle" % lv["id"])
            struct.pack_into("<I", data, lv["offset"], int(lv["id"], 16))
    st = doc.get("settings")
    if st:
        singles = [("controller_layout", st["controller_layout"]), ("brightness", st["brightness"]),
                   ("difficulty", st["difficulty"])]
        if "region_rule" in st:
            singles.append(("region_rule", st["region_rule"]))
        for name, f in list(st["audio"].items()) + singles:
            if not 0 <= f["value"] <= f["max"]:
                raise SystemExit("setting %s out of range (0-%d)" % (name, f["max"]))
            data[f["offset"]] = f["value"] + f.get("bias", 0)
        kl = st["keyboard_layout"]
        if not 0 <= kl["value"] <= kl["max"]:
            raise SystemExit("keyboard_layout out of range")
        struct.pack_into("<I", data, kl["offset"], kl["value"])
        data[kl["offset2"]] = kl["value"]
    lights = doc.get("profile", {}).get("lights")
    if lights:
        struct.pack_into("<f", data, lights["offset"], float(lights["value"]))
    stats = doc.get("stats")
    if stats:
        if "seen_mask" in stats:
            struct.pack_into("<I", data, stats["offset"] - 8, stats["seen_mask"])
        for e in stats["entries"]:
            if e["available"]:
                struct.pack_into("<f", data, stats["offset"] + 8 * e["index"] + 4, float(e["value"]))
    mod = doc.get("profile", {}).get("mod")
    if mod:
        if not 0 <= mod["value"] <= 255:
            raise SystemExit("mod out of range")
        data[mod["offset"]] = mod["value"]
    for t in doc.get("campaign", []):
        struct.pack_into("<I", data, t["state"]["offset"], t["state"]["value"])
        b = t["boss"]
        for k, (c, d) in enumerate(zip(b["counters"], b["demands"])):
            if d in FLOAT_DEMANDS:
                struct.pack_into("<f", data, b["offset"] + 4 + 4 * k, float(c))
            else:
                struct.pack_into("<I", data, b["offset"] + 4 + 4 * k, int(c))
        data[b["offset"] + 20:b["offset"] + 24] = bytes(b["status"])
        for e in t["events"]:
            data[e["offset"] + 20:e["offset"] + 24] = bytes(e["flags"])
            a, _, f, car = struct.unpack_from("<IIfI", data, e["offset"] + 4)
            if "info_a" in e and e["info_a"] != a:                                  # fans of the saved run
                struct.pack_into("<I", data, e["offset"] + 4, e["info_a"])
            if e.get("info_float") is not None and e["info_float"] != (round(f, 3) if f == f else None):
                struct.pack_into("<f", data, e["offset"] + 12, float(e["info_float"]))   # (probably the time)
            if "info_car_id" in e and e["info_car_id"] != "%08x" % car:
                struct.pack_into("<I", data, e["offset"] + 16, int(e["info_car_id"], 16))
    for v in doc.get("vehicles", []):
        if struct.unpack_from("<I", data, v["offset"])[0] != int(v["id"], 16):
            raise SystemExit("vehicle record at offset %d does not match %s" % (v["offset"], v["name"]))
        if v["state"] not in (0, 1, 2):
            raise SystemExit("state of %s must be 0, 1 or 2" % v["name"])
        data[v["offset"] + 4] = v["state"]
    pt = doc.get("paints")
    if pt:                                                           # last: the table can change its length
        data[pt["offset"]:pt["offset"] + pt["length"]] = encode_paints(pt)
    return bytes(data)


def pack(src, dst):
    data = build(json.load(open(src, encoding="utf-8")))
    write_save(dst, data)
    print("packed %d bytes -> %s" % (len(data), dst))


def check(src):
    data = read_save(src)
    tmp = src + ".check.json"
    unpack(src, tmp)
    again = build(json.load(open(tmp, encoding="utf-8")))
    os.remove(tmp)
    print("round trip of the data: %s" % ("identical" if again == data else "DIFFERENT"))
    return again == data


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "unpack" and len(sys.argv) == 4:
        unpack(sys.argv[2], sys.argv[3])
    elif cmd == "pack" and len(sys.argv) == 4:
        if os.path.abspath(sys.argv[3]) == os.path.abspath(sys.argv[2]):
            raise SystemExit("output must differ from the input")
        pack(sys.argv[2], sys.argv[3])
    elif cmd == "check" and len(sys.argv) == 3:
        sys.exit(0 if check(sys.argv[2]) else 1)
    else:
        print(__doc__)
