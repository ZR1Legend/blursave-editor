"""Reads a Blur save game of the PlayStation 3 (the file AMAXSAVE with its PARAM.PFD) or of the Xbox 360 (an STFS package).

The PS3 protects the file (PFD version 3, key from the game's "secure file id", checked against the HMAC in the PFD). The content is
the same record layout as the PC `blursave`, but big-endian. `read(path)` returns the values the editor knows about; they are
copied into a PC save game by `apply(doc, ps3)` (everything the editor does not know stays as the PC template has it).
Pure Python (own AES), no extra module."""
import hashlib
import hmac
import json
import os
import re
import struct
import zlib

import blursave as bs

SYSCON_MANAGER_KEY = bytes.fromhex("D413B89663E1FE9F75143D3BB4565274")
SECURE_FILE_ID = b"BEAUTIFUL_CHAOS!"           # games.conf: [BLUS30295/BLES00759/BLJM60244]
MAGIC_BE = b"\xab\xcd\xe3\x37"


# ---------- AES-128 (decrypt and encrypt of single blocks, CBC decrypt) ----------
def _tables():
    sbox, p, q = [0] * 256, 1, 1
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ (q << 1 | q >> 7) ^ (q << 2 | q >> 6) ^ (q << 3 | q >> 5) ^ (q << 4 | q >> 4)
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox, [sbox.index(i) for i in range(256)]


SBOX, INV = _tables()


def _xt(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a, b = _xt(a), b >> 1
    return r


def _expand(key):
    w = [list(key[4 * i:4 * i + 4]) for i in range(4)]
    rcon = 1
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = [SBOX[t[1]] ^ rcon, SBOX[t[2]], SBOX[t[3]], SBOX[t[0]]]
            rcon = _xt(rcon)
        w.append([a ^ b for a, b in zip(w[i - 4], t)])
    return [sum(w[4 * r:4 * r + 4], []) for r in range(11)]


def aes_encrypt_block(key, block):
    ks, s = _expand(key), [a ^ b for a, b in zip(block, _expand(key)[0])]
    for r in range(1, 11):
        s = [SBOX[b] for b in s]
        s = [s[(i + 4 * (i % 4)) % 16] for i in range(16)]                       # ShiftRows
        if r < 10:
            m = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                m += [_mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3], a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3],
                      a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3), _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)]
            s = m
        s = [a ^ b for a, b in zip(s, ks[r])]
    return bytes(s)


def aes_decrypt_block(key, block):
    ks, s = _expand(key), [a ^ b for a, b in zip(block, _expand(key)[10])]
    for r in range(9, -1, -1):
        s = [s[(i - 4 * (i % 4)) % 16] for i in range(16)]                       # InvShiftRows
        s = [INV[b] for b in s]
        s = [a ^ b for a, b in zip(s, ks[r])]
        if r > 0:
            m = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                m += [_mul(a[0], 14) ^ _mul(a[1], 11) ^ _mul(a[2], 13) ^ _mul(a[3], 9),
                      _mul(a[0], 9) ^ _mul(a[1], 14) ^ _mul(a[2], 11) ^ _mul(a[3], 13),
                      _mul(a[0], 13) ^ _mul(a[1], 9) ^ _mul(a[2], 14) ^ _mul(a[3], 11),
                      _mul(a[0], 11) ^ _mul(a[1], 13) ^ _mul(a[2], 9) ^ _mul(a[3], 14)]
            s = m
    return bytes(s)


def cbc_decrypt(key, iv, data):
    out, prev = bytearray(), iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(aes_decrypt_block(key, blk), prev))
        prev = blk
    return bytes(out)


# ---------- Xbox 360: STFS package (CON / LIVE / PIRS) ----------
def stfs_file(raw):
    """the content of the save file inside an STFS package (not encrypted there); the package signature is not checked"""
    if len(raw) < 0xB000:
        raise SystemExit("the Xbox 360 package is too short")
    first = (struct.unpack_from(">I", raw, 0x340)[0] + 0xFFF) & 0xF000       # the first block follows the header
    step = 1 if raw[0x379 + 2] & 1 else 2                                 # blocks per hash table (read-only packages 1, the others 2)
    ft_count = struct.unpack_from("<H", raw, 0x379 + 3)[0]
    ft_start = raw[0x379 + 5] | raw[0x379 + 6] << 8 | raw[0x379 + 7] << 16

    def offset(n):
        adj = (n // 0xAA + 1) * step
        if n >= 0xAA:
            adj += (n // 0x70E4 + 1) * step
        if n >= 0x70E4:
            adj += step
        return first + (n + adj) * 0x1000

    def chain(start, count, consecutive):
        if consecutive:
            return list(range(start, start + count))
        if start + count >= 0xAA:
            raise SystemExit("this Xbox 360 package is larger than a save game")
        out, n = [], start
        for _ in range(count):                                           # level-0 hash table (at the first block): 24 bytes per block
            out.append(n)
            n = int.from_bytes(raw[first + 24 * n + 21:first + 24 * n + 24], "big")
        return out

    found = []
    for b in chain(ft_start, ft_count, True):
        for i in range(0x40):
            e = raw[offset(b) + 0x40 * i: offset(b) + 0x40 * (i + 1)]
            if len(e) < 0x40 or e[0] == 0:
                break
            flags = e[0x28]
            if flags & 0x80:                                              # a directory
                continue
            name = e[:flags & 0x3F].decode("latin-1")
            blocks = e[0x29] | e[0x2A] << 8 | e[0x2B] << 16
            start = e[0x2F] | e[0x30] << 8 | e[0x31] << 16
            size = struct.unpack_from(">I", e, 0x34)[0]
            found.append((name, chain(start, blocks, bool(flags & 0x40)), size))
    if not found:
        raise SystemExit("the Xbox 360 package holds no file")
    name, blocks, size = next((f for f in found if f[0].lower() == "savegame"), found[0])
    return b"".join(raw[offset(n):offset(n) + 0x1000] for n in blocks)[:size]


# ---------- PARAM.PFD and the protected file ----------
def _hash_key(secure_id):
    """the 20-byte hash key of a file: the 16 bytes of the secure file id with 11, 15, 14, 10 inserted at 1, 2, 5, 8"""
    out, j = bytearray(20), 0
    for i in range(20):
        if i in (1, 2, 5, 8):
            out[i] = {1: 11, 2: 15, 5: 14, 8: 10}[i]
        else:
            out[i] = secure_id[j]
            j += 1
    return bytes(out)


def decrypt_file(path):
    """the decrypted AMAXSAVE: path = the file (PARAM.PFD in the same folder) or the save folder"""
    if os.path.isdir(path):
        path = os.path.join(path, "AMAXSAVE")
    folder, name = os.path.split(path)
    raw = open(path, "rb").read()
    if raw[:4] == MAGIC_BE:                                  # already decrypted
        return raw
    if raw[:4] in (b"CON ", b"LIVE", b"PIRS"):               # Xbox 360
        return stfs_file(raw)
    pfd_path = os.path.join(folder, "PARAM.PFD")
    if not os.path.exists(pfd_path):
        raise SystemExit("PARAM.PFD is missing next to %s - the PS3 save cannot be decrypted without it" % name)
    pfd = open(pfd_path, "rb").read()
    magic, ver = struct.unpack_from(">QQ", pfd, 0)
    if magic != 0x50464442 or ver != 3:
        raise SystemExit("PARAM.PFD: unsupported version %d" % ver)
    capacity, _, used = struct.unpack_from(">QQQ", pfd, 96)
    table = 96 + 24 + capacity * 8
    hk = _hash_key(SECURE_FILE_ID)
    for i in range(used):
        e = pfd[table + 272 * i:table + 272 * (i + 1)]
        if e[8:73].split(b"\0")[0].decode("latin-1").upper() != name.upper():
            continue
        if hmac.new(hk, raw, hashlib.sha1).digest() != e[144:164]:
            raise SystemExit("%s does not match its PARAM.PFD (changed or from another game)" % name)
        size = struct.unpack_from(">Q", e, 264)[0]
        entry_key = cbc_decrypt(SYSCON_MANAGER_KEY, hk[:16], e[80:144])[:16]
        out = bytearray()
        for n in range(len(raw) // 16):
            mask = aes_encrypt_block(entry_key, struct.pack(">QQ", n, 0))
            out += bytes(a ^ b for a, b in zip(aes_decrypt_block(entry_key, raw[16 * n:16 * n + 16]), mask))
        return bytes(out[:size])
    raise SystemExit("%s is not listed in PARAM.PFD" % name)


def payload(path):
    """the entpacked big-endian data of a PS3 save game"""
    d = decrypt_file(path)
    if d[:4] != MAGIC_BE:
        raise SystemExit("not a Blur save game (decryption gave no ab cd e3 37)")
    usz, csz = struct.unpack_from(">II", d, 4)
    data = zlib.decompressobj().decompress(d[12:12 + csz])
    if len(data) != usz:
        raise SystemExit("unexpected size in the PS3 save game")
    return data


# ---------- the values ----------
def _ids(data, uid):
    key, hits, i = struct.pack(">I", uid), [], -1
    while True:
        i = data.find(key, i + 1)
        if i < 0:
            return hits
        hits.append(i)


def _one(data, uid):
    h = _ids(data, uid)
    return h[0] if len(h) == 1 else None


def _stat_table(data):
    """offset of the 118 statistics entries [index u32][float32]; index ffffffff = not available"""
    for m in re.finditer(rb"\x00\x00\x00\x00.{4}\x00\x00\x00\x01.{4}\x00\x00\x00\x02.{4}\x00\x00\x00\x03.{4}\x00\x00\x00\x04", data, re.S):
        s = m.start()
        if struct.unpack_from(">I", data, s + 8 * 0x75)[0] == 0x75 and struct.unpack_from(">I", data, s + 8 * 0x76)[0] < 0x10000:
            return s
    return None


def _vehicle_table(data, veh):
    best, i = None, 0
    while i < len(data) - 8:
        k = 0
        while i + 8 * k + 4 <= len(data) and struct.unpack_from(">I", data, i + 8 * k)[0] in veh:
            k += 1
        if k >= 20 and (best is None or k > best[1]):
            best = (i, k)
        i += 8 * k if k else 1
    if best:
        i, k = best
        while k > 1 and struct.unpack_from(">I", data, i)[0] > struct.unpack_from(">I", data, i + 8)[0]:
            i, k = i + 8, k - 1
        best = (i, k)
    return best


def read(path):
    """the values of a PS3 save game: level, fans, last vehicle, mod, stats, vehicle states, campaign"""
    data = payload(path)
    veh = bs.load_vehicles()
    out = {"size": len(data)}
    tier = _one(data, bs.FAN_ANCHOR_TIER_ID)
    if tier is None or tier < 60:
        raise SystemExit("the fan data of the PS3 save game were not found")
    at = tier - 60
    out["fan_level"], out["fans"] = struct.unpack_from(">I", data, at)[0], struct.unpack_from(">Q", data, at + 4)[0]
    lv = struct.unpack_from(">I", data, at + 20)[0]
    out["last_vehicle"] = "%08x" % lv if lv in veh else None
    s = _stat_table(data)
    if s is None:
        raise SystemExit("the statistics table of the PS3 save game was not found")
    out["stats"] = {i: struct.unpack_from(">f", data, s + 8 * i + 4)[0] for i in range(bs.STAT_COUNT)
                    if struct.unpack_from(">I", data, s + 8 * i)[0] == i}
    out["mod"] = struct.unpack_from(">I", data, s + 8 * bs.STAT_COUNT + 5)[0]
    out["seen_mask"] = struct.unpack_from(">I", data, s - 8)[0]
    t = _vehicle_table(data, veh)
    if t is None:
        raise SystemExit("the vehicle table of the PS3 save game was not found")
    out["vehicles"] = {"%08x" % struct.unpack_from(">I", data, t[0] + 8 * j)[0]: data[t[0] + 8 * j + 4] for j in range(t[1])}
    camp = []
    for td in json.load(open(bs.CAMPAIGN)):
        tp, bp = _one(data, td["id"]), _one(data, td["boss_id"])
        if tp is None or bp is None:
            raise SystemExit("the campaign data of the PS3 save game were not found")
        raw = struct.unpack_from(">4I", data, bp + 4)
        counters = [struct.unpack(">f", struct.pack(">I", c))[0] if d in bs.FLOAT_DEMANDS else c for c, d in zip(raw, td["boss_demands"])]
        events = []
        for e in td["events"]:
            ep = _one(data, e["id"])
            if ep is None:
                raise SystemExit("the event %s of the PS3 save game was not found" % e["name"])
            a, _, f, car = struct.unpack_from(">IIfI", data, ep + 4)
            events.append({"flags": list(data[ep + 20:ep + 24]), "info_a": a, "info_float": f, "info_car_id": "%08x" % car})
        camp.append({"state": data[tp + 4], "counters": counters, "status": list(data[bp + 20:bp + 24]), "events": events})
    out["campaign"] = camp
    return out


def apply(doc, ps3):
    """copies the values into a decoded PC save game (`blursave.make_doc`); returns a short description of what was taken over"""
    p = doc["profile"]
    p["fan_level"]["value"], p["fans"]["value"] = ps3["fan_level"], min(ps3["fans"], 0xFFFFFFFF)
    if ps3["last_vehicle"]:                                             # a new profile has no car there yet: the field is 20 bytes behind the level
        lv = p.setdefault("last_vehicle", {"offset": p["fan_level"]["offset"] + 20, "id": "", "name": "",
                                           "note": "the car driven last (menu background, car preselected for the event)"})
        lv["id"] = ps3["last_vehicle"]
        lv["name"] = bs.load_vehicles()[int(ps3["last_vehicle"], 16)]["name"]
    if "mod" in p:
        p["mod"]["value"] = ps3["mod"] if ps3["mod"] < 256 else 255
        p["mod"]["name"] = bs.MODS_SEEN.get(p["mod"]["value"])
    if "stats" in doc:
        doc["stats"]["seen_mask"] = ps3["seen_mask"]                        # the cutscenes the player has seen: the game does not replay them
    for e in doc.get("stats", {}).get("entries", []):
        if e["available"] and e["index"] in ps3["stats"]:
            e["value"] = ps3["stats"][e["index"]]
            if e["index"] == 0x1D and "lights" in p:                      # the lights counter is this entry
                p["lights"]["value"] = e["value"]
    for v in doc["vehicles"]:
        if v["id"] in ps3["vehicles"]:
            v["state"] = ps3["vehicles"][v["id"]]
    for t, s in zip(doc.get("campaign", []), ps3["campaign"]):
        t["state"]["value"] = s["state"]
        t["boss"]["counters"] = list(s["counters"])
        t["boss"]["status"] = [s["status"][0], s["status"][1], 174, s["status"][3]]        # the PC game keeps the constant 174
        for e, se in zip(t["events"], s["events"]):
            e["flags"] = list(se["flags"])
            e["info_a"], e["info_car_id"] = se["info_a"], se["info_car_id"]
            e["info_float"] = round(se["info_float"], 3) if se["info_float"] == se["info_float"] else None
    return ("level %d, %s fans, %d events, %d counters" % (ps3["fan_level"], format(ps3["fans"], ","),
            sum(1 for t in ps3["campaign"] for e in t["events"] if e["flags"][0] == 2), len(ps3["stats"])))


# ---------- the other way: a PC save game into a PS3 save game ----------
def export(doc, template):
    """the big-endian data of a PS3 save game: the PS3 save game `template` (path) with the values of the decoded PC save game `doc`
    written into it (level, fans, last car, mod, counters, seen cutscenes, car states, campaign); the rest stays as in the template.
    Returns the entpacked data; `container` makes the file of them."""
    data = bytearray(payload(template))
    veh = bs.load_vehicles()
    tier = _one(bytes(data), bs.FAN_ANCHOR_TIER_ID)
    if tier is None or tier < 60:
        raise SystemExit("the template has no fan data")
    at, p = tier - 60, doc["profile"]
    struct.pack_into(">I", data, at, p["fan_level"]["value"])
    struct.pack_into(">Q", data, at + 4, p["fans"]["value"])
    lv = p.get("last_vehicle")
    if lv and int(lv["id"], 16) in veh:
        struct.pack_into(">I", data, at + 20, int(lv["id"], 16))
    s = _stat_table(bytes(data))
    if s is None:
        raise SystemExit("the template has no statistics table")
    for e in doc.get("stats", {}).get("entries", []):
        if e["available"] and struct.unpack_from(">I", data, s + 8 * e["index"])[0] == e["index"]:
            struct.pack_into(">f", data, s + 8 * e["index"] + 4, float(e["value"]))
    if "mod" in p:
        struct.pack_into(">I", data, s + 8 * bs.STAT_COUNT + 5, p["mod"]["value"])
    if "seen_mask" in doc.get("stats", {}):
        struct.pack_into(">I", data, s - 8, doc["stats"]["seen_mask"])
    t = _vehicle_table(bytes(data), veh)
    if t is None:
        raise SystemExit("the template has no vehicle table")
    states = {v["id"]: v["state"] for v in doc["vehicles"]}
    for j in range(t[1]):
        vid = "%08x" % struct.unpack_from(">I", data, t[0] + 8 * j)[0]
        if vid in states:
            data[t[0] + 8 * j + 4] = states[vid]
    for td, tier_doc in zip(json.load(open(bs.CAMPAIGN)), doc.get("campaign", [])):
        tp, bp = _one(bytes(data), td["id"]), _one(bytes(data), td["boss_id"])
        if tp is None or bp is None:
            raise SystemExit("the template has no campaign data")
        data[tp + 4] = tier_doc["state"]["value"] & 0xFF                 # the state is the first byte, the three behind it are stray bytes
        b = tier_doc["boss"]
        for k, (c, d) in enumerate(zip(b["counters"], td["boss_demands"])):
            if d in bs.FLOAT_DEMANDS:
                struct.pack_into(">f", data, bp + 4 + 4 * k, float(c))
            else:
                struct.pack_into(">I", data, bp + 4 + 4 * k, int(c))
        data[bp + 20], data[bp + 21], data[bp + 23] = b["status"][0], b["status"][1], b["status"][3]     # the PS3 keeps 0 in the third byte
        for e, ed in zip(td["events"], tier_doc["events"]):
            ep = _one(bytes(data), e["id"])
            if ep is None:
                raise SystemExit("the template has no event %s" % e["name"])
            data[ep + 20:ep + 24] = bytes(ed["flags"])
            a_, _, f_, car_ = struct.unpack_from(">IIfI", data, ep + 4)              # written only where the PC value differs (it is rounded)
            if "info_a" in ed and ed["info_a"] != a_:
                struct.pack_into(">I", data, ep + 4, ed["info_a"])
            if ed.get("info_float") is not None and ed["info_float"] != (round(f_, 3) if f_ == f_ else None):
                struct.pack_into(">f", data, ep + 12, float(ed["info_float"]))
            if "info_car_id" in ed and ed["info_car_id"] != "%08x" % car_:
                struct.pack_into(">I", data, ep + 16, int(ed["info_car_id"], 16))
    return bytes(data)


def container(data):
    """the file AMAXSAVE (not encrypted): ab cd e3 37, size, packed size (big-endian), zlib stream with a sync flush at the end"""
    c = zlib.compressobj(9)
    stream = c.compress(data) + c.flush(zlib.Z_SYNC_FLUSH)
    return struct.pack(">III", 0xABCDE337, len(data), len(stream)) + stream
