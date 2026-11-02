"""blursave editor by ZR1Legend (Tkinter). Start:  python tools\\blursave_editor.py [blursave]

Reads and writes %APPDATA%\\bizarre creations\\blur\\save\\blursave. Before every write the file is copied to
...\\blur\\editor_backups. The game recomputes or repairs several values when it loads a save (fan level, lights,
unlocked tiers/events, boss reward cars); the "Vorschau" tab shows what that would change, and the same repairs are
applied before writing, so the file already is what the game makes of it (see blursave_rules.py, BLURSAVE_FORMAT.md).
"""
import copy
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blursave as bs                      # noqa: E402
import ps3save                             # noqa: E402
import blursave_rules as rules             # noqa: E402
import blurdisplay
import blurtip
import blurevents
import blurpicker                         # noqa: E402
import blursettings                        # noqa: E402
from blurgallery import Gallery            # noqa: E402
import blurtheme as theme                  # noqa: E402
ICONS = os.path.join(HERE, "blursave_icons.zip")
NEW_SAVE = os.path.join(HERE, "blursave_new.bin")           # a save game as the game writes it for a new profile
DEFAULT_SAVE = os.path.join(os.environ.get("APPDATA", ""), "bizarre creations", "blur", "save", "blursave")
DISPLAY = blurdisplay.load()               # readable names made from the save's internal names; no game file is read
STATUS = ["Locked", "Unlocked", "Completed"]
PLACES = {0: "No podium", 3: "1st", 2: "2nd", 1: "3rd"}
DIFFS = {0: "–", 1: "Easy", 2: "Medium", 3: "Hard"}
VSTATE = {0: "Not awarded", 1: "New", 2: "Seen"}
ONOFF = ["Off", "On"]
AUDIO_ROWS = [      # (label, key in doc["settings"]["audio"], options; None = 0-9 spinbox)
    ("Audio quality", "quality", ["Low", "Medium", "High"]),
    ("Sound effects", "sfx", None), ("Music", "music", None), ("Menu music", "menu_music", None),
    ("Licensed Soundtrack", "licensed", ONOFF), ("Dynamic range", "dynamic_range", ["TV", "Home theater"]),
    ("Output", "output", ["Stereo", "Surround"])]
ADVANCED_ROWS = [
    ("Room size", "room_size", ["Small", "Medium", "Large", "Auditorium"]),
    ("Music mode", "music_mode", ["Stereo", "Quad", "Surround"]), ("LFE Boost", "lfe_boost", None)]
CONTROL_ROWS = [
    ("Controller layout", "controller_layout", ["Layout 1", "Layout 2", "Layout 3"]),
    ("Keyboard layout", "keyboard_layout", ["Layout 1", "Layout 2"])]
GAME_ROWS = [("Difficulty", "difficulty", ["Easy (default)", "Easy", "Medium", "Hard"])]
BRIGHTNESS_ROWS = [("Brightness Adjust", "brightness", None)]
REGION_ROWS = [("Region Rule", "region_rule", ["Any Region", "Local Region Preferred", "Local Region Only"])]
LOGO_BOTTOM, LOGO_BAND, TEXT_GAP = 52, 46, 10         # info area: the logo ends at this y, the name starts TEXT_GAP below it, the class TEXT_GAP below the name
PAINT_SHIFT = 7                     # pixels a car is shifted to the right in the gallery when it shows the colour hexagon
PAINT_LEVELS = ["1 (darkest, black)", "2", "3", "4 (brightest)"]
FINISH_NAMES = list(bs.FINISHES.values())          # standard, then the paints with the prefixes P_, C_, M_
GFX_QUALITY = ["0 (lowest)", "1", "2", "3 (highest)"]
GFX_AA = ["Off", "2x", "4x", "8x"]
RESOLUTIONS = ["1024x768", "1280x720", "1280x1024", "1366x768", "1600x900", "1920x1080", "2560x1440", "3840x2160"]
EVENTS = json.load(open(os.path.join(HERE, "blursave_events.json"), encoding="utf-8"))      # city, landmark and kind of each event
STICKERS = json.load(open(os.path.join(HERE, "blursave_stats.json"), encoding="utf-8"))    # the goals of the stickers (index of the counter, goal, text)
STICKER_ORDER = list(dict.fromkeys(e["achievement_id"] for e in sorted(STICKERS, key=lambda e: (e["gallery_position"], e["index"]))))   # the order of the game's sticker gallery
MODS = dict(bs.MODS_SEEN)                  # number -> name (the eight single-player mods)
MOD_NOTE = "Only 24 to 31 are single-player mods; tested: 0, 23 and 32 keep the car selection of a race from opening"


def mod_text(n):
    return "%s (%d)" % (MODS.get(n, "None" if n == 255 else "Untested"), n)



def num(n):
    return "{:,}".format(int(n))


def demand_text(tier_def, i):
    d, target = tier_def["boss_demands"][i], tier_def["boss_demand_targets"][i]
    return DISPLAY["demands"].get(d, d).replace("%d", num(target), 1).replace("%d", "…")


def game_running():
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
    except Exception:
        return False
    return "blur.exe" in out or "blurrebuilt.exe" in out


class Editor(tk.Tk):
    def __init__(self, path=None, tab=0):
        super().__init__()
        theme.apply(self)
        self.title("blursave editor")
        w, h = min(1280, self.winfo_screenwidth() - 40), min(860, self.winfo_screenheight() - 90)
        self.geometry("%dx%d+%d+%d" % (w, h, (self.winfo_screenwidth() - w) // 2, max(0, (self.winfo_screenheight() - h) // 3)))
        self.minsize(min(1100, w), min(700, h))
        self.path = None
        self.doc = None
        self.dirty = False
        self._busy = False
        self._icons = {}
        self._build_ui()
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-o>", lambda e: self.open_dialog())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if path or os.path.exists(DEFAULT_SAVE):
            self.load(path or DEFAULT_SAVE)
        self.nb.select(tab)
        theme.dark_titlebar(self)

    def icon(self, kind, name):
        """a car ("cars") or mod ("mods") picture from blursave_icons.zip; None if there is none"""
        key = (kind, name)
        if key not in self._icons:
            img = None
            try:
                with zipfile.ZipFile(ICONS) as z:
                    img = tk.PhotoImage(data=z.read("%s/%s.png" % (kind, name)))
            except (KeyError, OSError, tk.TclError):
                pass
            self._icons[key] = img
        return self._icons[key]

    # ---------- layout ----------
    def _build_ui(self):
        self.header = theme.Header(self, "blursave editor")
        self.header.images = {k: self.icon("header", k) for k in ("logo", "coin", "fan", "person")}
        self.header.pack(fill="x", padx=(8, 8), pady=(8, 0))
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Button(bar, text="New…", command=self.new_save).pack(side="left")
        ttk.Button(bar, text="Open…", command=self.open_dialog).pack(side="left", padx=4)
        ttk.Button(bar, text="Import PS3/Xbox…", command=self.import_ps3).pack(side="left")
        ttk.Button(bar, text="Export PS3…", command=self.export_ps3).pack(side="left", padx=4)
        ttk.Button(bar, text="Reload", command=self.reload).pack(side="left")
        self.save_btn = ttk.Button(bar, text="Save (Ctrl+S)", command=self.save, style="Accent.TButton")
        self.save_btn.pack(side="left", padx=4)
        ttk.Button(bar, text="Save As…", command=self.save_as).pack(side="left")
        ttk.Button(bar, text="Info", command=self.show_info).pack(side="right", padx=4)
        self.file_lbl = ttk.Label(bar, text="no file", style="Note.TLabel")
        self.file_lbl.pack(side="left", padx=12)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tab_profile, self.tab_camp, self.tab_veh, self.tab_stk, self.tab_set, self.tab_prev = (
            ttk.Frame(self.nb, padding=14) for _ in range(6))
        for t, n in ((self.tab_profile, "Profile"), (self.tab_camp, "Career"), (self.tab_veh, "Cars"),
                     (self.tab_stk, "Stickers"), (self.tab_set, "Settings"), (self.tab_prev, "Preview")):
            self.nb.add(t, text=n)
        self.status = ttk.Label(self, anchor="w", style="Status.TLabel")
        self.status.pack(fill="x", side="bottom")
        self._build_profile()
        self._build_campaign()
        self._build_vehicles()
        self._build_stickers()
        self._build_settings()
        self._build_preview()

    def _build_profile(self):
        f = self.tab_profile
        f.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(f, text="Fans").grid(row=r, column=0, sticky="w", pady=4)
        self.fans_var = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.fans_var, width=14)
        e.grid(row=r, column=1, sticky="w")
        e.bind("<Return>", lambda ev: self.apply_fans())
        e.bind("<FocusOut>", lambda ev: self.apply_fans())
        self.level_lbl = ttk.Label(f, text="", style="Value.TLabel")
        self.level_lbl.grid(row=r, column=2, sticky="w", padx=12)
        r += 1
        ttk.Label(f, text="Set Fan Status").grid(row=r, column=0, sticky="w", pady=4)
        self.rank_var = tk.StringVar()
        cb = ttk.Combobox(f, textvariable=self.rank_var, width=30, state="readonly",
                          values=["Fan Status %d  (from %s fans)" % (x["rank"], num(x["fans"])) for x in rules.RANKS if x["rank"]])
        cb.grid(row=r, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", self.apply_rank)
        r += 1
        ttk.Label(f, text="Mod").grid(row=r, column=0, sticky="w", pady=4)
        self.mod_var = tk.StringVar()
        mf = ttk.Frame(f)
        mf.grid(row=r, column=1, sticky="w")
        self.mod_cb = ttk.Combobox(mf, textvariable=self.mod_var, width=30, state="readonly",
                                   values=[mod_text(k) for k in range(256)])          # experiment: every number 0-255 (see MOD_NOTE)
        self.mod_cb.pack(side="left")
        self.mod_icon = ttk.Label(mf)
        self.mod_icon.pack(side="left", padx=(10, 0))
        self.mod_cb.bind("<<ComboboxSelected>>", self.apply_mod)
        self.mod_note = ttk.Label(f, text="", style="Note.TLabel")
        self.mod_note.grid(row=r, column=2, sticky="w", padx=12)
        r += 1
        lf = ttk.Frame(f)
        lf.grid(row=r, column=0, sticky="w", pady=4)
        ttk.Label(lf, text="Last driven car").pack(side="left")
        tip = self.last_tip = ttk.Label(lf, image=blurtip.info_image(), cursor="question_arrow")
        tip.pack(side="left", padx=(8, 12))
        blurtip.Tooltip(tip, "This car appears in the background of the menu when you select the campaign.")
        self.last_var = tk.StringVar()
        cf = ttk.Frame(f)
        cf.grid(row=r, column=1, sticky="w")
        self.last_cb = ttk.Combobox(cf, textvariable=self.last_var, width=46, state="readonly")
        self.last_cb.pack(side="left")
        self.last_cb.bind("<<ComboboxSelected>>", self.apply_last)
        self.last_pic = ttk.Label(cf)
        self.last_pic.pack(side="left", padx=(14, 0))
        r += 1
        ttk.Label(f, text="Lights").grid(row=r, column=0, sticky="w", pady=4)
        self.lights_lbl = ttk.Label(f, text="", style="Value.TLabel")
        self.lights_lbl.grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(f, justify="left", style="Note.TLabel", text=(
            "The game works out the Fan Status from the fans and the lights from the event results,\n"
            "so both can only be changed indirectly here (fans, or the Career tab).")).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(18, 0))

    def _build_campaign(self):
        f = self.tab_camp
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        left = ttk.Frame(f)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.tier_tv = ttk.Treeview(left, columns=("boss", "lights", "state"), show="tree headings", height=10,
                                    selectmode="browse")
        self.tier_tv.heading("#0", text="Group")
        self.tier_tv.heading("boss", text="Rival")
        self.tier_tv.heading("lights", text="Lights")
        self.tier_tv.heading("state", text="Status")
        self.tier_tv.column("#0", width=160)
        self.tier_tv.column("boss", width=115)
        self.tier_tv.column("lights", width=70, anchor="e")
        self.tier_tv.column("state", width=105)
        self.tier_tv.pack(fill="y", expand=True)
        self.tier_tv.bind("<<TreeviewSelect>>", lambda e: self.select_tier())
        tb = ttk.Frame(left)
        tb.pack(fill="x", pady=6)
        ttk.Button(tb, text="Complete group", command=self.tier_complete).pack(side="left")
        ttk.Button(tb, text="Reset group", command=self.tier_reset).pack(side="left", padx=4)
        right = ttk.Frame(f)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.ev_tv = blurevents.EventCards(right, lambda n, kind="events": self.icon(kind, n))     # the cards of the game's Career menu
        self.ev_tv.grid(row=0, column=0, sticky="nsew")
        self.ev_tv.bind("<<TreeviewSelect>>", lambda e: self.select_event())
        box = ttk.LabelFrame(right, text="Selected event", padding=8)
        box.grid(row=1, column=0, sticky="ew", pady=8)
        self.e_status, self.e_place, self.e_diff, self.e_fans = (tk.StringVar() for _ in range(4))
        self.e_tunnel = tk.IntVar()
        ttk.Label(box, text="Status").grid(row=0, column=0, sticky="w")
        ttk.Combobox(box, textvariable=self.e_status, values=STATUS, width=12, state="readonly").grid(row=0, column=1, padx=6)
        ttk.Label(box, text="Place").grid(row=0, column=2, sticky="w")
        ttk.Combobox(box, textvariable=self.e_place, values=list(PLACES.values()), width=12, state="readonly").grid(row=0, column=3, padx=6)
        ttk.Label(box, text="Difficulty").grid(row=0, column=4, sticky="w")
        ttk.Combobox(box, textvariable=self.e_diff, values=list(DIFFS.values()), width=10, state="readonly").grid(row=0, column=5, padx=6)
        ttk.Checkbutton(box, text="Fan Run", variable=self.e_tunnel).grid(row=1, column=0, pady=6, sticky="w")
        self.e_car = ttk.Label(box, text="")
        self.e_car.grid(row=1, column=4, columnspan=2, sticky="w", padx=6)
        ttk.Label(box, text="Fans").grid(row=1, column=2, sticky="w")
        ttk.Entry(box, textvariable=self.e_fans, width=10).grid(row=1, column=3, sticky="w", padx=6)
        bb = ttk.Frame(box)
        bb.grid(row=2, column=0, columnspan=6, sticky="w", pady=(4, 0))
        ttk.Button(bb, text="Apply", command=self.event_apply).pack(side="left")
        ttk.Button(bb, text="Best result", command=self.event_best).pack(side="left", padx=4)
        ttk.Button(bb, text="Reset", command=self.event_reset).pack(side="left")
        self.boss_box = ttk.LabelFrame(right, text="Rival Demands", padding=8)
        self.boss_box.grid(row=2, column=0, sticky="ew")
        self.b_vars, self.b_lbls = [], []
        for i in range(4):
            lbl = ttk.Label(self.boss_box, text="", width=58)
            lbl.grid(row=i, column=0, sticky="w")
            v = tk.StringVar()
            ent = ttk.Entry(self.boss_box, textvariable=v, width=10)
            ent.grid(row=i, column=1, padx=6, pady=1)
            ent.bind("<Return>", lambda ev: self.boss_apply())
            ent.bind("<FocusOut>", lambda ev: self.boss_apply())
            tgt = ttk.Label(self.boss_box, text="")
            tgt.grid(row=i, column=2, sticky="w")
            self.b_vars.append(v)
            self.b_lbls.append((lbl, tgt))
        self.boss_info = ttk.Label(self.boss_box, text="", style="Note.TLabel")
        self.boss_info.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        bb2 = ttk.Frame(self.boss_box)
        bb2.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Button(bb2, text="Meet demands", command=self.boss_meet).pack(side="left")
        ttk.Button(bb2, text="Defeat rival", command=self.boss_win).pack(side="left", padx=4)
        ttk.Button(bb2, text="Reset demands", command=self.boss_reset).pack(side="left")

    def _build_vehicles(self):
        f = self.tab_veh
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        first = self.icon("seen", sorted(v["name"] for v in bs.load_vehicles().values())[0])
        cell = (max(first.width() + 14, 116), first.height() + 8 + 46) if first else (116, 108)   # picture and up to 3 lines of name
        self.veh_tv = Gallery(f, cell)
        self.veh_tv.grid(row=0, column=0, sticky="nsew")
        self.veh_sep = ttk.Separator(f, orient="horizontal")
        self.veh_sep.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        info = ttk.Frame(f)
        info.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.veh_info = info
        # fixed places: whatever the car, nothing moves (each block has a fixed size, the contents are placed inside it)
        pic_box = ttk.Frame(info, width=150, height=170)
        pic_box.grid(row=0, column=0, rowspan=2, padx=(10, 0), sticky="nw")
        pic_box.grid_propagate(False)
        pic_box.pack_propagate(False)
        self.car_pic = ttk.Label(pic_box)
        self.car_pic.place(relx=0, rely=0.5, anchor="w")
        head = ttk.Frame(info, width=230, height=184)               # logo, name and class one below the other, centred (as in the game)
        head.grid(row=0, column=1, sticky="nw")
        head.grid_propagate(False)
        head.pack_propagate(False)
        self.car_logo = ttk.Label(head)
        self.car_logo.place(relx=0.5, y=LOGO_BOTTOM - LOGO_BAND // 2, anchor="center")          # centred in the band the biggest logo fills
        self.car_name = ttk.Label(head, font=theme.fonts["big"], wraplength=220, justify="center")
        self.car_name.place(relx=0.5, y=LOGO_BOTTOM + TEXT_GAP, anchor="n")
        self.car_class = ttk.Label(head)
        self.car_class.place(relx=0.5, y=LOGO_BOTTOM + 70, anchor="n")
        facts = ttk.Frame(info)
        facts.grid(row=0, column=2, sticky="nw", padx=(14, 0))
        facts.columnconfigure(1, minsize=230)
        self.car_facts = {}
        for r, (key, label) in enumerate((("status", "Status"), ("source", "Unlocked by"), ("paint", "Paint"))):
            facts.rowconfigure(r, minsize=44)
            ttk.Label(facts, text=label).grid(row=r, column=0, sticky="nw", padx=(0, 16), pady=2)
            self.car_facts[key] = ttk.Label(facts, style="Value.TLabel", font=theme.fonts["body"], compound="left",
                                            wraplength=225, justify="left", anchor="nw")
            self.car_facts[key].grid(row=r, column=1, sticky="nw", pady=2)
        bb = ttk.Frame(info)
        bb.grid(row=1, column=1, columnspan=2, sticky="sw", pady=(10, 0), padx=(0, 0))
        ttk.Button(bb, text="Selected: seen", command=lambda: self.veh_set(2)).pack(side="left")
        ttk.Button(bb, text="Selected: new (marker)", command=lambda: self.veh_set(1)).pack(side="left", padx=4)
        ttk.Button(bb, text="All: seen", command=self.veh_all_seen).pack(side="left")
        pf = ttk.LabelFrame(info, text="Paint (Respray, saved in the save game)", padding=8)
        pf.grid(row=0, column=3, rowspan=2, sticky="ne", padx=(14, 0))
        self.pt_frame = pf
        self.pt_info, self.pt_buttons = info, None
        self.pt_level, self.pt_row, self.pt_col = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.pt_finish = tk.StringVar(value=FINISH_NAMES[0])
        self.pt_level.set(PAINT_LEVELS[3])
        self.pt_row.set("4")
        self.pt_col.set("4")
        self._paint_colours = {}
        self.picker = blurpicker.PaintPicker(pf, self.pt_level, self.pt_row, self.pt_col, PAINT_LEVELS, self._picker_colour,
                                             self._picker_available)
        self.picker.grid(row=0, column=0, rowspan=4, sticky="nw")
        side = ttk.Frame(pf)
        side.grid(row=0, column=1, rowspan=4, sticky="nw", padx=(14, 0))
        side.columnconfigure(0, minsize=190)                        # fixed width, so the frame does not move when the hint appears
        ttk.Label(side, text="Finish").grid(row=0, column=0, sticky="w")
        fin = ttk.Combobox(side, textvariable=self.pt_finish, values=FINISH_NAMES, width=17, state="readonly")
        fin.grid(row=1, column=0, sticky="w", pady=(2, 0))
        fin.bind("<<ComboboxSelected>>", lambda e: self._paint_finish())
        self.pt_text = ttk.Label(side, text="", style="Note.TLabel", wraplength=170, justify="left")
        self.pt_text.grid(row=2, column=0, sticky="w", pady=(8, 0))
        for var in (self.pt_level, self.pt_row, self.pt_col, self.pt_finish):
            var.trace_add("write", lambda *a: self._paint_text_update())
        self.pt_btn = ttk.Button(side, text="Apply to selected cars", command=self.paint_apply)
        self.pt_btn.grid(row=3, column=0, sticky="we", pady=(16, 0))
        ttk.Button(side, text="Remove paint", command=self.paint_remove).grid(row=4, column=0, sticky="we", pady=(6, 0))
        hint_box = ttk.Frame(side, width=190, height=62)             # the room of the hint is always there, so nothing moves
        hint_box.grid(row=5, column=0, sticky="nw", pady=(10, 0))
        hint_box.pack_propagate(False)
        hint_box.grid_propagate(False)
        self.pt_hint = ttk.Label(hint_box, text="", style="Hint.TLabel", wraplength=190, justify="left")
        self.pt_hint.pack(anchor="nw")
        self._paint_text_update()
        self.pt_buttons = bb
        self.after_idle(self._reserve_paint_space)
        ttk.Label(f, style="Note.TLabel", justify="left", wraplength=1100, text=(
            "Cars: coloured = seen, with a triangle = new, grey = not awarded. The status is only the \"seen\" marker; a car is "
            "unlocked by the Fan Status or by a rival reward, and reward cars without the rival are set back to \"Not awarded\" by "
            "the game when it loads the save. Paint: row and column are the cell in the colour hexagon of the game (rows of 4, 5, "
            "6, 7, 6, 5, 4 cells, counted from the top left); brightness 1 is always black; Finish: Pearlescent/Candy/Metallic are paints the game has but its colour picker does not offer (brightest level only). The game accepts a paint for every car, "
            "also for those it offers no respray for.")).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.veh_tv.bind("<<TreeviewSelect>>", lambda e: self._car_info(controls=True))
        self.bind("<Escape>", self._escape)

    def _escape(self, e):
        """Escape on the Cars tab: no car chosen (not while typing in a field)"""
        if self.nb.select() == str(self.tab_veh) and not isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)):
            self.veh_tv.selection_set()

    def _reserve_paint_space(self):
        """keep the room of the paint frame when it is hidden, so the gallery above does not change its height"""
        self.update_idletasks()
        self.pt_info.rowconfigure(0, minsize=max(0, self.pt_frame.winfo_reqheight() - self.pt_buttons.winfo_reqheight() - 10))

    def _picker_finish(self):
        return list(bs.FINISHES)[FINISH_NAMES.index(self.pt_finish.get())]

    def _picker_colour(self, row, col, level):
        key = (row, col, level)
        if key not in self._paint_colours:
            self._paint_colours[key] = bs.paint_colour(row, col, level)
        return self._paint_colours[key]

    def _picker_available(self, row, col, level):
        """False for what the chosen finish does not have: other brightness levels, and the cells the game lacks for it"""
        finish = self._picker_finish()
        if not finish:
            return True
        if level != 4:
            return False
        try:
            bs.paint_id(4, sum(bs.PAINT_ROWS[:row - 1]) + col - 1, finish)
        except KeyError:
            return False
        return True

    def _paint_finish(self):
        """the paints with a finish exist in the brightest level only (the game hides the brightness selector for P_ and C_)"""
        if self._picker_finish():
            self.pt_level.set(PAINT_LEVELS[3])
        self.picker.refresh()

    def _paint_text_update(self):
        try:
            self.pt_text.config(text="Row %s, column %s, brightness %d" % (
                self.pt_row.get(), self.pt_col.get(), PAINT_LEVELS.index(self.pt_level.get()) + 1))
        except ValueError:
            pass

    def _paint_colour_of(self, vid, dimmed):
        """colour of the car's paint for the gallery; None for the manufacturer's colour (no entry in the paint table)"""
        e = self._paint_entry(vid)
        c = bs.paint_colour_of(int(e["paint"], 16)) if e else None
        return blurpicker.dim(c, 0.45) if c and dimmed else c

    def _paint_entry(self, vid):
        pt = self.doc.get("paints")
        return next((e for e in pt["entries"] if e["vehicle"] == vid), None) if pt else None

    def _paint_text(self, vid):
        e = self._paint_entry(vid)
        if not e:
            return ""
        row, col = bs.paint_cell(e["index"])
        fin = bs.paint_finish(int(e["paint"], 16))
        return "%sBrightness %d, row %d, column %d" % (
            bs.FINISHES[fin].split(" (")[0] + ", " if fin else "", bs.paint_level(int(e["paint"], 16)), row, col)

    def _car_info(self, controls=False):
        """the info area: picture, manufacturer, name and facts of the selected car; controls: also fill the paint controls"""
        sel = self.veh_tv.selection() if self.doc else ()
        facts = self.car_facts
        for w in (self.veh_sep, self.veh_info):                    # no car chosen: the gallery gets the whole tab
            w.grid() if sel else w.grid_remove()
        _, can = bs.load_paints()
        n_no = sum(int(self.veh_by_id[i]["id"], 16) not in can for i in sel)
        self.pt_hint.config(text="" if not n_no else (
            "The game offers no respray for this car; it takes the paint from the save game anyway." if len(sel) == 1 else
            "No respray in the game for %d of the selected cars; it takes the paint from the save game anyway." % n_no))
        if sel:                                                    # the paint table takes every car, not only those the game offers a respray for
            self.pt_frame.grid()
        else:
            self.pt_frame.grid_remove()
        if len(sel) != 1:
            self.car_pic.config(image="")
            self.car_logo.config(image="")
            self.car_class.config(image="")
            self.car_name.config(text="%d cars selected" % len(sel) if sel else "Select a car")
            for lbl in facts.values():
                lbl.config(text="", image="")
            return
        v = self.veh_by_id[sel[0]]
        self.car_pic.config(image=self.icon("cars", v["name"]) or "")
        self.car_logo.config(image=self.icon("logos", blurdisplay.maker_logo(v["name"]) or "") or "")
        self.car_name.config(text=self.short[v["id"]])
        self.update_idletasks()                                    # the class follows the name (one or two lines) at the same gap as the name follows the logo
        self.car_class.place_configure(y=LOGO_BOTTOM + TEXT_GAP + self.car_name.winfo_reqheight() + TEXT_GAP)
        badge = self.icon("classes", v["class"])
        self.car_class.config(image=badge or "")
        facts["status"].config(text=VSTATE[v["state"]])
        facts["source"].config(text=self._car_source().get(v["name"], "-"))
        facts["paint"].config(text=self._paint_text(v["id"]) or "stock")
        if controls:
            e = self._paint_entry(sel[0])
            if e:
                row, col = bs.paint_cell(e["index"])
                self.pt_finish.set(bs.FINISHES[bs.paint_finish(int(e["paint"], 16))])
                self.pt_level.set(PAINT_LEVELS[bs.paint_level(int(e["paint"], 16)) - 1])
                self._paint_finish()
                self.pt_row.set(str(row))
                self.pt_col.set(str(col))

    def _car_source(self):
        """{model name: how the car is unlocked}"""
        src = {}
        for r in rules.RANKS:
            for n in r["vehicles"]:
                src[n] = "Fan Status %d (from %s fans)" % (r["rank"], num(r["fans"]))
        for tier, (a, b) in rules.REWARDS.items():
            for n in a:
                src[n] = "Group %d: demands met (%s)" % (tier, DISPLAY["bosses"][tier - 1])
            for n in b:
                src[n] = "Group %d: rival %s defeated" % (tier, DISPLAY["bosses"][tier - 1])
        return src

    def paint_set(self, vid, level, row, col, finish=""):
        pt = self.doc["paints"]
        index = sum(bs.PAINT_ROWS[:row - 1]) + col - 1
        paint = "%08x" % bs.paint_id(level, index, finish)
        e = self._paint_entry(vid)
        if e is None:
            e = {"vehicle": vid, "name": self.veh_by_id[vid]["name"]}
            pt["entries"].append(e)
        e["paint"], e["index"] = paint, index
        pt["last"] = {"paint": paint, "index": index}

    def paint_apply(self):
        if self._busy or not self.doc:
            return
        if "paints" not in self.doc:
            messagebox.showinfo("Paint", "This save has no paint table the editor recognises (no car has been resprayed yet). "
                                         "Respray any car in the game once, then open the save again.")
            return
        cars = self._selected_vehicles()
        if not cars:
            messagebox.showinfo("Paint", "Select one or more cars.")
            return
        level = PAINT_LEVELS.index(self.pt_level.get()) + 1
        finish = list(bs.FINISHES)[FINISH_NAMES.index(self.pt_finish.get())]
        try:
            bs.paint_id(level, sum(bs.PAINT_ROWS[:int(self.pt_row.get()) - 1]) + int(self.pt_col.get()) - 1, finish)
        except KeyError:
            messagebox.showinfo("Paint", "The game has no paint with this finish for row %s, column %s. Pick another cell." % (
                self.pt_row.get(), self.pt_col.get()))
            return
        for v in cars:
            self.paint_set(v["id"], level, int(self.pt_row.get()), int(self.pt_col.get()), finish)
        self.touch()

    def paint_remove(self):
        if self._busy or not self.doc or "paints" not in self.doc:
            return
        ids = {v["id"] for v in self._selected_vehicles()}
        pt = self.doc["paints"]
        keep = [e for e in pt["entries"] if e["vehicle"] not in ids]
        if len(keep) == len(pt["entries"]):
            messagebox.showinfo("Paint", "None of the selected cars has a paint to remove.")
            return
        pt["entries"] = keep
        self.touch()

    # ---------- stickers (achievements): the counters of the statistics table ----------
    def _build_stickers(self):
        f = self.tab_stk
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        left = ttk.Frame(f)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self.stk_tv = ttk.Treeview(left, columns=("no", "goals", "modes"), show="tree headings", height=18, selectmode="browse")
        self.stk_tv.heading("#0", text="Sticker")
        self.stk_tv.heading("no", text="No.")
        self.stk_tv.heading("goals", text="Goals")
        self.stk_tv.heading("modes", text="Modes")
        self.stk_tv.column("#0", width=240)
        self.stk_tv.column("no", width=60, anchor="center")
        self.stk_tv.column("goals", width=60, anchor="center")
        self.stk_tv.column("modes", width=95)
        sb = ttk.Scrollbar(left, command=self.stk_tv.yview)
        self.stk_tv.configure(yscrollcommand=sb.set)
        self.stk_tv.pack(side="left", fill="y", expand=True)
        sb.pack(side="left", fill="y")
        self.stk_tv.bind("<<TreeviewSelect>>", lambda e: self.select_sticker())
        right = ttk.Frame(f)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        self.stk_title = ttk.Label(right, text="", font=theme.fonts["big"])
        self.stk_title.grid(row=0, column=0, sticky="w")
        self.stk_modes = ttk.Label(right, text="", style="Note.TLabel")
        self.stk_modes.grid(row=1, column=0, sticky="w", pady=(0, 10))
        box = ttk.LabelFrame(right, text="Goals", padding=10)
        box.grid(row=2, column=0, sticky="ew")
        box.columnconfigure(0, weight=1)
        self.g_rows = []
        for i in range(4):
            lbl = ttk.Label(box, text="", wraplength=470, justify="left")
            lbl.grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar()
            ent = ttk.Entry(box, textvariable=v, width=10, justify="right")
            ent.grid(row=i, column=1, padx=(10, 4))
            ent.bind("<Return>", lambda ev, i=i: self.stat_apply(i))
            ent.bind("<FocusOut>", lambda ev, i=i: self.stat_apply(i))
            goal = ttk.Label(box, text="", width=10)
            goal.grid(row=i, column=2, sticky="w")
            mark = ttk.Label(box, text="", width=14)
            mark.grid(row=i, column=3, sticky="w")
            self.g_rows.append((lbl, v, ent, goal, mark))
        bb = ttk.Frame(right)
        bb.grid(row=3, column=0, sticky="w", pady=10)
        ttk.Button(bb, text="Reach goals", command=lambda: self.stat_reach(False)).pack(side="left")
        ttk.Button(bb, text="Reset counters", command=self.stat_reset).pack(side="left", padx=4)
        ttk.Button(bb, text="Reach all goals of all stickers", command=lambda: self.stat_reach(True)).pack(side="left", padx=(16, 0))
        self.stk_note = ttk.Label(right, style="Note.TLabel", justify="left", wraplength=640, text=(
            "The game does not store which stickers you have; it stores these counters and compares them with the goals when it shows "
            "the sticker screen (tested: a counter set from 244 to 250 showed 250/250 with a tick at once). A goal with the value 1 is a "
            "yes/no goal. The list is in the order of the game's sticker gallery; No. is the position the game shows (for example 33/48 for Incoming!). Counters are numbers; some are fractions (repaired health, a time). Stickers marked \"n/a\" "
            "have a counter the game marks as unavailable (Blur.exe does that for the Xbox LIVE and sharing stickers when it loads)."))
        self.stk_note.grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.stk_empty = ttk.Label(f, style="Note.TLabel", wraplength=700, text=(
            "This save game has no statistics yet. The game creates the table when you play."))

    @staticmethod
    def _fmt(v):
        return str(int(v)) if v == int(v) else ("%.2f" % v).rstrip("0").rstrip(".")

    @staticmethod
    def sticker_text(e):
        g = Editor._fmt(e["goal"])
        return e["text"].replace("%.0f", g).replace("%.1f", g).replace("%%", "%")

    def _stat(self, index):
        return self.doc["stats"]["entries"][index]

    def _sticker_goals(self, ach_id):
        return [e for e in STICKERS if e["achievement_id"] == ach_id]

    def refresh_stickers(self):
        st = self.doc.get("stats")
        if not st:
            self.stk_tv.delete(*self.stk_tv.get_children())
            self.stk_empty.grid(row=0, column=0, columnspan=2, sticky="nw")
            return
        self.stk_empty.grid_remove()
        sel = self.stk_tv.selection()
        self.stk_tv.delete(*self.stk_tv.get_children())
        avail = [a for a in STICKER_ORDER if all(self._stat(g["index"])["available"] for g in self._sticker_goals(a))]   # the gallery leaves out the others
        for a in STICKER_ORDER:
            goals = self._sticker_goals(a)
            done = sum(1 for g in goals if self._stat(g["index"])["value"] >= g["goal"])
            modes = ", ".join(n for n, k in (("SP", "singleplayer"), ("MP", "multiplayer"), ("Split", "splitscreen")) if goals[0][k])
            self.stk_tv.insert("", "end", iid="stk%d" % a, text=goals[0]["achievement"], values=("%d/%d" % (avail.index(a) + 1, len(avail)) if a in avail else "–", "%d/%d" % (done, len(goals)), modes))
        if sel and self.stk_tv.exists(sel[0]):
            self.stk_tv.selection_set(sel[0])
        elif self.stk_tv.get_children():
            self.stk_tv.selection_set(self.stk_tv.get_children()[0])
        self.select_sticker()

    def _current_sticker(self):
        sel = self.stk_tv.selection()
        return int(sel[0][3:]) if sel else None

    def select_sticker(self):
        a = self._current_sticker()
        if a is None or not self.doc or not self.doc.get("stats"):
            return
        goals = self._sticker_goals(a)
        self.stk_title.config(text=goals[0]["achievement"])
        self.stk_modes.config(text="Can be earned in: " + ", ".join(
            n for n, k in (("single player", "singleplayer"), ("multiplayer", "multiplayer"), ("split screen", "splitscreen")) if goals[0][k]))
        for i, (lbl, v, ent, goal, mark) in enumerate(self.g_rows):
            if i >= len(goals):
                for w in (lbl, ent, goal, mark):
                    w.grid_remove()
                continue
            for w in (lbl, ent, goal, mark):
                w.grid()
            g, s = goals[i], self._stat(goals[i]["index"])
            lbl.config(text=self.sticker_text(g))
            v.set(self._fmt(s["value"]))
            ent.config(state="normal" if s["available"] else "disabled")
            goal.config(text="/ " + self._fmt(g["goal"]))
            mark.config(text="n/a" if not s["available"] else ("reached" if s["value"] >= g["goal"] else "not reached"),
                        foreground=theme.ORANGE if s["available"] and s["value"] >= g["goal"] else theme.MUTED)

    def stat_apply(self, i):
        if self._busy or not self.doc or not self.doc.get("stats"):
            return
        a = self._current_sticker()
        goals = self._sticker_goals(a) if a is not None else []
        if i >= len(goals):
            return
        s = self._stat(goals[i]["index"])
        if not s["available"]:
            return
        try:
            v = float(self.g_rows[i][1].get().replace(",", "."))
            if not (0 <= v < 1e9):
                raise ValueError
        except ValueError:
            self.g_rows[i][1].set(self._fmt(s["value"]))
            return
        v = float(struct.unpack("<f", struct.pack("<f", v))[0])             # what a float32 can hold
        if v != s["value"]:
            s["value"] = v
            self.touch()

    def stat_reach(self, everything):
        if not self.doc or not self.doc.get("stats"):
            return
        a = self._current_sticker()
        goals = STICKERS if everything else (self._sticker_goals(a) if a is not None else [])
        n = 0
        for g in goals:
            s = self._stat(g["index"])
            if s["available"] and s["value"] < g["goal"]:
                s["value"] = float(g["goal"])
                n += 1
        if n:
            self.touch()
            self.set_status("%d counters set to their goal, not saved" % n)

    def stat_reset(self):
        a = self._current_sticker()
        if a is None or not self.doc or not self.doc.get("stats"):
            return
        n = 0
        for g in self._sticker_goals(a):
            s = self._stat(g["index"])
            if s["available"] and s["value"] != 0:
                s["value"] = 0.0
                n += 1
        if n:
            self.touch()

    def _build_settings(self):
        f = self.tab_set
        self.set_vars, self.set_widgets = {}, []
        left = ttk.LabelFrame(f, text="Audio (saved in the save game)", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = ttk.Frame(f)
        right.grid(row=0, column=1, sticky="nsew")
        r = 0
        for label, key, opts in AUDIO_ROWS:
            self._set_row(left, r, label, key, opts)
            r += 1
        ttk.Label(left, text="Advanced Audio (the game shows these only with Output = Surround)", style="Note.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(12, 2))
        r += 1
        for label, key, opts in ADVANCED_ROWS:
            self._set_row(left, r, label, key, opts)
            r += 1
        ctl = ttk.LabelFrame(right, text="Controls (saved in the save game)", padding=10)
        ctl.grid(row=0, column=0, sticky="ew")
        for r, (label, key, opts) in enumerate(CONTROL_ROWS):
            self._set_row(ctl, r, label, key, opts)
        gm = ttk.LabelFrame(right, text="Game (saved in the save game)", padding=10)
        gm.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        for r, (label, key, opts) in enumerate(GAME_ROWS):
            self._set_row(gm, r, label, key, opts)
        mp = ttk.LabelFrame(right, text="Multiplayer Options (saved in the save game)", padding=10)
        mp.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        for r, (label, key, opts) in enumerate(REGION_ROWS):
            self._set_row(mp, r, label, key, opts)
        disp = ttk.LabelFrame(right, text="Display (saved in the save game)", padding=10)
        disp.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        for r, (label, key, opts) in enumerate(BRIGHTNESS_ROWS):
            self._set_row(disp, r, label, key, opts)
        gfx = ttk.LabelFrame(right, text="Graphics (settings.xml, written separately)", padding=10)
        gfx.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.g_quality, self.g_aa, self.g_res = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.g_full, self.g_vsync = tk.IntVar(), tk.IntVar()
        ttk.Label(gfx, text="Graphics Quality").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(gfx, textvariable=self.g_quality, values=GFX_QUALITY, width=14, state="readonly").grid(row=0, column=1, sticky="w")
        ttk.Label(gfx, text="Anti-aliasing").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(gfx, textvariable=self.g_aa, values=GFX_AA, width=14, state="readonly").grid(row=1, column=1, sticky="w")
        ttk.Label(gfx, text="Resolution").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(gfx, textvariable=self.g_res, values=RESOLUTIONS, width=14).grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(gfx, text="Fullscreen", variable=self.g_full).grid(row=3, column=0, sticky="w", pady=3)
        ttk.Checkbutton(gfx, text="Vsync", variable=self.g_vsync).grid(row=3, column=1, sticky="w")
        self.gfx_btn = ttk.Button(gfx, text="Write settings.xml", command=self.write_graphics)
        self.gfx_btn.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.gfx_note = ttk.Label(gfx, text="", style="Note.TLabel", wraplength=420, justify="left")
        self.gfx_note.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.set_note = ttk.Label(f, text="", style="Note.TLabel")
        self.set_note.grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _set_row(self, parent, r, label, key, opts):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 12))
        var = tk.StringVar()
        self.set_vars[key] = (var, opts)
        if opts is None:
            w = ttk.Spinbox(parent, from_=0, to=9, width=6, textvariable=var, command=lambda k=key: self.set_changed(k))
            w.bind("<Return>", lambda e, k=key: self.set_changed(k))
            w.bind("<FocusOut>", lambda e, k=key: self.set_changed(k))
        else:
            w = ttk.Combobox(parent, textvariable=var, values=opts, width=14, state="readonly")
            w.bind("<<ComboboxSelected>>", lambda e, k=key: self.set_changed(k))
        w.grid(row=r, column=1, sticky="w")
        self.set_widgets.append(w)

    def _set_field(self, key):
        st = self.doc["settings"]
        return st[key] if key in ("controller_layout", "keyboard_layout", "region_rule", "brightness", "difficulty") else st["audio"][key]

    def set_changed(self, key):
        if self._busy or not self.doc or "settings" not in self.doc:
            return
        var, opts = self.set_vars[key]
        f = self._set_field(key)
        try:
            v = opts.index(var.get()) if opts else int(var.get())
        except ValueError:
            self.refresh_all()
            return
        v = max(0, min(f["max"], v))
        if v != f["value"]:
            f["value"] = v
            self.touch()
        else:
            self.refresh_all()

    def refresh_settings(self):
        has = "settings" in self.doc
        for w in self.set_widgets:
            w.config(state=("readonly" if isinstance(w, ttk.Combobox) else "normal") if has else "disabled")
        self.set_note.config(text="" if has else "This save has no settings block the editor recognises.")
        if has:
            for key, (var, opts) in self.set_vars.items():
                if key == "region_rule" and key not in self.doc["settings"]:
                    var.set("")
                    continue
                v = self._set_field(key)["value"]
                var.set(opts[v] if opts and v < len(opts) else str(v))

    def load_graphics(self):
        self.gfx_path = blursettings.default_path(self.path)
        g = blursettings.read(self.gfx_path)
        self.gfx = g
        self.gfx_btn.config(state="normal" if g else "disabled")
        if not g:
            self.gfx_note.config(text="settings.xml not found or not readable: %s" % self.gfx_path)
            return
        self.g_quality.set(GFX_QUALITY[max(0, min(3, g["graphical_detail"] - 1))])
        self.g_aa.set(GFX_AA[max(0, min(3, g["multisample"]))])
        self.g_res.set("%dx%d" % (g["width"], g["height"]))
        self.g_full.set(0 if g["windowed"] else 1)
        self.g_vsync.set(int(bool(g["vsync"])))
        self.gfx_note.config(text="%s - the game rewrites this file itself when Graphics settings are accepted; "
                                  "a changed resolution should be one the game offers." % self.gfx_path)

    def write_graphics(self):
        if not self.gfx:
            return
        try:
            w, h = (int(x) for x in self.g_res.get().lower().replace(" ", "").split("x"))
            assert 320 <= w <= 16384 and 200 <= h <= 16384
        except (ValueError, AssertionError):
            messagebox.showerror("Resolution", "Please enter the resolution as WIDTHxHEIGHT, for example 1920x1080.")
            return
        if game_running() and not messagebox.askyesno(
                "Game running", "Blur is running and may overwrite settings.xml. Write anyway?"):
            return
        vals = dict(self.gfx)
        vals.update(width=w, height=h, multisample=GFX_AA.index(self.g_aa.get()),
                    graphical_detail=GFX_QUALITY.index(self.g_quality.get()) + 1,
                    windowed=0 if self.g_full.get() else 1, vsync=int(self.g_vsync.get()))
        bdir = os.path.join(os.path.dirname(self.gfx_path), "editor_backups")
        os.makedirs(bdir, exist_ok=True)
        backup = os.path.join(bdir, "settings_%s.xml" % time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(self.gfx_path, backup)
        blursettings.write(self.gfx_path, vals)
        if blursettings.read(self.gfx_path) != vals:
            messagebox.showerror("settings.xml", "Verification after writing failed. Backup: %s" % backup)
            return
        self.load_graphics()
        self.set_status("settings.xml written; backup: %s" % backup)

    def _build_preview(self):
        f = self.tab_prev
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        ttk.Label(f, text="What the game would change in this save when it loads it (and what is written along when saving):",
                  ).grid(row=0, column=0, sticky="w")
        self.prev_txt = tk.Text(f, wrap="word", height=20)
        theme.style_text(self.prev_txt)
        self.prev_txt.grid(row=1, column=0, sticky="nsew", pady=6)
        self.prev_txt.tag_configure("Game", foreground=theme.GREEN)
        self.prev_txt.tag_configure("Guess", foreground=theme.ORANGE)
        ttk.Label(f, style="Note.TLabel", text=("green = seen in the game, orange = guess (not tested in the game)")).grid(
            row=2, column=0, sticky="w")

    def show_info(self):
        win = tk.Toplevel(self)
        win.title("About and licenses")
        win.configure(bg=theme.BG)
        win.geometry("780x560")
        txt = tk.Text(win, wrap="word")
        theme.style_text(txt)
        sb = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True, padx=(10, 0), pady=10)
        try:
            txt.insert("1.0", open(os.path.join(HERE, "LICENSES.txt"), encoding="utf-8").read())
        except OSError:
            txt.insert("1.0", "LICENSES.txt is missing.")
        txt.config(state="disabled")
        theme.dark_titlebar(win)

    # ---------- load / save ----------
    def open_dialog(self):
        if not self.confirm_discard():
            return
        p = filedialog.askopenfilename(title="Open save game", initialdir=os.path.dirname(DEFAULT_SAVE) or None)
        if p:
            self.load(p)

    def new_save(self):
        """creates a new save game: the file the game writes for a new profile (no fans, no campaign progress, standard settings)"""
        if not self.confirm_discard():
            return
        p = filedialog.asksaveasfilename(title="New save game", initialfile="blursave",
                                         initialdir=os.path.dirname(self.path or DEFAULT_SAVE) or None)
        if not p:
            return
        if game_running() and not messagebox.askyesno(
                "Game running", "Blur is running. The game overwrites the save game when it exits and when it loads. "
                                "Create the new save game anyway?"):
            return
        try:
            data, _ = bs.extend_campaign(bs.read_save(NEW_SAVE))      # the campaign records of a new profile, initialised
            doc = bs.make_doc(data)
        except (Exception, SystemExit) as e:
            messagebox.showerror("New save game", "The template for a new save game cannot be read: %s" % e)
            return
        doc.setdefault("campaign", [])
        self.path, self.doc, self.dirty = None, doc, False
        self.veh_by_id = {v["id"]: v for v in self.doc["vehicles"]}
        self._texts()
        if not self.write(p):                                      # an existing file is backed up first (editor_backups)
            return
        self.veh_by_id = {v["id"]: v for v in self.doc["vehicles"]}
        self._texts()
        self.refresh_all()
        self.load_graphics()
        self.set_status("New save game created: %s (no fans, no campaign progress; the Career tab can be edited)" % p)

    def import_ps3(self):
        """reads a PlayStation 3 save game (AMAXSAVE with its PARAM.PFD) and writes its progress into a NEW PC save game: the PC template
        (a new profile) takes over level, fans, last car, mod, counters, car states and the whole campaign; the rest stays as in the template"""
        if not self.confirm_discard():
            return
        src = filedialog.askopenfilename(title="PS3 or Xbox 360 save game (AMAXSAVE; for the PS3 PARAM.PFD must be in the same folder)",
                                         filetypes=[("PS3 save game", "AMAXSAVE"), ("All files", "*.*")])
        if not src:
            return
        try:
            ps3 = ps3save.read(src)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Import PS3", str(e))
            return
        p = filedialog.asksaveasfilename(title="Save the PC save game as", initialfile="blursave",
                                         initialdir=os.path.dirname(self.path or DEFAULT_SAVE) or None)
        if not p:
            return
        if game_running() and not messagebox.askyesno(
                "Game running", "Blur is running. The game overwrites the save game when it exits and when it loads. "
                                "Create the save game anyway?"):
            return
        try:
            data, _ = bs.extend_campaign(bs.read_save(NEW_SAVE))
            doc = bs.make_doc(data)
            what = ps3save.apply(doc, ps3)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Import PS3", str(e))
            return
        doc.setdefault("campaign", [])
        self.path, self.doc, self.dirty = None, doc, False
        self.veh_by_id = {v["id"]: v for v in self.doc["vehicles"]}
        self._texts()
        if not self.write(p):                                      # an existing file is backed up first (editor_backups)
            return
        self.veh_by_id = {v["id"]: v for v in self.doc["vehicles"]}
        self._texts()
        self.refresh_all()
        self.load_graphics()
        if self.doc["campaign"]:
            self.tier_tv.selection_set("tier0")
        self.set_status("PS3 save game imported: %s (%s). Paint jobs and settings are not taken over." % (p, what))

    def export_ps3(self):
        """writes the open save game as a PS3 save game (AMAXSAVE, NOT encrypted: the form RPCS3 reads). A PS3 save game is the template: its values
        are replaced by the ones of the open save game, everything the editor does not know stays as in the template"""
        if not self.doc:
            return
        tmpl = filedialog.askopenfilename(title="PS3 save game as the template (AMAXSAVE, encrypted with PARAM.PFD or not)",
                                          filetypes=[("PS3 save game", "AMAXSAVE"), ("All files", "*.*")])
        if not tmpl:
            return
        out = filedialog.askdirectory(title="Folder for the PS3 save game (RPCS3: dev_hdd0/home/00000001/savedata/BLES00759-AUTO-)", mustexist=False)
        if not out:
            return
        doc = copy.deepcopy(self.doc)
        rules.normalise(doc)
        try:
            data = ps3save.container(ps3save.export(doc, tmpl))
            os.makedirs(out, exist_ok=True)
            target = os.path.join(out, "AMAXSAVE")
            if os.path.exists(target):                                  # an existing file is kept next to it
                shutil.copy2(target, target + ".old_" + time.strftime("%Y%m%d_%H%M%S"))
            with open(target, "wb") as f:
                f.write(data)
            for name in ("PARAM.SFO", "ICON0.PNG", "PIC1.PNG"):          # the rest of a save folder comes from the template's folder
                src = os.path.join(os.path.dirname(tmpl), name)
                if os.path.exists(src) and not os.path.exists(os.path.join(out, name)):
                    shutil.copy2(src, os.path.join(out, name))
            ps3save.read(target)                                         # reads it back: proves the file is complete
        except (Exception, SystemExit) as e:
            messagebox.showerror("Export PS3", str(e))
            return
        self.set_status("PS3 save game written: %s (not encrypted, no PARAM.PFD: for RPCS3; settings and paint jobs are not exported)" % target)

    def reload(self):
        if self.path and self.confirm_discard():
            self.load(self.path)

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno("Unsaved changes", "Discard changes?")

    def load(self, path):
        try:
            data = bs.read_save(path)
            doc = bs.make_doc(data)
            filled = 0
            if not doc.get("campaign"):                  # a new profile: the records are there but not initialised, the editor does what the game does
                data, filled = bs.extend_campaign(data)
                if filled:
                    doc = bs.make_doc(data)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Open failed", str(e))
            return
        if "profile" not in doc or not doc.get("vehicles"):
            messagebox.showerror("Open failed", "This is not a Blur save game that can be read.")
            return
        doc.setdefault("campaign", [])                   # no campaign records at all: the Career tab shows a note
        self.path, self.doc, self.dirty = path, doc, bool(filled)
        self.file_lbl.config(text=path)
        self.veh_by_id = {v["id"]: v for v in self.doc["vehicles"]}
        self._texts()
        self.refresh_all()
        self.load_graphics()
        if self.doc["campaign"]:
            self.tier_tv.selection_set("tier0")
        self.set_status("Loaded: %s" % path + ("; the campaign data of this new profile were initialised (as the game does when the campaign is "
                                              "played), save to keep them" if filled else ""))

    def _texts(self):
        self.vtext = {v["id"]: DISPLAY["vehicles"].get(v["id"], v["name"]) for v in self.doc["vehicles"]}
        self.short = {v["id"]: blurdisplay.SHORT_NAMES.get(v["name"], self.vtext[v["id"]]) for v in self.doc["vehicles"]}   # gallery names
        self.last_names = sorted(self.vtext.values())
        self.last_cb.config(values=self.last_names)

    def write(self, path):
        doc = copy.deepcopy(self.doc)
        changes = rules.normalise(doc)
        try:
            data = bs.build(doc)
        except (Exception, SystemExit) as e:
            messagebox.showerror("Save failed", str(e))
            return False
        bdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), "editor_backups")
        backup = None
        if os.path.exists(path):
            os.makedirs(bdir, exist_ok=True)
            backup = os.path.join(bdir, "blursave_%s" % time.strftime("%Y%m%d_%H%M%S"))
            shutil.copy2(path, backup)
        bs.write_save(path, data)
        again = bs.read_save(path)
        if again != data:
            messagebox.showerror("Save", "Verification after writing failed. Backup: %s" % backup)
            return False
        self.doc = bs.make_doc(data)
        self.doc.setdefault("campaign", [])
        self.path, self.dirty = path, False
        self.file_lbl.config(text=path)
        self.refresh_all()
        self.set_status("Saved (%d corrections the game would make were applied)%s" % (
            len(changes), "; backup: " + backup if backup else ""))
        return True

    def save(self):
        if not self.doc:
            return
        if game_running() and not messagebox.askyesno(
                "Game running", "Blur is running. The game overwrites the save game when it exits and when it loads.\n"
                               "Save anyway?"):
            return
        self.write(self.path)

    def save_as(self):
        if not self.doc:
            return
        p = filedialog.asksaveasfilename(title="Save as", initialfile="blursave",
                                         initialdir=os.path.dirname(self.path or DEFAULT_SAVE) or None)
        if p:
            self.write(p)

    def on_close(self):
        if self.confirm_discard():
            self.destroy()

    def set_status(self, text):
        self.status.config(text=text)

    def touch(self):
        self.dirty = True
        self.refresh_all()
        self.set_status("Changed, not saved")

    # ---------- refresh ----------
    def refresh_all(self):
        if not self.doc:
            return
        self._busy = True
        p = self.doc["profile"]
        fans = p["fans"]["value"]
        self.fans_var.set(num(fans))
        rank, _, nxt = rules.rank_for_fans(fans)
        cur_fans = next(x["fans"] for x in rules.RANKS if x["rank"] == rank)
        self.rank_var.set("Fan Status %d  (from %s fans)" % (rank, num(cur_fans)) if rank else "")
        self.level_lbl.config(text="Fan Status %d%s" % (rank, "" if nxt is None else "  (next at %s fans)" % num(nxt)))
        m = p.get("mod")
        if m:
            name = MODS.get(m["value"])
            self.mod_var.set(mod_text(m["value"]))
            self.mod_note.config(text="" if name or m["value"] == 255 else MOD_NOTE)
            img = self.icon("mods", name) if name else None
            self.mod_icon.config(image=img or "")
        else:
            self.mod_cb.config(state="disabled")
        lv = p.get("last_vehicle")
        self.last_cb.config(state="readonly" if lv else "disabled")
        if lv:
            self.last_var.set(self.vtext.get(lv["id"], lv["name"]))
            self.last_pic.config(image=self.icon("seen", lv["name"]) or "")
        else:
            self.last_var.set("")
            self.last_pic.config(image="")
        total = rules.total_lights(self.doc)
        self.lights_lbl.config(text="%d of 450 (total of all events)" % total)
        cur = cur_fans
        self.header.set(lights="%d/450" % total, rank=rank, name=os.path.basename(self.path or "") and "Save: %s" % os.path.basename(self.path),
                        progress=1.0 if nxt is None else (fans - cur) / max(1, nxt - cur))
        self.refresh_tiers()
        self.refresh_vehicles()
        self.refresh_stickers()
        self.refresh_settings()
        self.refresh_preview()
        self._busy = False

    def refresh_tiers(self):
        if not self.doc["campaign"]:
            self.ev_tv.set_items([], "This save game has no campaign data yet. The game creates it when you play the campaign.")
        sel = self.tier_tv.selection()
        self.tier_tv.delete(*self.tier_tv.get_children())
        total = rules.total_lights(self.doc)
        for i, (t, tdef) in enumerate(zip(self.doc["campaign"], rules.CAMPAIGN)):
            locked = total < tdef["lights_needed_to_unlock"]
            self.tier_tv.insert("", "end", iid="tier%d" % i, text="%d. %s" % (i + 1, DISPLAY["tiers"][i]),
                                values=(DISPLAY["bosses"][i], "%d/50" % rules.tier_lights(t, tdef),
                                        "at %d lights" % tdef["lights_needed_to_unlock"] if locked else
                                        ("Rival defeated" if t["boss"]["status"][1] else "Unlocked")))
        if sel and self.tier_tv.exists(sel[0]):
            self.tier_tv.selection_set(sel[0])
        self.select_tier(keep=True)

    def cur_tier(self):
        sel = self.tier_tv.selection()
        return int(sel[0][4:]) if sel else None

    def select_tier(self, keep=False):
        i = self.cur_tier()
        sel_ev = self.ev_tv.selection()
        if i is None:
            return
        t, tdef = self.doc["campaign"][i], rules.CAMPAIGN[i]
        tier_locked = rules.total_lights(self.doc) < tdef["lights_needed_to_unlock"]      # the whole group is still closed
        items = []
        for j, (ev, edef) in enumerate(zip(t["events"], tdef["events"])):
            st, place, diff, tun = ev["flags"]
            boss = edef["type"] == "BossEvent"
            info = EVENTS.get("T%dE%d" % (i + 1, j), {})
            lights = rules.event_lights(ev, edef)
            fan = int(not boss and lights > 0 and ev["info_a"] >= edef["fan_par"])
            run = int(not boss and lights > 0 and bool(tun))
            if st == 0 or tier_locked:
                status = "Locked"
            elif st == 1:
                status = "Unlocked"
            else:
                status = "No podium" if place == 0 else "%s – %s" % (PLACES.get(place, "?"), DIFFS.get(diff, "?"))
            items.append({"iid": "ev%d" % j, "city": info.get("city", "?"), "landmark": info.get("icon", ""),
                          "kind": info.get("kind", DISPLAY["event_kinds"].get(edef["type"], edef["type"])), "status": status,
                          "locked": st == 0 or tier_locked, "coins_max": 8 if boss else 5, "coins": max(0, lights - fan - run),
                          "fan": fan, "run": run, "place": place if place in (1, 2, 3) else 3, "new": st == 1,
                          "diff": diff if st in (1, 2) and diff in (1, 2, 3) and not tier_locked else 0,     # not for a locked event; else if one is saved
                          "number": j + 1})
        self.ev_tv.set_items(items)
        if sel_ev:
            self.ev_tv.selection_set(sel_ev[0])
        elif not keep:
            self.ev_tv.selection_set("ev0")
        self.select_event()
        b = t["boss"]
        self.boss_box.config(text="Rival Demands – %s" % DISPLAY["bosses"][i])
        for k in range(4):
            lbl, tgt = self.b_lbls[k]
            lbl.config(text=demand_text(tdef, k))
            tgt.config(text="of %s" % num(b["targets"][k]))
            self.b_vars[k].set(str(int(b["counters"][k])))
        met = rules.boss_met(t)
        self.boss_info.config(text="Demands %s · Rival %s" % ("met" if met else "open",
                                                              "defeated" if b["status"][1] else "not defeated"))

    def cur_event(self):
        sel = self.ev_tv.selection()
        return int(sel[0][2:]) if sel and self.cur_tier() is not None else None

    def select_event(self):
        i, j = self.cur_tier(), self.cur_event()
        if i is None or j is None:
            return
        ev = self.doc["campaign"][i]["events"][j]
        st, place, diff, tun = ev["flags"]
        self.e_status.set(STATUS[st] if st < 3 else STATUS[0])
        self.e_place.set(PLACES.get(place, PLACES[0]))
        self.e_diff.set(DIFFS.get(diff, DIFFS[0]))
        self.e_tunnel.set(int(bool(tun)))
        self.e_fans.set(str(ev["info_a"]))
        car = self.veh_by_id.get(ev["info_car_id"])
        self.e_car.config(text=self.vtext[car["id"]] if car else "")

    def refresh_vehicles(self):
        sel = self.veh_tv.selection()
        order = blurdisplay.GALLERY_ORDER
        named = {m for models in order.values() for m in models}
        by_model = {}
        for v in self.doc["vehicles"]:
            by_model.setdefault(v["name"], []).append(v)
        groups = []
        for cls in "ABCD":
            cars = [v for m in order[cls] for v in by_model.get(m, [])]                 # the game's order, then the other cars
            cars += sorted((v for v in self.doc["vehicles"] if v["class"] == cls and v["name"] not in named),
                           key=lambda v: self.short[v["id"]])
            items = []
            for v in cars:
                kind = {0: "locked", 1: "new", 2: "seen"}[v["state"]]                  # not awarded: grey; new: with the triangle
                paint = self._paint_colour_of(v["id"], v["state"] == 0)
                items.append((v["id"], self.icon(kind, v["name"]), self.short[v["id"]], v["state"] == 0, paint,
                              PAINT_SHIFT if paint else 0))                      # only the colour hexagon shifts the car (not the "new" triangle)
            groups.append((self.icon("classes", cls) or cls, items))
        self.veh_tv.set_groups(groups)
        self.veh_tv.selection_set(*sel)
        self._car_info()

    def refresh_preview(self):
        d = copy.deepcopy(self.doc)
        ch = rules.normalise(d)
        self.prev_txt.config(state="normal")
        self.prev_txt.delete("1.0", "end")
        if not ch:
            self.prev_txt.insert("end", "The game would not change anything.")
        for s, t in ch:
            self.prev_txt.insert("end", "• %s\n" % t, s)
        self.prev_txt.config(state="disabled")

    # ---------- profile actions ----------
    def apply_fans(self):
        if self._busy or not self.doc:
            return
        try:
            v = int(self.fans_var.get().replace(",", "").replace(".", "").replace(" ", ""))
            assert 0 <= v <= 4_000_000_000
        except (ValueError, AssertionError):
            self.refresh_all()
            return
        if v != self.doc["profile"]["fans"]["value"]:
            self.doc["profile"]["fans"]["value"] = v
            self.touch()

    def apply_rank(self, _=None):
        r = int(self.rank_var.get().split()[2])
        self.doc["profile"]["fans"]["value"] = [x["fans"] for x in rules.RANKS if x["rank"] == r][0]
        self.touch()

    def apply_mod(self, _=None):
        n = int(self.mod_var.get().rsplit("(", 1)[1].rstrip(")"))
        self.doc["profile"]["mod"]["value"] = n
        self.mod_note.config(text="" if n in MODS or n == 255 else MOD_NOTE)
        self.mod_icon.config(image=(self.icon("mods", MODS[n]) if n in MODS else None) or "")
        self.touch()

    def apply_last(self, _=None):
        name = self.last_var.get()
        uid = next(k for k, t in self.vtext.items() if t == name)
        lv = self.doc["profile"]["last_vehicle"]
        lv["id"] = uid
        lv["name"] = self.veh_by_id[uid]["name"]
        self.touch()

    # ---------- events ----------
    def event_apply(self):
        i, j = self.cur_tier(), self.cur_event()
        if i is None or j is None:
            return
        ev = self.doc["campaign"][i]["events"][j]
        try:
            fans = int(self.e_fans.get().replace(",", "").replace(".", ""))
        except ValueError:
            messagebox.showerror("Fans", "Please enter a whole number.")
            return
        inv = lambda d, s: next(k for k, v in d.items() if v == s)
        ev["flags"] = [STATUS.index(self.e_status.get()), inv(PLACES, self.e_place.get()),
                       inv(DIFFS, self.e_diff.get()), int(self.e_tunnel.get())]
        ev["info_a"] = fans
        self.touch()

    def event_best(self):
        i, j = self.cur_tier(), self.cur_event()
        if i is not None and j is not None:
            self._best(i, j)
            self.touch()

    def _best(self, i, j):
        ev = self.doc["campaign"][i]["events"][j]
        edef = rules.CAMPAIGN[i]["events"][j]
        boss = edef["type"] == "BossEvent"
        ev["flags"] = [2, 3, 3, 0 if boss else 1]
        ev["info_a"] = max(ev["info_a"], edef["fan_par"] or 1000)
        if ev["info_car_id"] == "00000000":                  # the car of the result: the one driven last; a new profile has none, then a car of the list
            lv = self.doc["profile"].get("last_vehicle")
            ev["info_car_id"] = lv["id"] if lv else next((v["id"] for v in self.doc["vehicles"] if v["state"] != 0), self.doc["vehicles"][0]["id"])

    def event_reset(self):
        i, j = self.cur_tier(), self.cur_event()
        if i is not None and j is not None:
            self._reset(i, j)
            self.touch()

    def _reset(self, i, j):
        ev = self.doc["campaign"][i]["events"][j]
        ev["flags"] = [0, 0, 0, 0]
        ev["info_a"], ev["info_float"], ev["info_car_id"] = 0, 0.0, "00000000"

    # ---------- boss / tier ----------
    def boss_apply(self):
        if self._busy:
            return
        i = self.cur_tier()
        if i is None:
            return
        b = self.doc["campaign"][i]["boss"]
        new = list(b["counters"])
        for k in range(4):
            s = self.b_vars[k].get().strip()
            if s.isdigit():
                new[k] = float(s) if b["float"][k] else int(s)
        if new != b["counters"]:
            b["counters"] = new
            self.touch()

    def boss_meet(self):
        i = self.cur_tier()
        if i is not None:
            b = self.doc["campaign"][i]["boss"]
            self._meet(b)
            self.touch()

    def _meet(self, b):
        """every demand counter at least at its target (float counters stay floats: the drift demand counts in float32)"""
        b["counters"] = [float(max(c, g)) if f else int(max(c, g)) for c, g, f in zip(b["counters"], b["targets"], b["float"])]

    def boss_reset(self):
        i = self.cur_tier()
        if i is not None:
            self.doc["campaign"][i]["boss"]["counters"] = [0, 0, 0, 0]
            self.touch()

    def boss_win(self):
        i = self.cur_tier()
        if i is not None:
            self.boss_meet()
            self._best(i, 6)
            self.touch()

    def tier_complete(self):
        i = self.cur_tier()
        if i is None:
            return
        for j in range(6):
            self._best(i, j)
        self._meet(self.doc["campaign"][i]["boss"])
        self._best(i, 6)
        self.touch()

    def tier_reset(self):
        i = self.cur_tier()
        if i is None:
            return
        for j in range(7):
            self._reset(i, j)
        self.doc["campaign"][i]["boss"]["counters"] = [0, 0, 0, 0]
        self.touch()

    # ---------- vehicles ----------
    def _selected_vehicles(self):
        return [self.veh_by_id[s] for s in self.veh_tv.selection()]

    def veh_set(self, state):
        for v in self._selected_vehicles():
            if v["state"] != 0 or state == 2:
                v["state"] = state
        self.touch()

    def veh_all_seen(self):
        for v in self.doc["vehicles"]:
            if v["state"] != 0:
                v["state"] = 2
        self.touch()


def selftest(path):
    """no window interaction: load, edit, save to a temp file and read back"""
    app = Editor(path)
    app.withdraw()
    d0 = copy.deepcopy(app.doc)
    app.tier_tv.selection_set("tier3")
    app.update()
    app.tier_complete()
    app.doc["profile"]["fans"]["value"] = 90000
    app.veh_all_seen()
    painted = None
    if "paints" in app.doc:
        ok = sorted(bs.load_paints()[1] - {int(e["vehicle"], 16) for e in app.doc["paints"]["entries"]})
        painted = "%08x" % ok[0]
        app.paint_set(painted, 4, 3, 5)
        app.paint_set(app.doc["paints"]["entries"][0]["vehicle"], 1, 7, 4)
        gone = app.doc["paints"]["entries"][-2]["vehicle"] if len(app.doc["paints"]["entries"]) > 2 else None
        if gone:
            app.veh_tv.selection_set(gone)
            app.update()
            app.paint_remove()
        candy = "%08x" % ok[1]
        app.paint_set(candy, 4, 4, 5, "C_")
        rest = [v for v in app.doc["vehicles"] if int(v["id"], 16) not in bs.load_paints()[1]
                and v["id"] not in {e["vehicle"] for e in app.doc["paints"]["entries"]}][0]["id"]   # a car with no respray
        app.veh_tv.selection_set(rest)
        app.update()
        app.pt_finish.set(FINISH_NAMES[2])
        app.pt_row.set("4")
        app.pt_col.set("4")
        app.paint_apply()
    stk = None
    if "stats" in app.doc:
        a = next(g["achievement_id"] for g in STICKERS if g["index"] == 94)         # Incoming!
        app.stk_tv.selection_set("stk%d" % a)
        app.update()
        app.g_rows[0][1].set("250")
        app.stat_apply(0)
        app.stat_reach(False)
        stk = {g["index"]: g["goal"] for g in STICKERS if g["achievement_id"] == a}
    if "settings" in app.doc:
        app.doc["settings"]["audio"]["sfx"]["value"] = 4
        app.doc["settings"]["audio"]["room_size"]["value"] = 2
        app.doc["settings"]["controller_layout"]["value"] = 2
        app.doc["settings"]["keyboard_layout"]["value"] = 0
        app.doc["settings"]["region_rule"]["value"] = 2
        app.doc["settings"]["brightness"]["value"] = 8
        app.doc["settings"]["difficulty"]["value"] = 2
    out = os.path.join(os.environ.get("TEMP", "."), "bs_selftest", "save", "blursave")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    assert app.write(out)
    again = bs.make_doc(bs.read_save(out))
    t4 = again["campaign"][3]
    assert t4["boss"]["status"] == [1, 1, 174, 0], t4["boss"]["status"]
    assert all(e["flags"][0] == 2 for e in t4["events"]), [e["flags"] for e in t4["events"]]
    assert again["profile"]["fan_level"]["value"] == rules.rank_for_fans(90000)[0]
    if painted:
        pe = {e["vehicle"]: e for e in again["paints"]["entries"]}
        assert (pe[painted]["index"], bs.paint_name(4, pe[painted]["index"])) == (13, "R3C5a"), pe[painted]
        assert pe[app.doc["paints"]["entries"][0]["vehicle"]]["index"] == 36
        assert len(again["paints"]["entries"]) == len(d0["paints"]["entries"]) + 3 - (1 if gone else 0)
        assert pe[rest]["index"] == 18 and bs.paint_finish(int(pe[rest]["paint"], 16)) == "C_", pe[rest]
        assert (pe[candy]["index"], bs.paint_finish(int(pe[candy]["paint"], 16)),
                bs.paint_name(4, pe[candy]["index"], "C_")) == (19, "C_", "C_R4C5a"), pe[candy]
        assert not gone or gone not in pe
        assert bs.build(again) == bs.read_save(out)
    if stk:
        assert all(again["stats"]["entries"][i]["value"] == g for i, g in stk.items()), stk
        assert all(e["value"] == o["value"] for e, o in zip(again["stats"]["entries"], app.doc["stats"]["entries"]))
    if "settings" in app.doc:
        st = again["settings"]
        assert (st["audio"]["sfx"]["value"], st["audio"]["room_size"]["value"], st["controller_layout"]["value"],
                st["keyboard_layout"]["value"], st["region_rule"]["value"],
                st["brightness"]["value"], st["difficulty"]["value"]) == (4, 2, 2, 0, 2, 8, 2), st
    fresh, n = bs.extend_campaign(bs.read_save(NEW_SAVE))                  # a new profile gets its campaign records initialised
    nd = bs.make_doc(fresh)
    assert n and len(nd["campaign"]) == 9 and all(t["boss"]["status"][2] == 174 for t in nd["campaign"]), n
    assert [t["state"]["value"] for t in nd["campaign"]] == [1] + [0] * 8 and bs.build(nd) == fresh
    assert bs.extend_campaign(fresh)[1] == 0                                   # and nothing more is changed the second time
    ps3_dir = os.path.join(os.path.dirname(HERE), "ps3_saves", "SAVEDATA", "BLES00759-AUTO-")
    if os.path.isdir(ps3_dir):                                             # a PS3 save game imported into the template
        base = bs.make_doc(fresh)
        ps = ps3save.read(os.path.join(ps3_dir, "AMAXSAVE"))
        ps3save.apply(base, ps)
        imp = bs.make_doc(bs.build(base))
        assert imp["profile"]["fan_level"]["value"] == ps["fan_level"] and imp["profile"]["fans"]["value"] == ps["fans"]
        assert [[e["flags"] for e in t["events"]] for t in imp["campaign"]] == [[e["flags"] for e in t["events"]] for t in
                                                                          [{"events": s["events"]} for s in ps["campaign"]]]
        assert {v["id"]: v["state"] for v in imp["vehicles"]} == ps["vehicles"]
    if os.path.isdir(ps3_dir):                                             # and back: a PC save game as a PS3 save game
        T = os.path.join(ps3_dir, "AMAXSAVE")
        assert ps3save.export(bs.make_doc(bs.build(base)), T) == ps3save.payload(T)         # the imported one gives the template back, byte for byte
        tmp = os.path.join(os.environ.get("TEMP", "."), "selftest_AMAXSAVE")
        with open(tmp, "wb") as f:
            f.write(ps3save.container(ps3save.export(app.doc, T)))
        back = ps3save.read(tmp)
        assert back["fan_level"] == app.doc["profile"]["fan_level"]["value"] and back["fans"] == app.doc["profile"]["fans"]["value"]
        assert [[e["flags"] for e in t["events"]] for t in back["campaign"]] == [[e["flags"] for e in t["events"]] for t in app.doc["campaign"]]
        os.remove(tmp)
    xb = os.path.join(os.path.dirname(HERE), "xbox360_save", "41560845", "00000001", "AMAXSAVE")
    if os.path.exists(xb):                                                 # an Xbox 360 package
        x = ps3save.read(xb)
        assert x["fan_level"] == 25 and x["fans"] == 193498 and len(x["campaign"]) == 9
        ps3save.apply(bs.make_doc(fresh), x)
    print("selftest ok: group 4 completed, fans 90000 -> level %d, lights %d" % (
        again["profile"]["fan_level"]["value"], rules.total_lights(again)))
    app.destroy()


if __name__ == "__main__":
    if sys.stdout is None:                      # windowed .exe: no console, so printing must not fail
        sys.stdout = sys.stderr = open(os.devnull, "w")
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2])
    else:
        args = [a for a in sys.argv[1:] if not a.startswith("--tab=")]
        tab = next((int(a[6:]) for a in sys.argv[1:] if a.startswith("--tab=")), 0)
        Editor(args[0] if args else None, tab).mainloop()
