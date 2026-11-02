"""Renders the car, class, status, manufacturer and mod pictures from an installed game into tools/blursave_icons.zip
(cars/<model name>.png, seen/, new/ and locked/<model name>.png, classes/<A-D>.png, status/, logos/<maker>.png, mods/<mod name>.png).

Development tool, not part of the editor. Needs PIL and the game's cache/root.pak (see blurico.find_root_pak).
The zip is added to the editor .exe by build_exe.bat.
"""
import io
import json
import os
import sys
import zipfile

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blurico                                              # noqa: E402
import blurbpr                                              # noqa: E402
import blurpak                                              # noqa: E402
import blursave as bs                                       # noqa: E402
import blurdisplay                                          # noqa: E402
import make_wordmark                                        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
USED = set(blurdisplay.MAKERS.values()) | set(blurdisplay.MAKER_EXCEPTIONS.values())      # logos of cars that exist
OUT = os.path.join(HERE, "blursave_icons.zip")
CAR_WIDTH, MOD_WIDTH, CLASS_WIDTH = 140, 48, 56
COMMON = "/ui/data/ui_common.bpr"                     # blur_logo, blur_lights (the lights coin), default_gamerpic
BUNDLE = "/ui/data/ui_frontend.bpr"                   # pictures man_<maker>: the manufacturer logos
LOGO_BOX = (84, 46)
LIST_W, LIST_PAD_X, LIST_PAD_Y = 88, 14, 8      # status column: silhouette width, space left of / above it for the "new" triangle
CLASS_SHEET = "/ui/data/ipf/common_icons.ipf"        # shapes class_a ... class_d, alert
NEW_GREEN, LOCKED_GREY = (66, 212, 96), (84, 96, 130)        # the "new" triangle; cars not awarded are drawn in grey


def alert_icon(sheet, width=28, scale=4):
    """the "new" triangle: the outline of the shape alert (its last, largest polygon) with the exclamation mark cut out"""
    h, polys = blurico.polygons(sheet, blurico.shapes(sheet)["alert"][0])
    w2 = width * scale
    mask = Image.new("L", (w2, int(round(h * w2)) + scale), 0)
    dr = ImageDraw.Draw(mask)
    for i, fill in ((56, 255), (54, 0), (55, 0)):          # triangle, bar and dot of the exclamation mark
        dr.polygon([(u * w2, v * w2) for u, v in polys[i]], fill=fill)
    mask = mask.resize((width, max(1, mask.height // scale)), Image.LANCZOS)
    out = Image.new("RGBA", mask.size, NEW_GREEN + (0,))
    out.putalpha(mask)
    return out


def header_images(common, sheet):
    """the pictures of the header bar: the "blur" logo, the lights coin, the fan icon and the person of the profile badge"""
    pics = blurbpr.pictures(common)
    out = {}
    f, w, h, d = pics["blur_logo"]
    logo = blurbpr.decode(f, w, h, d, order="ARGB")
    mark = make_wordmark.build(logo.getchannel("A"))                 # "blursave editor": the game's "blur" plus drawn letters
    white = Image.new("RGBA", mark.size, (255, 255, 255, 0))
    white.putalpha(mark)
    out["logo"] = white.resize((round(white.width * 30 / white.height), 30), Image.LANCZOS)
    f, w, h, d = pics["blur_lights"]
    out["coin"] = blurbpr.decode(f, w, h, d).crop((0, 0, 64, 64)).resize((24, 24), Image.LANCZOS)      # the first coin: lights
    f, w, h, d = pics["default_gamerpic"]
    lum = blurbpr.decode(f, w, h, d).convert("RGB").convert("L").point(lambda v: 255 if v > 130 else 0)   # the person is the bright part
    person = Image.new("RGBA", lum.size, (10, 26, 92, 0))
    person.putalpha(lum)
    person = person.crop(lum.getbbox())
    out["person"] = person.resize((round(person.width * 30 / person.height), 30), Image.LANCZOS)
    out["fan"] = blurico.render(sheet, blurico.shapes(sheet)["fan"], 24, color=(255, 163, 26), glyph=(255, 224, 160), layered=True)
    return out


EVENT_SHAPES = {"Race": "style_racing", "Destruction": "survivor", "Checkpoint": "quick_race", "One-on-One": "deathmatch"}
EVENT_BLUE = (40, 190, 255)
COIN_FRAMES = {"coin_1": 1, "coin_2": 2, "coin_3": 3, "fan_on": 4, "run_on": 5, "coin_off": 6, "fan_off": 7, "run_off": 8}   # frames of blur_lights (64 px each): coins red = easy, blue = medium, gold = hard
COIN_SIZE, LANDMARK_H, TYPE_H = 30, 40, 30


def event_images(common, pak_path, sheet):
    """pictures of the Career event cards: the white landmark of each city, the light coins (lit and dark: place, fan target, fan
    run) and the icon of each kind of event"""
    out = {}
    f, w, h, d = blurbpr.pictures(common)["blur_lights"]
    strip = blurbpr.decode(f, w, h, d)
    for name, k in COIN_FRAMES.items():
        out[name] = strip.crop((64 * k, 0, 64 * k + 64, 64)).resize((COIN_SIZE, COIN_SIZE), Image.LANCZOS)
    coin = out["coin_2"].convert("RGBA")                           # the silver coin of a locked event: the blue coin without its colour
    out["coin_lock"] = silver_of(coin)
    events = json.load(open(os.path.join(HERE, "blursave_events.json")))
    loc = blurpak.Pak(pak_path)
    try:
        loc_sheet = loc.read("/ui/data/ipf/location_icons.ipf")
    finally:
        loc.close()
    loc_shapes = blurico.shapes_scan(loc_sheet)
    for icon in sorted({e["icon"] for e in events.values()}):
        im = blurico.render(loc_sheet, loc_shapes[icon], 160, color=(255, 255, 255), glyph=(255, 255, 255))
        out["lm_" + icon] = im.resize((max(1, round(im.width * LANDMARK_H / im.height)), LANDMARK_H), Image.LANCZOS)
    shapes = blurico.shapes(sheet)
    for kind, shape in EVENT_SHAPES.items():
        for tag, col in (("type_", EVENT_BLUE), ("typedim_", (62, 128, 245)), ("typelock_", (205, 214, 232)), ("typelockdim_", (110, 120, 142))):   # chosen, other, locked card
            im = blurico.render(sheet, shapes[shape], 160, color=col, glyph=col)
            out[tag + kind] = im.resize((max(1, round(im.width * TYPE_H / im.height)), TYPE_H), Image.LANCZOS)
    for level in (1, 2, 3):                                    # orange for Hard, blue for Easy and Medium, as in the game
        lit, dim = ((255, 156, 28), (120, 72, 22)) if level == 3 else ((47, 134, 255), (18, 44, 110))
        out["diff_%d" % level] = difficulty_icon(sheet, shapes, level, 24, lit, dim)
    for name in ("fan", "run"):                                # the fan target and the fan run of a locked event: silver, and darker
        out[name + "_lock"] = silver_of(out[name + "_on"])
        out[name + "_lockdim"] = silver_of(out[name + "_on"], 0.55)
    out["coin_lockdim"] = silver_of(coin, 0.55)
    out["lock"] = padlock(30)
    return out


def silver_of(im, gain=1.0):
    """a coin or icon in silver (grey with a touch of blue, so that it does not look like bronze), `gain` darkens it"""
    im = im.convert("RGBA")
    g = im.convert("L").point(lambda v: min(255, int(v * 1.2) + 30))
    r = g.point(lambda v: int(v * 0.93 * gain))
    gr = g.point(lambda v: int(v * 0.98 * gain))
    b = g.point(lambda v: min(255, int(v * 1.1 * gain)))
    return Image.merge("RGBA", (r, gr, b, im.getchannel("A")))


def difficulty_icon(sheet, shapes, level, height, lit_colour, dim_colour):
    """the orange difficulty symbol: blocks (lit one more for each level) and the person; the blocks not lit are dark"""
    low = shapes["ai_difficulty_low"]                          # parts: middle block, top block, person, lower left block
    lit = [low[3], low[2]] + ([low[0]] if level >= 2 else []) + ([low[1]] if level >= 3 else [])
    dim = ([low[0]] if level < 2 else []) + ([low[1]] if level < 3 else [])
    w2 = 160 * blurico.SCALE
    size = (160, round(0.864 * 160))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for bodies, colour in ((dim, dim_colour), (lit, lit_colour)):
        if not bodies:
            continue
        mask = blurico._mask(sheet, bodies, w2, 0.864).resize(size, Image.LANCZOS)
        layer = Image.new("RGBA", size, colour + (0,))
        layer.putalpha(mask)
        out.alpha_composite(layer)
    return out.resize((round(out.width * height / out.height), height), Image.LANCZOS)


def padlock(size):
    """the red padlock of a locked event, drawn at 4 x the size and reduced"""
    k = 4
    im = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    red, dark = (255, 70, 84, 255), (120, 20, 36, 255)
    w = size * k
    d.arc([w * 0.22, w * 0.06, w * 0.78, w * 0.62], 180, 360, fill=red, width=int(w * 0.1))
    d.line([(w * 0.25, w * 0.34), (w * 0.25, w * 0.5)], fill=red, width=int(w * 0.1))
    d.line([(w * 0.75, w * 0.34), (w * 0.75, w * 0.5)], fill=red, width=int(w * 0.1))
    d.rounded_rectangle([w * 0.12, w * 0.44, w * 0.88, w * 0.94], radius=int(w * 0.1), fill=red)
    d.ellipse([w * 0.43, w * 0.55, w * 0.57, w * 0.69], fill=dark)
    d.rectangle([w * 0.47, w * 0.64, w * 0.53, w * 0.8], fill=dark)
    return im.resize((size, size), Image.LANCZOS)


def main():
    pak = blurico.find_root_pak(sys.argv[1:])
    if not pak:
        raise SystemExit("root.pak not found; pass the game folder as an argument")
    icons = blurico.Icons(pak)
    p = blurpak.Pak(pak)
    try:
        sheet = p.read(CLASS_SHEET)
    finally:
        p.close()
    status = {"new": alert_icon(sheet), "new_small": alert_icon(sheet, LIST_PAD_Y + 8)}
    p = blurpak.Pak(pak)
    try:
        bundle = blurbpr.pictures(p.read(BUNDLE))
    finally:
        p.close()
    logos = {}
    for pic, (fmt, w, h, data) in bundle.items():
        if pic.startswith("man_") and pic[4:] in USED:
            im = blurbpr.decode(fmt, w, h, data)
            box = im.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()     # cut the empty border
            im = im.crop(box)
            k = min(LOGO_BOX[0] / im.width, LOGO_BOX[1] / im.height)
            logos[pic[4:]] = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    p = blurpak.Pak(pak)
    try:
        header = header_images(p.read(COMMON), sheet)
    finally:
        p.close()
    p = blurpak.Pak(pak)
    try:
        events = event_images(p.read(COMMON), pak, sheet)
    finally:
        p.close()
    shapes = blurico.shapes(sheet)
    badges = {c: blurico.render(sheet, shapes["class_" + c.lower()], CLASS_WIDTH, color=(24, 110, 235), glyph=(205, 240, 255))
              for c in "ABCD"}
    n = 0
    smalls = {}
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted({v["name"] for v in bs.load_vehicles().values()}):
            im = icons.car(name, CAR_WIDTH)
            if im is None:
                print("no icon:", name)
                continue
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            z.writestr("cars/%s.png" % name, buf.getvalue())
            n += 1
            smalls[name] = (icons.car(name, LIST_W), icons.cars.get(name, LIST_W, color=LOCKED_GREY))   # normal and greyed out
        tile_h = max(im.height for im, _ in smalls.values()) + LIST_PAD_Y      # the tallest car fits; all tiles have the same size
        for name, (small, grey) in smalls.items():
            for kind in ("seen", "new", "locked"):          # "new": with the triangle at the top left; "locked": grey
                small = grey if kind == "locked" else small
                tile = Image.new("RGBA", (LIST_W + LIST_PAD_X, tile_h), (0, 0, 0, 0))
                x = (tile.width - small.width) // 2                           # centred (the editor shifts cars that show a paint hexagon)
                tile.paste(small, (x, tile_h - small.height), small)                     # on one ground line
                if kind == "new":
                    tile.alpha_composite(status["new_small"], (0, 0))
                buf = io.BytesIO()
                tile.save(buf, "PNG", optimize=True)
                z.writestr("%s/%s.png" % (kind, name), buf.getvalue())
        for name, im in events.items():
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            z.writestr("events/%s.png" % name, buf.getvalue())
        for name, im in header.items():
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            z.writestr("header/%s.png" % name, buf.getvalue())
        for name, im in logos.items():
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            z.writestr("logos/%s.png" % name, buf.getvalue())
        for c, badge in badges.items():
            buf = io.BytesIO()
            badge.save(buf, "PNG", optimize=True)
            z.writestr("classes/%s.png" % c, buf.getvalue())
        for s, im in status.items():
            if s == "new_small":
                continue
            buf = io.BytesIO()
            im.save(buf, "PNG", optimize=True)
            z.writestr("status/%s.png" % s, buf.getvalue())
        for m in blurico.MOD_SHAPES:
            im = icons.mod(m, MOD_WIDTH)
            if im is not None:
                buf = io.BytesIO()
                im.save(buf, "PNG", optimize=True)
                z.writestr("mods/%s.png" % m, buf.getvalue())
    print("%d car icons + mod icons -> %s (%d bytes)" % (n, OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
