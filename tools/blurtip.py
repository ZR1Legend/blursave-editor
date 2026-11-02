"""A small info symbol (a smoothed blue circle with a white "i") and a tooltip that shows a text while the mouse is over a widget."""
import base64
import tkinter as tk

import blurtheme as theme
from blurpicker import _png

_icons = {}


def info_image(size=18, fill="#2b8cff", glyph="#ffffff"):
    """RGBA picture of the info symbol; 4 x 4 sub-pixels per pixel"""
    key = (size, fill, glyph)
    if key not in _icons:
        sub = 4
        c = size / 2
        f = [int(fill[i:i + 2], 16) for i in (1, 3, 5)]
        g = [int(glyph[i:i + 2], 16) for i in (1, 3, 5)]
        dot_r, stem_w = size * 0.09, size * 0.13
        rows = []
        for py in range(size):
            row = []
            for px in range(size):
                n = ring = mark = 0
                for sy in range(sub):
                    y = py + (sy + 0.5) / sub - c
                    for sx in range(sub):
                        x = px + (sx + 0.5) / sub - c
                        if x * x + y * y <= (size / 2 - 0.5) ** 2:
                            n += 1
                            in_dot = x * x + (y + size * 0.22) ** 2 <= dot_r * dot_r
                            in_stem = abs(x) <= stem_w / 2 and -size * 0.1 <= y <= size * 0.26
                            if in_dot or in_stem:
                                mark += 1
                a = n / (sub * sub)
                m = mark / n if n else 0
                col = [round(f[i] * (1 - m) + g[i] * m) for i in range(3)]
                row += col + [round(a * 255)]
            rows.append(row)
        _icons[key] = tk.PhotoImage(data=base64.b64encode(_png(size, size, rows)))
    return _icons[key]


class Tooltip:
    """text in a small window next to the mouse while it is over the widget"""

    def __init__(self, widget, text, delay=350):
        self.widget, self.text, self.delay = widget, text, delay
        self.win = self.after_id = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, e):
        self._leave()
        self.after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        x, y = self.widget.winfo_pointerx() + 14, self.widget.winfo_pointery() + 18
        self.win = tk.Toplevel(self.widget)
        self.win.wm_overrideredirect(True)
        self.win.wm_geometry("+%d+%d" % (x, y))
        tk.Label(self.win, text=self.text, bg=theme.FIELD, fg=theme.FG, relief="solid", borderwidth=1, justify="left",
                 wraplength=320, padx=8, pady=5, font=theme.fonts["small"]).pack()

    def _leave(self, e=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.win:
            self.win.destroy()
            self.win = None
