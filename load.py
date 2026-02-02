# -*- coding: utf-8 -*-
#
# HabZone (EDMC 6.x / Python 3.x)
# v1.23:
# - Auto-rescan on EDMC startup (Journal restore + optional EDSM refresh)
# - manual "Rescan" button
# - V2 formatting: no decimals, optional k/M abbreviation + tooltip shows exact value when abbreviated
# - Python 3 migration: plugin_start3, tkinter, urllib.parse.quote, config.get_int, Locale.string_from_number
#

from __future__ import print_function

from collections import defaultdict
import glob
import json
import os
import requests
import sys
import threading
from urllib.parse import quote

import tkinter as tk
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb

if __debug__:
    from traceback import print_exc

from config import config
from l10n import Locale

VERSION = "1.23"

SETTING_DEFAULT = 0x0002    # Earth-like
SETTING_EDSM    = 0x1000
SETTING_NONE    = 0xffff

CFG_ABBREV = "habzone_abbrev"  # 1/0

WORLDS = [
    # Type            Black-body temp range   EDSM description key
    ('Metal-Rich',      0,    1103.0, 'Metal-rich body'),
    ('Earth-Like',    278.0,   227.0, 'Earth-like world'),
    ('Water',         307.0,   156.0, 'Water world'),
    ('Ammonia',       193.0,   117.0, 'Ammonia world'),
    ('Terraformable', 315.0,   223.0, 'terraformable'),
]

LS = 300000000.0    # 1 ls in m (approx)

this = sys.modules[__name__]
this.frame = None
this.worlds = []
this.edsm_session = None
this.edsm_data = None

# Used during preferences
this.settings = None
this.edsm_setting = None
this.abbrev_setting = None

# Track last system name for EDSM
this._last_systemname = ""


# -----------------------------
# Journal helpers
# -----------------------------
def _journal_dir():
    try:
        jd = config.get('journaldir')
    except Exception:
        jd = None
    if jd and os.path.isdir(jd):
        return jd
    return os.path.join(
        os.path.expanduser("~"),
        "Saved Games",
        "Frontier Developments",
        "Elite Dangerous",
    )

def _system_from_journal():
    try:
        files = sorted(
            glob.glob(os.path.join(_journal_dir(), "Journal.*.log")),
            key=os.path.getmtime,
            reverse=True
        )
        if not files:
            return ""
        with open(files[0], "r", encoding="utf-8", errors="ignore") as f:
            tail = f.readlines()[-5000:]
        for line in reversed(tail):
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") in ("Location", "FSDJump"):
                return e.get("StarSystem", "") or ""
    except Exception:
        if __debug__:
            print_exc()
    return ""

def _system_from_config():
    try:
        v = config.get('system')
        return v or ""
    except Exception:
        return ""

def _ensure_systemname_best_effort():
    if this._last_systemname:
        return this._last_systemname

    sysname = _system_from_config()
    if sysname:
        this._last_systemname = sysname
        return sysname

    sysname = _system_from_journal()
    if sysname:
        this._last_systemname = sysname
        return sysname

    return ""

def _last_arrival_star_scan_from_journal():
    """Return (radius, temperature) from the most recent arrival-star Scan event."""
    try:
        files = sorted(
            glob.glob(os.path.join(_journal_dir(), "Journal.*.log")),
            key=os.path.getmtime,
            reverse=True
        )
        if not files:
            return (None, None)

        with open(files[0], "r", encoding="utf-8", errors="ignore") as f:
            tail = f.readlines()[-20000:]

        for line in reversed(tail):
            try:
                e = json.loads(line)
            except Exception:
                continue

            if e.get("event") != "Scan":
                continue

            try:
                if float(e.get("DistanceFromArrivalLS", 0.0)) == 0.0:
                    r = float(e.get("Radius"))
                    t = float(e.get("SurfaceTemperature"))
                    return (r, t)
            except Exception:
                continue
    except Exception:
        if __debug__:
            print_exc()

    return (None, None)


# -----------------------------
# Formatting helpers (V2)
# -----------------------------
def _abbrev_enabled():
    try:
        return bool(int(config.get(CFG_ABBREV) or 0))
    except Exception:
        return False

def format_distance(value, abbreviate):
    value = int(value)
    if abbreviate and value >= 10_000:
        if value >= 1_000_000:
            return Locale.string_from_number(value / 1_000_000, 2) + "M"
        return Locale.string_from_number(value / 1_000, 1) + "k"
    return Locale.string_from_number(value, 0)

class SimpleTooltip:
    def __init__(self, widget, text_fn):
        self.widget = widget
        self.text_fn = text_fn
        self.tip = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, *_):
        text = self.text_fn() or ""
        if not text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        tk.Label(
            self.tip,
            text=text,
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=6,
            pady=3,
        ).pack()
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 12
        self.tip.wm_geometry(f"+{x}+{y}")

    def hide(self, *_):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# -----------------------------
# EDMC start
# -----------------------------
def plugin_start():
    return "HabZone"

def plugin_start3(plugin_dir):
    return "HabZone"


def plugin_app(parent):
    this.frame = tk.Frame(parent)
    this.frame.columnconfigure(3, weight=1)
    this.frame.bind('<<HabZoneData>>', edsm_data)

    # Manual rescan button
    tk.Button(this.frame, text="Rescan", command=manual_rescan).grid(
        row=0, column=0, sticky=tk.W, padx=(0, 8)
    )

    # Build rows
    for (name, high, low, subType) in WORLDS:
        lbl = tk.Label(this.frame, text=name + ':')
        edsm = HyperlinkLabel(this.frame)   # original: one link/label
        near = tk.Label(this.frame, anchor=tk.E)
        dash = tk.Label(this.frame)
        far  = tk.Label(this.frame, anchor=tk.E)
        ls   = tk.Label(this.frame)

        near._exact = ""
        far._exact = ""
        SimpleTooltip(near, lambda w=near: w._exact)
        SimpleTooltip(far,  lambda w=far:  w._exact)

        this.worlds.append((lbl, edsm, near, dash, far, ls))

    this.spacer = tk.Frame(this.frame)
    update_visibility()

    # v2.5: Auto-rescan after startup (timing-safe)
    # EDMC can load plugins very early; we try immediately + later.
    def _auto_rescan():
        try:
            manual_rescan()
        except Exception:
            if __debug__:
                print_exc()

    this.frame.after(600, _auto_rescan)
    this.frame.after(2000, _auto_rescan)
    this.frame.after(5000, _auto_rescan)

    return this.frame


def plugin_prefs(parent, cmdr, is_beta):
    frame = nb.Frame(parent)
    nb.Label(frame, text='Display:').grid(row=0, padx=10, pady=(10, 0), sticky=tk.W)

    setting = get_setting()
    this.settings = []
    row = 1
    for (name, high, low, subType) in WORLDS:
        var = tk.IntVar(value=(setting & row) and 1)
        nb.Checkbutton(frame, text=name, variable=var).grid(row=row, padx=10, pady=2, sticky=tk.W)
        this.settings.append(var)
        row *= 2

    nb.Label(frame, text='Elite Dangerous Star Map:').grid(padx=10, pady=(10, 0), sticky=tk.W)
    this.edsm_setting = tk.IntVar(value=(setting & SETTING_EDSM) and 1)
    nb.Checkbutton(
        frame,
        text='Look up system in EDSM database',
        variable=this.edsm_setting
    ).grid(padx=10, pady=2, sticky=tk.W)

    nb.Label(frame, text='Formatting:').grid(padx=10, pady=(10, 0), sticky=tk.W)
    try:
        cur = int(config.get(CFG_ABBREV) or 0)
    except Exception:
        cur = 0
    this.abbrev_setting = tk.IntVar(value=cur)
    nb.Checkbutton(
        frame,
        text='Abbreviate large distances (k/M)',
        variable=this.abbrev_setting
    ).grid(padx=10, pady=2, sticky=tk.W)

    nb.Label(frame, text='Version %s' % VERSION).grid(padx=10, pady=10, sticky=tk.W)
    return frame


def prefs_changed(cmdr, is_beta):
    row = 1
    setting = 0
    for var in this.settings:
        setting += var.get() and row
        row *= 2

    setting += this.edsm_setting.get() and SETTING_EDSM
    config.set('habzone', setting or SETTING_NONE)

    config.set(CFG_ABBREV, "1" if this.abbrev_setting.get() else "0")

    this.settings = None
    this.edsm_setting = None
    this.abbrev_setting = None
    update_visibility()


def journal_entry(cmdr, is_beta, system, station, entry, state):

    if entry.get('event') == 'Scan':
        try:
            if not float(entry.get('DistanceFromArrivalLS', 0.0)):
                r = float(entry['Radius'])
                t = float(entry['SurfaceTemperature'])
                _apply_hz_values(r, t)
        except Exception:
            if __debug__:
                print_exc()
            _clear_hz_with_error()

    elif entry.get('event') == 'FSDJump':
        for (label, edsm, near, dash, far, ls) in this.worlds:
            edsm['text'] = ''
            edsm['url'] = ''
            near['text'] = ''
            dash['text'] = ''
            far['text'] = ''
            ls['text'] = ''
            near._exact = ''
            far._exact = ''

    if entry.get('event') in ['Location', 'FSDJump']:
        this._last_systemname = entry.get('StarSystem') or this._last_systemname

        if get_setting() & SETTING_EDSM and this._last_systemname:
            thread = threading.Thread(target=edsm_worker, name='EDSM worker', args=(this._last_systemname,))
            thread.daemon = True
            thread.start()


def cmdr_data(data, is_beta):
    try:
        if get_setting() & SETTING_EDSM and not data['commander']['docked']:
            sysname = data['lastSystem']['name']
            this._last_systemname = sysname or this._last_systemname
            if this._last_systemname:
                thread = threading.Thread(target=edsm_worker, name='EDSM worker', args=(this._last_systemname,))
                thread.daemon = True
                thread.start()
    except Exception:
        if __debug__:
            print_exc()


# -----------------------------
# Rescan (v2.4/v2.5): restore HZ from journal + optional EDSM refresh
# -----------------------------
def manual_rescan():
    # 1) Restore HabZone distances from journal
    try:
        r, t = _last_arrival_star_scan_from_journal()
        if r and t:
            _apply_hz_values(r, t)
    except Exception:
        if __debug__:
            print_exc()

    # 2) Optional EDSM refresh
    try:
        if get_setting() & SETTING_EDSM:
            sysname = this._last_systemname or _ensure_systemname_best_effort() or ""
            if sysname:
                this._last_systemname = sysname
                thread = threading.Thread(target=edsm_worker, name='EDSM worker', args=(sysname,))
                thread.daemon = True
                thread.start()
    except Exception:
        if __debug__:
            print_exc()


def _apply_hz_values(r, t):
    abbreviate = _abbrev_enabled()
    r = float(r)
    t = float(t)

    for i in range(len(WORLDS)):
        (name, high, low, subType) = WORLDS[i]
        (label, edsm, near, dash, far, ls) = this.worlds[i]

        far_dist = int(0.5 + dfort(r, t, low))
        radius   = int(0.5 + r / LS)

        if far_dist <= radius:
            near['text'] = ''
            dash['text'] = u'×'
            far['text'] = ''
            ls['text'] = ''
            near._exact = ''
            far._exact = ''
        else:
            near_val = radius if not high else int(0.5 + dfort(r, t, high))
            far_val  = far_dist

            near['text'] = format_distance(near_val, abbreviate)
            dash['text'] = '-'
            far['text']  = format_distance(far_val, abbreviate)
            ls['text'] = 'ls'

            if abbreviate:
                near._exact = "Exact distance: %s ls" % Locale.string_from_number(near_val, 0)
                far._exact  = "Exact distance: %s ls" % Locale.string_from_number(far_val, 0)
            else:
                near._exact = ''
                far._exact = ''


def _clear_hz_with_error():
    for (label, edsm, near, dash, far, ls) in this.worlds:
        near['text'] = ''
        dash['text'] = ''
        far['text'] = ''
        ls['text'] = '?'
        near._exact = ''
        far._exact = ''


# -----------------------------
# HabZone core
# -----------------------------
def dfort(r, t, target):
    return (((r ** 2) * (t ** 4) / (4 * (target ** 4))) ** 0.5) / LS


# -----------------------------
# EDSM lookup (original behaviour)
# -----------------------------
def edsm_worker(systemName):
    if not this.edsm_session:
        this.edsm_session = requests.Session()

    try:
        r = this.edsm_session.get(
            'https://www.edsm.net/api-system-v1/bodies?systemName=%s' % quote(systemName),
            timeout=10
        )
        r.raise_for_status()
        this.edsm_data = r.json() or {}
    except Exception:
        if __debug__:
            print_exc()
        this.edsm_data = None

    if this.frame:
        this.frame.event_generate('<<HabZoneData>>', when='tail')


def edsm_data(event):
    if this.edsm_data is None:
        for (label, edsm, near, dash, far, ls) in this.worlds:
            edsm['text'] = '?'
            edsm['url'] = None
        return

    bodies = defaultdict(list)
    for body in this.edsm_data.get('bodies', []):
        if body.get('terraformingState') == 'Candidate for terraforming':
            bodies['terraformable'].append(body.get('name', ''))
        else:
            bodies[body.get('subType', '')].append(body.get('name', ''))

    systemName = this.edsm_data.get('name', '') or ''
    if systemName:
        this._last_systemname = systemName

    url_all = 'https://www.edsm.net/show-system?systemName=%s&bodyName=ALL' % quote(systemName)
    for i in range(len(WORLDS)):
        (name, high, low, subType) = WORLDS[i]
        (label, edsm, near, dash, far, ls) = this.worlds[i]

        lst = bodies[subType]
        edsm['text'] = ' '.join([
            x[len(systemName):].replace(' ', '') if systemName and x.startswith(systemName) else x
            for x in lst if x
        ])

        edsm['url'] = (
            len(lst) == 1 and
            'https://www.edsm.net/show-system?systemName=%s&bodyName=%s' % (quote(systemName), quote(lst[0]))
            or url_all
        )


# -----------------------------
# Settings / visibility
# -----------------------------
def get_setting():
    setting = config.get_int('habzone')
    if setting == 0:
        return SETTING_DEFAULT
    elif setting == SETTING_NONE:
        return 0
    else:
        return setting

def update_visibility():
    setting = get_setting()
    row = 1
    grid_row = 1  # row 0 reserved for button

    for (label, edsm, near, dash, far, ls) in this.worlds:
        if setting & row:
            label.grid(row=grid_row, column=0, sticky=tk.W)
            edsm.grid(row=grid_row, column=1, sticky=tk.W, padx=(0, 10))
            near.grid(row=grid_row, column=2, sticky=tk.E)
            dash.grid(row=grid_row, column=3, sticky=tk.E)
            far.grid(row=grid_row, column=4, sticky=tk.E)
            ls.grid(row=grid_row, column=5, sticky=tk.W)
        else:
            label.grid_remove()
            edsm.grid_remove()
            near.grid_remove()
            dash.grid_remove()
            far.grid_remove()
            ls.grid_remove()

        row *= 2
        grid_row += 1

    if setting:
        this.spacer.grid_remove()
    else:
        this.spacer.grid(row=0)
