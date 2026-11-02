"""The colour picker of the game's respray menu, drawn in the editor: a hexagon of 37 cells (rows of 4, 5, 6, 7, 6, 5, 4), above it the four
brightness levels of the chosen cell (black, dark, medium, bright). Click a cell or a brightness level; the choice is kept in three
tk.StringVars (row, column and brightness) so that the rest of the editor can read and set it.

The hexagons are small smoothed pictures (a Tk canvas draws polygons without anti-aliasing): `hex_image` builds them with 4 x 4
sub-pixels per pixel and a PNG with an alpha channel, in pure Python (no PIL in the editor).
"""
import base64
import math
import struct
import tkinter as tk
import zlib

import blurtheme as theme

ROWS = (4, 5, 6, 7, 6, 5, 4)
RADIUS = 14
WIDTH, HEIGHT = 214, 212
EDGE = "#2b8cff"                       # blue outline of the game's cells
SELECT = "#ffffff"
SUB = 4                                # sub-pixels per pixel and axis

_masks = {}
_images = {}


def dim(colour, f=0.28):
    """the colour towards the background, for what the chosen finish does not offer"""
    bg = [int(theme.BG[i:i + 2], 16) for i in (1, 3, 5)]
    c = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(b + (x - b) * f) for b, x in zip(bg, c))


def _mask(r, size):
    """coverage 0..1 of a pointy-top hexagon of circumradius r in each pixel of a size x size picture"""
    key = (r, size)
    if key not in _masks:
        a = r * math.sqrt(3) / 2                                    # distance of the edges from the centre
        normals = [(math.cos(math.radians(t)), math.sin(math.radians(t))) for t in (0, 60, 120)]
        c = size / 2
        rows = []
        for py in range(size):
            row = []
            for px in range(size):
                n = 0
                for sy in range(SUB):
                    y = py + (sy + 0.5) / SUB - c
                    for sx in range(SUB):
                        x = px + (sx + 0.5) / SUB - c
                        if all(abs(x * nx + y * ny) <= a for nx, ny in normals):
                            n += 1
                row.append(n / (SUB * SUB))
            rows.append(row)
        _masks[key] = rows
    return _masks[key]


def _rgb(colour):
    return [int(colour[i:i + 2], 16) for i in (1, 3, 5)]


def _png(w, h, rows):
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def hex_image(layers):
    """smoothed hexagon picture with a transparent background; layers = ((colour, radius), ...), the outermost first, each laid
    over the one before it (outline, then fill). The picture is cached."""
    layers = tuple(layers)
    if layers not in _images:
        size = 2 * (math.ceil(max(r for _, r in layers)) + 1)
        masks = [(_rgb(c), _mask(r, size)) for c, r in layers]
        rows = []
        for py in range(size):
            row = []
            for px in range(size):
                rr = gg = bb = aa = 0.0                              # premultiplied, composed layer by layer
                for (cr, cg, cb), m in masks:
                    a = m[py][px]
                    if a:
                        rr, gg, bb, aa = cr * a + rr * (1 - a), cg * a + gg * (1 - a), cb * a + bb * (1 - a), a + aa * (1 - a)
                if aa:
                    row += [round(rr / aa), round(gg / aa), round(bb / aa), round(aa * 255)]
                else:
                    row += [0, 0, 0, 0]
            rows.append(row)
        _images[layers] = tk.PhotoImage(data=base64.b64encode(_png(size, size, rows)))
    return _images[layers]


class PaintPicker(tk.Canvas):
    def __init__(self, master, level_var, row_var, col_var, levels, colour, available):
        """levels: the texts of level_var for brightness 1 to 4; colour(row, column, level) -> "#rrggbb";
        available(row, column, level) -> False for what the chosen finish does not have"""
        super().__init__(master, width=WIDTH, height=HEIGHT, bg=theme.BG, highlightthickness=0, takefocus=0)
        self.level_var, self.row_var, self.col_var = level_var, row_var, col_var
        self.levels, self.colour, self.available = levels, colour, available
        self._cells, self._swatches = [], []
        for v in (level_var, row_var, col_var):
            v.trace_add("write", lambda *a: self.draw())
        self.bind("<Button-1>", self._click)
        self.draw()

    def refresh(self):
        self.draw()

    def _state(self):
        try:
            return int(self.row_var.get()), int(self.col_var.get()), self.levels.index(self.level_var.get()) + 1
        except ValueError:
            return None

    def draw(self):
        self.delete("all")
        self._cells, self._swatches = [], []
        st = self._state()
        if st is None:
            return
        row, col, level = st
        r = RADIUS
        # the four brightness levels of the chosen cell
        for k in range(4):
            cx, cy = WIDTH / 2 + (k - 1.5) * 32, 20
            ok = self.available(row, col, k + 1)
            fill = self.colour(row, col, k + 1)
            edge = EDGE
            if not ok:
                fill, edge = dim(fill), dim(edge)
            if k + 1 == level:
                img = hex_image(((edge, 16), (SELECT, 14), (fill, 12)))
            else:
                img = hex_image(((edge, 13), (fill, 10.5)))
            self.create_image(cx, cy, image=img)
            self._swatches.append((cx - 14, cy - 15, cx + 14, cy + 15, k + 1))
        # the hexagon of cells
        w = math.sqrt(3) * r
        top = 62
        sel = None
        for i, n in enumerate(ROWS):
            for j in range(n):
                cx = WIDTH / 2 + (j - (n - 1) / 2) * (w + 1)
                cy = top + i * (1.5 * r + 1)
                ok = self.available(i + 1, j + 1, 4)
                fill = self.colour(i + 1, j + 1, 4)
                edge = EDGE
                if not ok:
                    fill, edge = dim(fill), dim(edge)
                self.create_image(cx, cy, image=hex_image(((edge, r + 0.5), (fill, r - 1.5))))
                self._cells.append((cx, cy, i + 1, j + 1, ok))
                if (i + 1, j + 1) == (row, col):
                    sel = (cx, cy)
        if sel:                                                    # the chosen cell is drawn larger, with a white frame
            self.create_image(sel[0], sel[1], image=hex_image(((SELECT, r + 3), (self.colour(row, col, 4), r + 1))))

    def _click(self, e):
        for x0, y0, x1, y1, level in self._swatches:
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                st = self._state()
                if st and self.available(st[0], st[1], level):
                    self.level_var.set(self.levels[level - 1])
                return
        best = min(self._cells, key=lambda c: (c[0] - e.x) ** 2 + (c[1] - e.y) ** 2, default=None)
        if best and (best[0] - e.x) ** 2 + (best[1] - e.y) ** 2 <= (RADIUS * 0.95) ** 2 and best[4]:
            self.row_var.set(str(best[2]))
            self.col_var.set(str(best[3]))
