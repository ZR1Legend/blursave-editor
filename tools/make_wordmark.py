"""Builds the wordmark "blursave editor" from the game's "blur" logo (blur_logo in ui_common.bpr, white with alpha, 128 x 64).

Development tool (needs PIL). The letters b, l, u, r are the game's own pixels; the new letters s, a, v, e, d, i, t, o are drawn in the
logo's style: heavy strokes of one width, flat-cut ends, round bowls (the "d" is the mirrored "b"; "a" is a "d" cut at the x-height).
Measures of the logo in its own pixels: ascender top 8, x-height top 19.7, baseline 56, stem width 12.25, letter gap about 2.2.
"""
import math

from PIL import Image, ImageDraw

SS = 8                                      # sub-pixels per pixel for the drawn letters
TOP, XH, BASE = 8.0, 19.7, 56.0
STEM = 12.25
H = BASE - XH                               # x-height, 36.3
GAP = 2.4
SPACE = 15.0
BAR = 9.5                                   # thickness of the horizontal strokes of s and e


class Canvas:
    def __init__(self, w, h):
        self.im = Image.new("L", (int(w * SS), int(h * SS)), 0)
        self.d = ImageDraw.Draw(self.im)

    def poly(self, pts, fill=255):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)

    def rect(self, x0, y0, x1, y1, fill=255):
        self.d.rectangle([x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1], fill=fill)

    def disc(self, cx, cy, r, fill=255):
        self.d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS - 1, (cy + r) * SS - 1], fill=fill)

    def stroke(self, pts, width, fill=255):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=int(round(width * SS)), joint="curve")

    def downsample(self):
        return self.im.resize((self.im.width // SS, self.im.height // SS), Image.BOX)


def arc(cx, cy, r, a0, a1, n=48):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def glyph_o(c, x):
    r = H / 2
    c.disc(x + r, XH + r, r)
    c.disc(x + r, XH + r, r - STEM, 0)
    return x + H


def glyph_e(c, x):
    """a ring (a little higher and wider than the x-height, like the round letters of the user's drawing) with a rounded slot above
    a thin crossbar and a thin slit below it that runs out to the right. Measures from the drawing, in logo pixels: ring top 0.8
    above the x-height; strokes top 10.2, slot 6.5 (14 wide), bar 5.4, slit 4.3 (starts 5.8 left of the centre)"""
    r = H / 2 + 0.4
    top = XH - 0.8
    cx, cy = x + H / 2, top + r
    c.disc(cx, cy, r)
    y0 = top + 10.2
    slot, half, cr = 6.5, 7.0, 2.8                              # the slot is a rounded rectangle, the slit has a round left end
    sx0, sx1 = cx + 0.6 - half, cx + 0.6 + half
    c.rect(sx0 + cr, y0, sx1 - cr, y0 + slot, 0)
    c.rect(sx0, y0 + cr, sx1, y0 + slot - cr, 0)
    for qx in (sx0 + cr, sx1 - cr):
        for qy in (y0 + cr, y0 + slot - cr):
            c.disc(qx, qy, cr, 0)
    y1 = y0 + slot + 5.4
    slit = 4.3
    c.disc(cx - 5.8 + slit / 2, y1 + slit / 2, slit / 2, 0)
    c.rect(cx - 5.8 + slit / 2, y1, cx + r + 2, y1 + slit, 0)
    return x + H


def glyph_s(c, x):
    """three horizontal bars joined by two half rings (upper left, lower right); the top is 0.8 above the x-height and the middle bar
    is a little thicker, as in the user's drawing"""
    w = H - 3.5
    t0, b1 = XH - 0.8, XH + 8.8                               # top bar
    m0, m1 = XH + 12.5, XH + 22.25                            # middle bar
    g0 = XH + 26.9                                            # top of the bottom bar
    r1o, r1i = (m1 - t0) / 2, (m0 - b1) / 2                   # upper left ring: outer and inner radius
    r2o, r2i = (BASE - m0) / 2, (g0 - m1) / 2                 # lower right ring
    xl, xr = x, x + w
    cxl, cyl = xl + r1o, (t0 + m1) / 2
    cxr, cyr = xr - r2o, (m0 + BASE) / 2
    c.poly(arc(cxl, cyl, r1o, 90, 270) + arc(cxl, cyl, r1i, 270, 90))
    c.poly(arc(cxr, cyr, r2o, -90, 90) + arc(cxr, cyr, r2i, 90, -90))
    c.rect(cxl, t0, xr, b1)
    c.rect(cxl, m0, cxr, m1)
    c.rect(xl, g0, cxr, BASE)
    return x + w


def glyph_v(c, x):
    w = H + 2.5
    c.poly([(x, XH), (x + 13.2, XH), (x + w / 2, BASE - 17.0), (x + w - 13.2, XH), (x + w, XH), (x + w / 2 + 6.6, BASE), (x + w / 2 - 6.6, BASE)])
    return x + w


def glyph_i(c, x):
    c.rect(x, XH, x + STEM, BASE)
    c.rect(x, TOP, x + STEM, TOP + 9.0)
    return x + STEM


def glyph_t(c, x):
    c.rect(x + 5.0, 12.0, x + 5.0 + STEM, BASE)
    c.rect(x, XH, x + 5.0 + STEM + 7.0, XH + 8.5)
    return x + 5.0 + STEM + 7.0


def build(alpha, extra=(("s", "a", "v", "e"), ("e", "d", "i", "t", "o", "r"))):
    """alpha: the 128 x 64 alpha channel of blur_logo; returns an "L" picture of the wordmark, cropped"""
    src = alpha.load()
    box_b = alpha.crop((4, 0, 45, 64))                   # b (x 4..44)
    box_r = alpha.crop((100, 0, 119, 64))                # r (x 100..118)
    d_img = box_b.transpose(Image.FLIP_LEFT_RIGHT)       # d
    width = 520
    out = Image.new("L", (width, 64), 0)
    out.paste(alpha.crop((0, 0, 119, 64)), (0, 0))
    x = 119 + GAP
    cv = Canvas(width, 64)
    placed = []

    def paste_img(img, x):
        out.paste(img, (int(round(x)), 0), img)
        return x + img.width

    def a_glyph(x):
        # "a" = the "d" cut at the x-height
        img = d_img.copy()
        ImageDraw.Draw(img).rectangle([0, 0, img.width, int(XH) - 1], fill=0)
        row = int(XH)
        frac = int(round((1 - (XH - row)) * 255))
        for xx in range(img.width):
            v = d_img.getpixel((xx, row))
            img.putpixel((xx, row), v * frac // 255)
        return img

    for wi, word in enumerate(extra):
        for ch in word:
            if ch == "d":
                x = paste_img(d_img, x) + GAP
            elif ch == "a":
                x = paste_img(a_glyph(x), x) + GAP
            elif ch == "r":
                x = paste_img(box_r, x) + GAP
            else:
                x = {"s": glyph_s, "e": glyph_e, "v": glyph_v, "i": glyph_i, "t": glyph_t, "o": glyph_o}[ch](cv, x) + GAP
        if wi < len(extra) - 1:
            x += SPACE - GAP
    small = cv.downsample()
    out.paste(small, (0, 0), small)
    out = out.crop(out.getbbox())
    return out
