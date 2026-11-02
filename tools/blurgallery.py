"""A gallery of pictures grouped in rows with a label (the cars by class): the group's picture on the left, the items next to it
and wrapped when the window is narrow. Click selects (Ctrl toggles, Shift selects a range), the arrow keys move; the selected
items get a frame. A change sends the virtual event <<TreeviewSelect>>. Each item is a picture with its name below it.
"""
import tkinter as tk
from tkinter import ttk

import blurtheme as theme
from blurpicker import hex_image

LABEL_W = 96
GAP = 6
PAINT_EDGE = "#2b8cff"            # outline of the paint hexagon
DIM = "#4f5f8e"                   # text of items that are greyed out


class Gallery(ttk.Frame):
    def __init__(self, master, cell_size, height=260):
        """cell_size: (width, height) of one item"""
        super().__init__(master)
        self.cw, self.ch = cell_size
        self.groups = []                    # [(label picture or text, [(id, picture, name, dimmed)])]
        self.font = (theme.fonts["small"][0], 9, "bold")
        self._order = []                    # ids in reading order
        self._sel = []
        self._last = None
        self._col = None                    # column kept while moving up and down
        self._boxes = []                    # [(x0, y0, x1, y1, id)]
        self._width = 0
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.cv = tk.Canvas(self, bg=theme.FIELD, highlightthickness=1, highlightbackground=theme.EDGE,
                            highlightcolor=theme.EDGE, takefocus=1, height=height)
        self.sb = ttk.Scrollbar(self, command=self.cv.yview)
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.grid(row=0, column=0, sticky="nsew")
        self.sb.grid(row=0, column=1, sticky="ns")
        self.cv.bind("<Configure>", self._configure)
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Control-Button-1>", lambda e: self._click(e, ctrl=True))
        self.cv.bind("<Shift-Button-1>", lambda e: self._click(e, shift=True))
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        for key, d in (("Left", -1), ("Right", 1), ("Up", -1), ("Down", 1)):
            self.cv.bind("<%s>" % key, lambda e, d=d, k=key: self._step(d, k in ("Up", "Down")))
        self.cv.bind("<Control-a>", self._all)
        self.cv.bind("<Escape>", lambda e: (self._select([]), "break")[1])

    # ---------- contents ----------
    def set_groups(self, groups):
        """groups: [(label, [(id, picture, name, dimmed[, paint colour[, dx]]), ...]), ...]; label is a picture or a string; a
        paint colour ("#rrggbb") puts the small colour hexagon of the game's car carousel left of the picture; dx moves the picture
        to the right"""
        self.groups = list(groups)
        self._order = [it[0] for _, items in self.groups for it in items]
        self._sel = [i for i in self._sel if i in self._order]
        self._draw()

    def _configure(self, e):
        if e.width != self._width:
            self._width = e.width
            self._draw()

    def _per_row(self):
        return max(1, (self._width - LABEL_W - 24) // (self.cw + GAP))

    def _draw(self):
        c = self.cv
        c.delete("all")
        self._boxes = []
        per = self._per_row()
        y = 8
        for label, items in self.groups:
            lines = max(1, -(-len(items) // per))
            if isinstance(label, tk.PhotoImage):
                c.create_image(LABEL_W // 2 + 6, y + self.ch // 2, image=label)
            else:
                c.create_text(LABEL_W // 2 + 6, y + self.ch // 2, text=label, fill=theme.FG, font=theme.fonts["title"])
            for n, (iid, pic, name, dim, *paint) in enumerate(items):
                dx = paint[1] if len(paint) > 1 else 0
                x0 = LABEL_W + 12 + (n % per) * (self.cw + GAP)
                y0 = y + (n // per) * (self.ch + GAP)
                self._boxes.append((x0, y0, x0 + self.cw, y0 + self.ch, iid))
                if iid in self._sel:
                    c.create_rectangle(x0, y0, x0 + self.cw, y0 + self.ch, outline=theme.CYAN, fill="#14306f")
                top = y0 + 4
                if pic:
                    if paint and paint[0]:
                        hx, hy = x0 + 11, top + pic.height() - 20          # beside the silhouette, which stands on the bottom line of the picture
                        c.create_image(hx, hy, image=hex_image(((PAINT_EDGE, 10), (paint[0], 7.5))))
                    c.create_image(x0 + self.cw // 2 + dx, top, image=pic, anchor="n")
                    top += pic.height() + 2
                c.create_text(x0 + self.cw // 2, top, text=name, width=self.cw - 8, anchor="n", justify="center",
                              fill=DIM if dim else "#e8eeff", font=self.font)
            y += lines * (self.ch + GAP) + 10
            c.create_line(8, y - 6, max(self._width - 8, 8), y - 6, fill=theme.TOPBAR)
        c.configure(scrollregion=(0, 0, max(self._width, 10), y))

    # ---------- selection (the names follow ttk.Treeview) ----------
    def selection(self):
        return tuple(i for i in self._order if i in self._sel)

    def exists(self, iid):
        return iid in self._order

    def get_children(self):
        return tuple(self._order)

    def selection_set(self, *ids):
        self._select([i for i in ids if i in self._order])

    def selection_add(self, *ids):
        self._select(list(self._sel) + [i for i in ids if i in self._order and i not in self._sel])

    def see(self, iid):
        box = next((b for b in self._boxes if b[4] == iid), None)
        if not box:
            return
        h = int(float(self.cv.cget("scrollregion").split()[3])) if self.cv.cget("scrollregion") else 1
        top, bottom = self.cv.canvasy(0), self.cv.canvasy(self.cv.winfo_height())
        if box[1] < top:
            self.cv.yview_moveto(max(0, (box[1] - 8) / h))
        elif box[3] > bottom:
            self.cv.yview_moveto(max(0, (box[3] + 8 - self.cv.winfo_height()) / h))

    def _select(self, ids):
        if list(ids) == self._sel:
            return
        self._sel = list(ids)
        self._draw()
        self.event_generate("<<TreeviewSelect>>")

    def _at(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        return next((b[4] for b in self._boxes if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)

    def _click(self, e, ctrl=False, shift=False):
        self.cv.focus_set()
        iid = self._at(e)
        if iid is None:                                       # an empty spot: nothing chosen
            if not (ctrl or shift):
                self._last = None
                self._select([])
            return "break"
        n = self._order.index(iid)
        if shift and self._last is not None:
            a, z = sorted((self._last, n))
            self._select(self._order[a:z + 1])
        elif ctrl:
            self._select([i for i in self._sel if i != iid] if iid in self._sel else self._sel + [iid])
            self._last, self._col = n, None
        else:
            self._select([iid])
            self._last, self._col = n, None
        return "break"

    def _rows(self):
        """the visual rows, group after group: [[ids of one line], ...]"""
        per = self._per_row()
        rows = []
        for _, items in self.groups:
            ids = [it[0] for it in items]
            rows += [ids[i:i + per] for i in range(0, len(ids), per)]
        return rows

    def _step(self, d, vertical):
        if not self._order:
            return "break"
        if self._last is None:
            n = 0
        elif vertical:                                        # one line up or down, also over a class border: same column (as far as there is one)
            rows = self._rows()
            cur = self._order[self._last]
            r = next(i for i, row in enumerate(rows) if cur in row)
            if self._col is None:
                self._col = rows[r].index(cur)
            r = max(0, min(len(rows) - 1, r + d))
            n = self._order.index(rows[r][min(self._col, len(rows[r]) - 1)])
        else:
            n = max(0, min(len(self._order) - 1, self._last + d))
            self._col = None
        self._last = n
        self._select([self._order[n]])
        self.see(self._order[n])
        return "break"

    def _all(self, e):
        self._select(list(self._order))
        return "break"
