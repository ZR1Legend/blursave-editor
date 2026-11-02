"""The event cards of the game's Career menu: above each card the white landmark of the city and the city's name, in the card the icon and
the name of the kind of event (Race, Destruction, Checkpoint, One-on-One) and a row of light coins (lit or dark), followed by the two
round icons of the fan target and the fan run. The cards are arranged in columns and scrolled with the mouse wheel; a click or the arrow
keys choose one (the widget sends <<TreeviewSelect>> like the table it replaces: selection(), selection_set(), get_children()).

The rounded cards are small smoothed pictures (distance to the rounded rectangle -> coverage), made in pure Python.
"""
import base64
import math
import tkinter as tk
from tkinter import ttk

import blurtheme as theme
from blurpicker import _png

CARD_W, CARD_H, HEAD_H, GAP_X, GAP_Y = 350, 70, 46, 16, 8
RADIUS = 14
COIN = 30
_cards = {}


def card_image(w, h, top, bottom, edge, edge_w=2.0, r=RADIUS):
    """RGBA picture of a rounded rectangle: vertical gradient from top to bottom, outline of the colour `edge`"""
    key = (w, h, top, bottom, edge, edge_w, r)
    if key not in _cards:
        t = [int(top[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(bottom[i:i + 2], 16) for i in (1, 3, 5)]
        e = [int(edge[i:i + 2], 16) for i in (1, 3, 5)]
        cx, cy = w / 2, h / 2
        rows = []
        for py in range(h):
            f = py / max(1, h - 1)
            fill = [t[i] + (b[i] - t[i]) * f for i in range(3)]
            qy = abs(py + 0.5 - cy) - (cy - r)
            row = []
            for px in range(w):
                qx = abs(px + 0.5 - cx) - (cx - r)
                d = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r
                a_o = min(1.0, max(0.0, 0.5 - d))
                a_i = min(1.0, max(0.0, 0.5 - (d + edge_w)))
                a = a_i + a_o * (1 - a_i)
                if a <= 0:
                    row += [0, 0, 0, 0]
                    continue
                col = [(fill[i] * a_i + e[i] * a_o * (1 - a_i)) / a for i in range(3)]
                row += [round(c) for c in col] + [round(a * 255)]
            rows.append(row)
        _cards[key] = tk.PhotoImage(data=base64.b64encode(_png(w, h, rows)))
    return _cards[key]


class EventCards(ttk.Frame):
    def __init__(self, master, icon, height=330):
        """icon(name) -> tk.PhotoImage or None, for the pictures "events/<name>" of the icon file"""
        super().__init__(master)
        self.icon = icon
        self.empty = ""
        self.items = []                       # [dict(iid, city, landmark, kind, status, locked, coins, coins_max, fan, run)]
        self._sel = None
        self._boxes = []
        self._width = 0
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.cv = tk.Canvas(self, bg=theme.FIELD, highlightthickness=1, highlightbackground=theme.EDGE, highlightcolor=theme.EDGE,
                            takefocus=1, height=height)
        self.sb = ttk.Scrollbar(self, command=self.cv.yview)
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.grid(row=0, column=0, sticky="nsew")
        self.sb.grid(row=0, column=1, sticky="ns")
        self.cv.bind("<Configure>", self._configure)
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        for key, d in (("Left", -1), ("Right", 1)):
            self.cv.bind("<%s>" % key, lambda e, d=d: self._step(d))
        for key, d in (("Up", -1), ("Down", 1)):
            self.cv.bind("<%s>" % key, lambda e, d=d: self._step(d * self._columns()))

    # ---------- contents ----------
    def set_items(self, items, empty=""):
        """empty: the text shown when there are no events"""
        self.items = list(items)
        self.empty = empty
        if self._sel not in [i["iid"] for i in self.items]:
            self._sel = None
        self._draw()

    def _configure(self, e):
        if e.width != self._width:
            self._width = e.width
            self._draw()

    def _columns(self):
        return max(1, (self._width - 24 + GAP_X) // (CARD_W + GAP_X))

    def _draw(self):
        c = self.cv
        c.delete("all")
        self._boxes = []
        cols = self._columns()
        font_city = (theme.fonts["title"][0], 12, "bold")
        font_kind = (theme.fonts["title"][0], 16, "bold")
        font_small = theme.fonts["small"]
        font_num = (theme.fonts["title"][0], 40, "bold")
        if not self.items and self.empty:
            c.create_text(20, 20, text=self.empty, anchor="nw", fill=theme.MUTED, font=theme.fonts["body"], width=max(200, self._width - 40))
        for n, it in enumerate(self.items):
            x0 = 12 + (n % cols) * (CARD_W + GAP_X)
            y0 = 10 + (n // cols) * (HEAD_H + CARD_H + GAP_Y)
            sel = it["iid"] == self._sel
            locked = it.get("locked")
            # colours as in the game: the chosen card is bright with white text, the others are dark blue with blue text, a locked one is
            # grey glass with silver coins and a red padlock
            if locked and sel:
                look = ("#a3aec8", "#66728f", "#e6edfa", "#eef3fc", "#d7deec", "typelock_")
            elif locked:                                             # a locked event that is not chosen is dark
                look = ("#3b4359", "#272e42", "#586279", "#8b94ab", "#7a839a", "typelockdim_")
            elif sel:
                look = ("#2f8aff", "#0f48d0", "#7fe0ff", "#ffffff", "#ffffff", "type_")
            else:
                look = ("#102f86", "#081f5e", "#2468dc", "#3f86ff", "#5b9bff", "typedim_")
            top, bottom, edge, ink, head_ink, tag = look
            lm = self.icon("lm_" + it["landmark"])
            tx = x0 + 6
            if lm:
                c.create_image(x0 + 6, y0 + HEAD_H // 2, image=lm, anchor="w")
                tx += lm.width() + 8
            c.create_text(tx, y0 + HEAD_H // 2, text=it["city"], anchor="w", fill=head_ink, font=font_city)
            mk = self.icon("diff_%d" % it["diff"]) if it.get("diff") in (1, 2, 3) else None    # the difficulty, on every card (none: no symbol)
            if mk:
                c.create_image(x0 + CARD_W - 8, y0 + HEAD_H // 2, image=mk, anchor="e")
            cy0 = y0 + HEAD_H
            img = card_image(CARD_W, CARD_H, top, bottom, edge, 3.0 if sel else 2.0)
            c.create_image(x0, cy0, image=img, anchor="nw")
            if sel:                                                  # the bright lower edge of the chosen card
                c.create_line(x0 + 22, cy0 + CARD_H - 3, x0 + CARD_W - 22, cy0 + CARD_H - 3, fill="#c9f1ff", width=3)
            if it.get("number"):                                     # the big number of the event, faint
                c.create_text(x0 + CARD_W - 24, cy0 + CARD_H // 2 + 2, text=str(it["number"]), anchor="e", font=font_num,
                              fill=("#9aa6c2" if sel else "#4a5573") if locked else ("#3b8bff" if sel else "#123a9a"))
            ti = self.icon(tag + it["kind"])
            kx = x0 + 14
            if ti:
                c.create_image(kx, cy0 + 21, image=ti, anchor="w")
                kx += ti.width() + 10
            c.create_text(kx, cy0 + 21, text=it["kind"], anchor="w", fill=ink, font=font_kind)
            if it.get("status"):
                c.create_text(x0 + CARD_W - 14, cy0 + 12, text=it["status"], anchor="e", fill="#c7d6f5" if (sel or locked) else theme.MUTED,
                              font=font_small)
            x = x0 + 14
            y = cy0 + 37
            off = self.icon("coin_off")
            lit = (self.icon("coin_lock") if sel else self.icon("coin_lockdim")) if locked else self.icon("coin_%d" % it.get("place", 3))
            for k in range(it["coins_max"]):
                im = lit if (locked or k < it["coins"]) else off
                if im:
                    c.create_image(x, y, image=im, anchor="nw")
                x += COIN + 4
            if it["coins_max"] < 8:                                  # the fan target and the fan run (not for the One-on-One)
                x += 12
                for name, on in (("fan", it["fan"]), ("run", it["run"])):
                    if locked:
                        im = self.icon("%s_%s" % (name, "lock" if sel else "lockdim"))
                    else:
                        im = self.icon("%s_%s" % (name, "on" if on else "off"))
                    if im:
                        c.create_image(x, y, image=im, anchor="nw")
                    x += COIN + 4
            corner = self.icon("lock") if locked else (self.icon("new", "status") if it.get("new") else None)
            if corner:                                               # red padlock (locked) or the green triangle (not played yet)
                c.create_image(x0 + CARD_W - 18, cy0 + CARD_H - 22, image=corner, anchor="e")
            self._boxes.append((x0, y0, x0 + CARD_W, cy0 + CARD_H, it["iid"]))
        rows = -(-len(self.items) // cols)
        c.configure(scrollregion=(0, 0, max(self._width, 10), 10 + rows * (HEAD_H + CARD_H + GAP_Y)))

    # ---------- selection (the names follow ttk.Treeview) ----------
    def selection(self):
        return (self._sel,) if self._sel else ()

    def get_children(self):
        return tuple(i["iid"] for i in self.items)

    def selection_set(self, *ids):
        self._select(ids[0] if ids else None)

    def _select(self, iid):
        if iid == self._sel:
            return
        self._sel = iid
        self._draw()
        self.event_generate("<<TreeviewSelect>>")

    def see(self, iid):
        box = next((b for b in self._boxes if b[4] == iid), None)
        if not box:
            return
        region = self.cv.cget("scrollregion").split()
        h = int(float(region[3])) if region else 1
        top, bottom = self.cv.canvasy(0), self.cv.canvasy(self.cv.winfo_height())
        if box[1] < top:
            self.cv.yview_moveto(max(0, (box[1] - 8) / h))
        elif box[3] > bottom:
            self.cv.yview_moveto(max(0, (box[3] + 8 - self.cv.winfo_height()) / h))

    def _click(self, e):
        self.cv.focus_set()
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        iid = next((b[4] for b in self._boxes if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)
        if iid:
            self._select(iid)
        return "break"

    def _step(self, d):
        ids = self.get_children()
        if not ids:
            return "break"
        n = 0 if self._sel is None else max(0, min(len(ids) - 1, ids.index(self._sel) + d))
        self._select(ids[n])
        self.see(ids[n])
        return "break"
