# -*- coding: utf-8 -*-
# HabZone (EDMC 6.x) – slim, same features:
# UI + k/M + tooltips + Recalc + persistence + auto-restore via journal + optional verbose logging

import glob, json, logging, os, sys
import tkinter as tk

import myNotebook as nb
from config import config
from l10n import Locale

VERSION = "1.20-edmc6-slim"

LOG = logging.getLogger("HabZone")

CFG_ABBREV = "habzone_abbrev"
CFG_DEBUG  = "habzone_debug"
CFG_LAST_SYSTEM = "habzone_last_system"
CFG_LAST_R      = "habzone_last_star_r"
CFG_LAST_T      = "habzone_last_star_t"

LS = 300000000.0
# (name, inner_temp(K) or 0, outer_temp(K))
WORLDS = [
    ("Metal-Rich",      0.0, 1103.0),
    ("Earth-Like",    278.0,  227.0),
    ("Water",         307.0,  156.0),
    ("Ammonia",       193.0,  117.0),
    ("Terraformable", 315.0,  223.0),
]

this = sys.modules[__name__]
this.frame = None
this.rows = []  # list of dicts: {"label","near","dash","far","unit"}
this.abbrev = True
this.last_system = ""
this.last_r = None
this.last_t = None
this.cur_system = ""
this.restored = False


# ----------------- config / logging -----------------
def cfg(key, default=""):
    try:
        v = config.get(key)
        return default if v in (None, "") else v
    except Exception:
        return default

def cfgb(key, default=False):
    try:
        return bool(int(cfg(key, "1" if default else "0")))
    except Exception:
        return default

def cfgf(key):
    try:
        return float(cfg(key, ""))
    except Exception:
        return None

def cfg_set(key, value):
    config.set(key, str(value))

def setup_logging():
    # default quiet: WARNING. verbose: INFO
    LOG.setLevel(logging.INFO if cfgb(CFG_DEBUG, False) else logging.WARNING)

# ----------------- persistence -----------------
def load_persist():
    this.last_system = cfg(CFG_LAST_SYSTEM, "")
    this.last_r = cfgf(CFG_LAST_R)
    this.last_t = cfgf(CFG_LAST_T)

def save_persist(system, r, t):
    system = system or ""
    cfg_set(CFG_LAST_SYSTEM, system)
    cfg_set(CFG_LAST_R, float(r))
    cfg_set(CFG_LAST_T, float(t))
    this.last_system, this.last_r, this.last_t = system, float(r), float(t)

# ----------------- journal parse (startup system) -----------------
def journal_dir():
    jd = cfg("journaldir", "")
    if jd and os.path.isdir(jd):
        return jd
    return os.path.join(os.path.expanduser("~"), "Saved Games", "Frontier Developments", "Elite Dangerous")

def system_from_journal():
    jd = journal_dir()
    files = sorted(glob.glob(os.path.join(jd, "Journal.*.log")), key=os.path.getmtime, reverse=True)
    if not files:
        return ""
    path = files[0]
    try:
        # last ~5000 lines is enough and still fast
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            tail = f.readlines()[-5000:]
        for line in reversed(tail):
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") in ("Location", "FSDJump"):
                return e.get("StarSystem", "") or ""
    except Exception:
        LOG.exception("journal parse failed")
    return ""

# ----------------- ui helpers -----------------
def fmt_ls(v):
    v = int(v)
    if this.abbrev and v >= 10_000:
        if v >= 1_000_000:
            return Locale.string_from_number(v / 1_000_000, 2) + "M"
        return Locale.string_from_number(v / 1_000, 1) + "k"
    return Locale.string_from_number(v, 0)

class Tip:
    def __init__(self, w, get_text):
        self.w, self.get_text, self.top = w, get_text, None
        w.bind("<Enter>", self.show, add="+")
        w.bind("<Leave>", self.hide, add="+")
        w.bind("<Motion>", self.move, add="+")

    def show(self, *_):
        if self.top:
            return
        txt = self.get_text() or ""
        if not txt:
            return
        self.top = tk.Toplevel(self.w)
        self.top.wm_overrideredirect(True)
        tk.Label(self.top, text=txt, relief="solid", borderwidth=1,
                 font=("TkDefaultFont", 9), padx=6, pady=3).pack()
        self.move()

    def move(self, *_):
        if not self.top:
            return
        x = self.w.winfo_pointerx() + 12
        y = self.w.winfo_pointery() + 12
        self.top.wm_geometry(f"+{x}+{y}")

    def hide(self, *_):
        if self.top:
            self.top.destroy()
            self.top = None

# ----------------- math / compute -----------------
def dfort(r, t, target):
    # distance in ls
    return (((r*r) * (t**4) / (4 * (target**4))) ** 0.5) / LS

def compute(r, t):
    r = float(r); t = float(t)
    for i, (name, hi, lo) in enumerate(WORLDS):
        row = this.rows[i]
        far = int(dfort(r, t, lo) + 0.5)
        rad = int(r / LS + 0.5)

        row["near"]._tt = row["far"]._tt = ""
        if far <= rad:
            row["near"]["text"] = ""
            row["dash"]["text"] = "×"
            row["far"]["text"]  = ""
            row["unit"]["text"] = ""
            continue

        near = rad if hi <= 0 else int(dfort(r, t, hi) + 0.5)
        row["near"]["text"] = fmt_ls(near)
        row["dash"]["text"] = "–"
        row["far"]["text"]  = fmt_ls(far)
        row["unit"]["text"] = "ls"

        row["near"]._tt = "Exakt: %s ls" % Locale.string_from_number(near, 0)
        row["far"]._tt  = "Exakt: %s ls" % Locale.string_from_number(far, 0)

# ----------------- restore -----------------
def restore_if_possible():
    if this.restored:
        return
    if this.cur_system and this.cur_system == this.last_system and this.last_r and this.last_t:
        compute(this.last_r, this.last_t)
        this.restored = True

def schedule_restore():
    if not this.frame:
        return
    for ms in (250, 1000, 2500):
        this.frame.after(ms, restore_if_possible)

def recalc():
    if this.last_r and this.last_t:
        compute(this.last_r, this.last_t)

# ----------------- EDMC entry points -----------------
def plugin_start3(_): return "HabZone"
def plugin_start(): return "HabZone"

def plugin_app(parent):
    this.frame = tk.Frame(parent)

    setup_logging()
    load_persist()
    this.abbrev = cfgb(CFG_ABBREV, True)

    this.cur_system = system_from_journal()

    # stable columns
    this.frame.grid_columnconfigure(0, minsize=115)
    this.frame.grid_columnconfigure(2, minsize=70)
    this.frame.grid_columnconfigure(3, minsize=18)
    this.frame.grid_columnconfigure(4, minsize=70)
    this.frame.grid_columnconfigure(5, minsize=18)

    tk.Button(this.frame, text="Recalc", command=recalc).grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=(0, 4))

    font = ("TkDefaultFont", 9)
    for idx, (name, _hi, _lo) in enumerate(WORLDS, start=1):
        lbl  = tk.Label(this.frame, text=name + ":", anchor="w", font=font)
        near = tk.Label(this.frame, text="", anchor="e", font=font)
        dash = tk.Label(this.frame, text="", anchor="center", font=font)
        far  = tk.Label(this.frame, text="", anchor="e", font=font)
        unit = tk.Label(this.frame, text="", anchor="w", font=font)

        lbl.grid(row=idx, column=0, sticky=tk.W, padx=(0, 8))
        near.grid(row=idx, column=2, sticky=tk.E, padx=(0, 6))
        dash.grid(row=idx, column=3, sticky=tk.E, padx=(0, 6))
        far.grid(row=idx, column=4, sticky=tk.E, padx=(0, 6))
        unit.grid(row=idx, column=5, sticky=tk.W)

        near._tt = far._tt = ""
        Tip(near, lambda w=near: getattr(w, "_tt", ""))
        Tip(far,  lambda w=far:  getattr(w, "_tt", ""))

        this.rows.append({"label": lbl, "near": near, "dash": dash, "far": far, "unit": unit})

    schedule_restore()
    return this.frame

def plugin_prefs(parent, *_):
    f = nb.Frame(parent)

    this._abbrev_var = tk.IntVar(value=1 if cfgb(CFG_ABBREV, True) else 0)
    nb.Checkbutton(f, text="Abbreviate large distances (k/M)", variable=this._abbrev_var).grid(padx=10, pady=(10, 2), sticky=tk.W)

    this._debug_var = tk.IntVar(value=1 if cfgb(CFG_DEBUG, False) else 0)
    nb.Checkbutton(f, text="Verbose logging (for troubleshooting)", variable=this._debug_var).grid(padx=10, pady=2, sticky=tk.W)

    nb.Label(f, text="Version %s" % VERSION).grid(padx=10, pady=(10, 10), sticky=tk.W)
    return f

def prefs_changed(*_):
    cfg_set(CFG_ABBREV, "1" if this._abbrev_var.get() else "0")
    cfg_set(CFG_DEBUG,  "1" if this._debug_var.get() else "0")
    this.abbrev = bool(this._abbrev_var.get())
    setup_logging()
    # apply immediately
    restore_if_possible()
    recalc()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    ev = entry.get("event")
    if ev == "Scan":
        try:
            if float(entry.get("DistanceFromArrivalLS", 0.0)) == 0.0:
                r = float(entry["Radius"]); t = float(entry["SurfaceTemperature"])
                sysname = entry.get("StarSystem") or system or ""
                save_persist(sysname, r, t)
                compute(r, t)
        except Exception:
            LOG.exception("scan handling failed")
    elif ev in ("Location", "FSDJump"):
        sysname = entry.get("StarSystem") or system or ""
        if sysname:
            this.cur_system = sysname
        if ev == "FSDJump":
            this.restored = False
