"""Icons from the game files: reads the vector icon sheets (/ui/data/ipf/*.ipf in root.pak) and draws them with PIL.

The .ipf layout is described in the Blur Map Builder (MIT licence, (c) 2026 MDPRO), car/car_icon.py and
flat_earth/minimap.py: header (u32 0x100000, u32 1, u32 3, u32 0), a named root node and a child count, then nodes
{u32 kind (3 group / 1 shape), u32 flags, u32 name length, name}; a group is followed by u32 child count and the children.
A shape: 34 header bytes, 6 floats (box u0, v0, 0, u1, v1, 0), 16 bytes, u32 n + n convex polygons {u32 k, k x 6 floats
(u, v, a, b, c, d)}, u32 n + n index lists {u32 k, k x u16}, u32 0. (u, v) are in 0..1 over the icon's width.
Only the polygons' outlines (u, v) are drawn; the curve data (a, b, c, d) is not used, so round edges are polygons.

The pictures are made from the user's own game files at the first start and kept in a cache folder; they are not shipped.
"""
import os
import re
import struct
import sys

from PIL import Image, ImageDraw

from blurpak import Pak

CAR_SHEETS = ["/ui/data/ipf/car_icons_%s.ipf" % c for c in "abcd"]
SCALE = 4                                           # supersampling


def _skip_shape(d, q):
    q += 34 + 24 + 16
    for item in (24, 2):                             # polygons (k x 6 floats), then index lists (k x u16)
        n = struct.unpack_from("<I", d, q)[0]
        q += 4
        for _ in range(n):
            k = struct.unpack_from("<I", d, q)[0]
            q += 4 + k * item
    return q + 4


def _walk(d, p, out, owner=None):
    """collects {name: [shape body offsets]}; a shape inside a group belongs to the group's name (a car made of parts)"""
    kind, _, nl = struct.unpack_from("<III", d, p)
    name = d[p + 12:p + 12 + nl].decode("latin1").lower()
    q = p + 12 + nl
    if kind == 3:
        n = struct.unpack_from("<I", d, q)[0]
        q += 4
        for _ in range(n):
            q = _walk(d, q, out, owner or name)
        return q
    out.setdefault(owner or name, []).append(q)
    return _skip_shape(d, q)


def shapes(d):
    """{lowercase name: [offset of each shape body]} of an .ipf sheet"""
    nl = struct.unpack_from("<I", d, 16)[0]
    at = 20 + nl
    n = struct.unpack_from("<I", d, at)[0]
    out, p = {}, at + 4
    for _ in range(n):
        p = _walk(d, p, out)
    return out


def shapes_scan(d):
    """{lowercase name: [offset of the shape body]} for sheets whose entries are not all of the usual layout (location_icons.ipf has
    a "<guide>" entry that shape_skip cannot walk): every top-level shape starts with u32 1, u32 1, u32 name length, name"""
    out = {}
    for m in re.finditer(rb"\x01\x00\x00\x00\x01\x00\x00\x00([\x03-\x28])\x00\x00\x00([a-zA-Z_<>0-9 ]+)", d):
        n = m.group(1)[0]
        name = m.group(2)[:n]
        if len(name) == n:
            out.setdefault(name.decode("latin1").lower(), []).append(m.end())
    return out


def polygons(d, body):
    """(box height in units of the width, [array of (u, v) per convex polygon])"""
    q = body + 34
    bb = struct.unpack_from("<6f", d, q)
    q += 24 + 16
    n = struct.unpack_from("<I", d, q)[0]
    q += 4
    polys = []
    for _ in range(n):
        k = struct.unpack_from("<I", d, q)[0]
        v = struct.unpack_from("<%df" % (6 * k), d, q + 4)
        polys.append([(v[6 * i], v[6 * i + 1]) for i in range(k)])
        q += 4 + 24 * k
    return bb[4], polys


def _mask(d, bodies, w2, h):
    big = Image.new("L", (w2, max(1, int(round(h * w2)) + SCALE)), 0)
    dr = ImageDraw.Draw(big)
    for b in bodies:
        for p in polygons(d, b)[1]:
            dr.polygon([(u * w2, v * w2) for u, v in p], fill=255)
    return big


def render(d, bodies, width, color=(120, 190, 255), glyph=(235, 245, 255), layered=False):
    """RGBA picture of a shape (or of the parts of a group), `width` pixels wide, transparent background.
    layered=True: the largest part is the plate (`color`), the others are the symbol on it (`glyph`)."""
    boxes = [polygons(d, b)[0] for b in bodies]
    w2 = width * SCALE
    if layered and len(bodies) > 1:
        order = sorted(range(len(bodies)), key=lambda i: -(struct.unpack_from("<6f", d, bodies[i] + 34)[3] * boxes[i]))
        h = boxes[order[0]]
        plate = _mask(d, [bodies[order[0]]], w2, h)
        sym = _mask(d, [bodies[i] for i in order[1:]], w2, h)
        size = (width, max(1, plate.size[1] // SCALE))
        out = Image.new("RGBA", size, color + (0,))
        out.putalpha(plate.resize(size, Image.LANCZOS))
        top = Image.new("RGBA", size, glyph + (0,))
        top.putalpha(sym.resize(size, Image.LANCZOS))
        out.alpha_composite(top)
        return out
    big = _mask(d, bodies, w2, boxes[0])
    mask = big.resize((width, max(1, big.size[1] // SCALE)), Image.LANCZOS)
    out = Image.new("RGBA", mask.size, color + (0,))
    out.putalpha(mask)
    return out


class CarIcons:
    """car icons by the game's vehicle model name (e.g. "Opel_AstraExtreme_Stock")"""

    def __init__(self, root_pak, cache_dir=None):
        self.root_pak, self.cache_dir = root_pak, cache_dir
        self._sheets = None

    def _load(self):
        if self._sheets is None:
            pak = Pak(self.root_pak)
            try:
                self._sheets = []
                for s in CAR_SHEETS:
                    d = pak.read(s)
                    self._sheets.append((d, shapes(d)))
            finally:
                pak.close()
        return self._sheets

    def names(self):
        return sorted({n for _, sh in self._load() for n in sh})

    def get(self, model_name, width=120, color=(120, 190, 255)):
        """the car's silhouette; boss/Legend variants without their own icon use the car they are made from"""
        for key in _candidates(model_name):
            for d, sh in self._load():
                if key in sh:
                    return render(d, sh[key], width, color)
        base = "".join(model_name.lower().split("_legend")[0].split("_"))          # e.g. opelastraextreme
        for d, sh in self._load():
            for key in sorted(sh):
                if "".join(key.split("_")).startswith(base):
                    return render(d, sh[key], width, color)
        return None


def _candidates(name):
    """model name, then the same without its last part (owner, Legend ...), then the Stock/Race/... variant of the base car"""
    parts = name.lower().split("_")
    out = [name.lower()]
    for i in range(len(parts) - 1, 1, -1):
        head = parts[:i]
        out.append("_".join(head))
        if head[-1] not in ("stock", "race", "rat", "drag", "drift", "tuner", "offroad"):
            out.append("_".join(head + ["stock"]))
    out.append("_".join(parts[:2] + ["stock"]))
    seen = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen


MOD_SHEET = "/ui/data/ipf/sp_mod_icons.ipf"
MOD_SHAPES = {                                      # mod name (multiplayer.loc) -> shape in sp_mod_icons.ipf
    "Overbolt": "additionalblindfireshots", "Fan Nitro": "fansnitrogift", "Scatter Shot": "shotgunblindfire",
    "Armor Plating": "repairbonus", "Titanium Shield": "doubleshield", "Super Shunt": "shuntdamage",
    "Quadshock": "additionalshockdomes", "Nitro Rift": "nitrorift", "Modkit": "shannonbossmod"}


def find_root_pak(extra=()):
    """root.pak of an installed Blur: given folders, the project's Game folder, common Steam/GOG places"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(x, "cache", "root.pak") for x in extra]
    cands.append(os.path.join(here, "..", "Game", "cache", "root.pak"))
    exe = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else None
    if exe:                                         # packaged .exe: next to it, or in a Game folder next to / above it
        for base in (exe, os.path.join(exe, "Game"), os.path.join(exe, "..", "Game"), os.path.join(exe, "..")):
            cands.append(os.path.join(base, "cache", "root.pak"))
    for pf in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), "C:\\", "D:\\"):
        if pf:
            for sub in (("Steam", "steamapps", "common", "Blur"), ("GOG Games", "Blur"),
                        ("GOG Galaxy", "Games", "Blur"), ("Games", "Blur"), ("Blur",)):
                cands.append(os.path.join(pf, *sub, "cache", "root.pak"))
    return next((os.path.normpath(c) for c in cands if os.path.isfile(c)), None)


class Icons:
    """car and mod icons, drawn from the user's own root.pak (nothing is stored or shipped)"""

    def __init__(self, root_pak):
        self.cars = CarIcons(root_pak)
        self._mods = None
        self.root_pak = root_pak

    def car(self, model_name, width=96):
        return self.cars.get(model_name, width)

    def mod(self, mod_name, width=64):
        if self._mods is None:
            pak = Pak(self.root_pak)
            try:
                d = pak.read(MOD_SHEET)
            finally:
                pak.close()
            self._mods = (d, shapes(d))
        d, sh = self._mods
        key = MOD_SHAPES.get(mod_name)
        return render(d, sh[key], width, color=(24, 110, 235), glyph=(205, 240, 255), layered=True) if key in sh else None
