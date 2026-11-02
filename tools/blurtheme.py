"""The game's look for the editor: night-blue background, glowing blue panels, orange numbers, rounded white headings.
Colours were taken from screenshots of the game's menus (career screen, event list, mod loadout); no game file is used or
shipped. Fonts are looked for on the system (the game's own font is not used); the first one that exists wins."""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#0a1030"          # night blue (the game's menu background)
PANEL = "#0e1a4d"
FIELD = "#08102e"
EDGE = "#1852bf"        # panel blue of the game
BLUE = "#1852bf"
BLUE_HI = "#2f7bff"
CYAN = "#17baff"        # selection glow
TOPBAR = "#0e2f77"      # the bar at the top of every menu
FG = "#eef4ff"
MUTED = "#8fa6d8"
ORANGE = "#ffc66b"      # numbers and descriptions
ORANGE_DK = "#ff9d1c"
GREEN = "#7be495"

HEADING_FONTS = ("Arial Rounded MT Bold", "Bahnschrift SemiBold", "Segoe UI Semibold", "Segoe UI")
BODY_FONTS = ("Bahnschrift SemiBold", "Segoe UI Semibold", "Segoe UI")

fonts = {}


def _pick(root, wanted, default="TkDefaultFont"):
    have = {f.lower() for f in tkfont.families(root)}
    return next((f for f in wanted if f.lower() in have), default)


def make_fonts(root):
    h, b = _pick(root, HEADING_FONTS), _pick(root, BODY_FONTS)
    fonts["heading"] = (h, 10)
    fonts["title"] = (h, 26)
    fonts["big"] = (h, 14)
    fonts["body"] = (b, 10)
    fonts["small"] = (b, 9)
    return fonts


def dark_titlebar(root):
    """Windows 10/11: dark title bar in the menu blue (silently skipped where unsupported)"""
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        dwm = ctypes.windll.dwmapi
        one = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(one), 4)            # immersive dark mode
        for attr, rgb in ((35, BG), (36, FG)):                                # caption colour, caption text (Windows 11)
            c = ctypes.c_int(int(rgb[5:7] + rgb[3:5] + rgb[1:3], 16))        # COLORREF is BGR
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c), 4)
    except Exception:
        pass


def apply(root):
    make_fonts(root)
    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", fonts["body"])
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=EDGE, lightcolor=EDGE,
                darkcolor=EDGE, troughcolor=FIELD, focuscolor=CYAN, selectbackground=BLUE, selectforeground="#ffffff",
                insertcolor="#ffffff", font=fonts["body"])
    s.configure("TLabel", background=BG, foreground=FG)
    s.configure("Note.TLabel", foreground=MUTED, font=fonts["small"])
    s.configure("Value.TLabel", foreground=ORANGE, font=fonts["big"])
    s.configure("Hint.TLabel", foreground=ORANGE, font=fonts["small"])
    s.configure("Status.TLabel", background=TOPBAR, foreground=FG, padding=(10, 6))
    s.configure("TFrame", background=BG)

    s.configure("TButton", background=BLUE, foreground="#ffffff", bordercolor=BLUE_HI, lightcolor=BLUE, darkcolor=BLUE,
                borderwidth=1, relief="flat", padding=(14, 6), font=fonts["heading"])
    s.map("TButton", background=[("disabled", PANEL), ("pressed", "#123f94"), ("active", BLUE_HI)],
          foreground=[("disabled", MUTED)], bordercolor=[("focus", CYAN), ("active", CYAN)],
          lightcolor=[("active", BLUE_HI)], darkcolor=[("active", BLUE_HI)])
    s.configure("Accent.TButton", background=ORANGE_DK, foreground="#2a1500", bordercolor=ORANGE, lightcolor=ORANGE_DK,
                darkcolor=ORANGE_DK)
    s.map("Accent.TButton", background=[("disabled", PANEL), ("pressed", "#d97f00"), ("active", ORANGE)],
          foreground=[("disabled", MUTED)], lightcolor=[("active", ORANGE)], darkcolor=[("active", ORANGE)])

    s.configure("TNotebook", background=BG, bordercolor=EDGE, tabmargins=(0, 4, 0, 0))
    s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(22, 8), bordercolor=PANEL,
                lightcolor=PANEL, darkcolor=PANEL, font=fonts["heading"])
    s.map("TNotebook.Tab", background=[("selected", BLUE), ("active", TOPBAR)],
          foreground=[("selected", "#ffffff"), ("active", FG)], bordercolor=[("selected", CYAN)],
          lightcolor=[("selected", CYAN)], darkcolor=[("selected", BLUE)], expand=[("selected", (0, 0, 0, 2))])

    # no dotted focus rectangle on tabs, buttons and check buttons (the focus element is left out of the layouts)
    s.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [("Notebook.label", {"side": "top", "sticky": ""})]})]})])
    s.layout("TButton", [("Button.border", {"sticky": "nswe", "border": "1", "children": [
        ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})]})])
    s.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        ("Checkbutton.indicator", {"side": "left", "sticky": ""}), ("Checkbutton.label", {"sticky": "nswe"})]})])

    s.configure("TLabelframe", background=BG, bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE, relief="solid")
    s.configure("TLabelframe.Label", background=BG, foreground=ORANGE, font=fonts["heading"])

    for w in ("TEntry", "TCombobox"):
        s.configure(w, fieldbackground=FIELD, foreground=FG, bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE,
                    insertcolor="#ffffff", padding=4, selectbackground=BLUE, selectforeground="#ffffff")
    s.map("TEntry", bordercolor=[("focus", CYAN)], lightcolor=[("focus", CYAN)], darkcolor=[("focus", CYAN)])
    s.configure("TCombobox", arrowcolor=CYAN, background=PANEL)
    s.map("TCombobox", fieldbackground=[("readonly", FIELD), ("disabled", PANEL)], foreground=[("disabled", MUTED)],
          selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)],
          bordercolor=[("focus", CYAN)], lightcolor=[("focus", CYAN)], darkcolor=[("focus", CYAN)],
          background=[("active", TOPBAR)], arrowcolor=[("disabled", MUTED)])

    s.configure("TCheckbutton", background=BG, foreground=FG, indicatorbackground=FIELD, indicatorforeground=CYAN)
    s.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("selected", BLUE)],
          foreground=[("active", "#ffffff")])

    s.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG, bordercolor=EDGE, lightcolor=EDGE,
                darkcolor=EDGE, rowheight=28, borderwidth=1, font=fonts["body"])
    s.map("Treeview", background=[("selected", BLUE)], foreground=[("selected", "#ffffff")])
    s.configure("Treeview.Heading", background=TOPBAR, foreground=ORANGE, bordercolor=EDGE, lightcolor=TOPBAR,
                darkcolor=TOPBAR, relief="flat", padding=(8, 5), font=fonts["heading"])
    s.map("Treeview.Heading", background=[("active", BLUE)])
    s.configure("TScrollbar", background=TOPBAR, troughcolor=FIELD, bordercolor=FIELD, lightcolor=TOPBAR,
                darkcolor=TOPBAR, arrowcolor=CYAN, relief="flat")
    s.map("TScrollbar", background=[("active", BLUE)])
    return s


def style_text(widget):
    """a classic tk.Text in the same colours"""
    widget.configure(bg=FIELD, fg=FG, insertbackground="#ffffff", selectbackground=BLUE, selectforeground="#ffffff",
                     relief="flat", highlightthickness=1, highlightbackground=EDGE, highlightcolor=CYAN,
                     font=fonts["body"], padx=10, pady=8)


class Header(tk.Canvas):
    """The top bar of the game's menus: round profile badge, "blur", a glowing blue bar with lights, fan level and progress."""
    H = 76

    def __init__(self, master, subtitle=""):
        super().__init__(master, height=self.H, bg=BG, highlightthickness=0)
        self.info = dict(lights="", rank=None, progress=0.0, name=subtitle)
        self.images = {}                                  # logo, coin, fan, person (tk.PhotoImage); drawn when present
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, **kw):
        self.info.update(kw)
        self.draw()

    def _glow_rect(self, x0, y0, x1, y1, fill, edge):
        for k, c in ((5, "#0c1c58"), (3, "#10307f"), (1, EDGE)):
            r = (y1 - y0) / 2 + k
            self._pill(x0 - k, y0 - k, x1 + k, y1 + k, c if k > 1 else edge, r)
        self._pill(x0, y0, x1, y1, fill, (y1 - y0) / 2)

    def _pill(self, x0, y0, x1, y1, fill, r):
        r = min(r, (y1 - y0) / 2)
        self.create_oval(x0, y0, x0 + 2 * r, y1 - 1, fill=fill, outline="")          # Tk draws an oval one pixel too low
        self.create_oval(x1 - 2 * r, y0, x1, y1 - 1, fill=fill, outline="")
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline="")

    def draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 400)
        cy = self.H // 2
        for r, c in ((34, "#0b1a55"), (30, "#0f2a85"), (26, "#1650d0")):          # badge with glow
            self.create_oval(52 - r, cy - r, 52 + r, cy + r, fill=c, outline="")
        self.create_oval(52 - 22, cy - 22, 52 + 22, cy + 22, fill="#1b6bff", outline="#6fb5ff", width=1)
        if self.images.get("person"):
            self.create_image(52, cy, image=self.images["person"])
        else:
            self.create_oval(52 - 7, cy - 15, 52 + 7, cy - 1, fill="#0a1a5c", outline="")                 # head
            self.create_arc(52 - 14, cy + 2, 52 + 14, cy + 30, start=0, extent=180, fill="#0a1a5c", outline="")  # shoulders
        if self.images.get("logo"):
            self.create_image(98, cy, image=self.images["logo"], anchor="w")
        else:
            self.create_text(98, cy, text="blur", anchor="w", fill="#ffffff", font=(fonts["title"][0], 24, "bold"))
        logo = self.images.get("logo")
        x0, x1 = (98 + logo.width() + 24 if logo else 215), w - 24                # the bar starts behind the logo / wordmark
        self._glow_rect(x0, cy - 13, x1, cy + 13, TOPBAR, EDGE)
        self.create_text(x0 + 18, cy, text=self.info["name"], anchor="w", fill=MUTED, font=fonts["small"])
        x = x1 - 18
        rank = self.info["rank"]
        if rank is not None:
            label = "Fan Status %d" % rank
            self.create_text(x, cy, text=label, anchor="e", fill="#ffffff", font=fonts["big"])
            x -= self._measure(label, fonts["big"]) + 22
            bx0, bx1 = x - 170, x                                                     # progress to the next fan level
            self._pill(bx0, cy - 5, bx1, cy + 5, "#0b1a55", 5)
            fill = bx0 + (bx1 - bx0) * max(0.0, min(1.0, self.info["progress"]))
            if fill - bx0 > 10:
                self._pill(bx0, cy - 5, fill, cy + 5, "#cdbdff", 5)
            x = bx0 - 18
            self.create_rectangle(x - 36, cy - 17, x, cy + 17, fill="#0a1a5c", outline=CYAN, width=2)          # fan badge
            if self.images.get("fan"):
                self.create_image(x - 18, cy, image=self.images["fan"])
            else:
                self.create_text(x - 18, cy, text="♥", fill=ORANGE, font=(fonts["big"][0], 15))
            x -= 56
        if self.info["lights"]:
            self.create_text(x, cy, text=self.info["lights"], anchor="e", fill=ORANGE, font=(fonts["big"][0], 15))
            x -= self._measure(self.info["lights"], (fonts["big"][0], 15)) + 8
            if self.images.get("coin"):
                self.create_image(x - 12, cy, image=self.images["coin"])
            else:
                self.create_oval(x - 18, cy - 9, x, cy + 9, fill="#2a2f9c", outline="#8f8fff")
                self.create_text(x - 9, cy, text="b", fill="#d6d6ff", font=(fonts["body"][0], 9, "bold"))

    def _measure(self, text, font):
        return tkfont.Font(font=font).measure(text)
