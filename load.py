# -*- coding: utf-8 -*-
#
# Display the "habitable-zone" (i.e. the range of distances in which you might find an Earth-Like World)
#
# V2 (EDMC 6.x / Python 3.x) UI formatting:
# - remove decimals in distance display
# - optional k/M abbreviation for large distances (toggle in prefs)
# - tooltip shows exact distance when abbreviation is enabled
#

from __future__ import print_function

from collections import defaultdict
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

VERSION = '1.22'

SETTING_DEFAULT = 0x0002    # Earth-like
SETTING_EDSM    = 0x1000
SETTING_NONE    = 0xffff

CFG_ABBREV = 'habzone_abbrev'  # 0/1

WORLDS = [
    # Type            Black-body temp range  EDSM description
    ('Metal-Rich',      0,    1103.0, 'Metal-rich body'),
    ('Earth-Like',    278.0,   227.0, 'Earth-like world'),
    ('Water',         307.0,   156.0, 'Water world'),
    ('Ammonia',       193.0,   117.0, 'Ammonia world'),
    ('Terraformable', 315.0,   223.0, 'terraformable'),
]

LS = 300000000.0    # 1 ls in m (approx)

this = sys.modules[__name__]    # For holding module globals
this.frame = None
this.worlds = []
this.edsm_session = None
this.edsm_data = None

# Used during preferences
this.settings = None
this.edsm_setting = None
this.abbrev_setting = None


def plugin_start3(plugin_dir):
    return 'HabZone'


def plugin_start():
    return 'HabZone'


# -----------------------------
# Formatting helpers
# -----------------------------

def format_distance(value, abbreviate):
    """Return a display string for a distance in ls."""
    value = int(value)

    if abbreviate and value >= 10_000:
        if value >= 1_000_000:
            return Locale.string_from_number(value / 1_000_000, 2) + 'M'
        return Locale.string_from_number(value / 1_000, 1) + 'k'

    return Locale.string_from_number(value, 0)


# -----------------------------
# Tooltip (only used when abbrev is enabled)
# -----------------------------

class SimpleTooltip(object):
    def __init__(self, widget, text_fn):
        self.widget = widget
        self.text_fn = text_fn
        self.tip = None
        widget.bind('<Enter>', self.show, add='+')
        widget.bind('<Leave>', self.hide, add='+')

    def show(self, *_):
        text = self.text_fn() or ''
        if not text or self.tip:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        tk.Label(
            self.tip,
            text=text,
            relief='solid',
            borderwidth=1,
            font=('TkDefaultFont', 9),
            padx=6,
            pady=3,
        ).pack()
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 12
        self.tip.wm_geometry(f'+{x}+{y}')

    def hide(self, *_):
        if self.tip:
            self.tip.destroy()
            self.tip = None



def plugin_app(parent):
    # Create and display widgets
    this.frame = tk.Frame(parent)
    this.frame.columnconfigure(3, weight=1)
    this.frame.bind('<<HabZoneData>>', edsm_data)    # callback when EDSM data received

    for (name, high, low, subType) in WORLDS:
        near = tk.Label(this.frame)
        far = tk.Label(this.frame)

        # store tooltip text on the widget itself
        near._exact = ''
        far._exact = ''

        # tooltips always bound; text_fn returns '' when disabled
        SimpleTooltip(near, lambda w=near: getattr(w, '_exact', ''))
        SimpleTooltip(far,  lambda w=far:  getattr(w, '_exact', ''))

        this.worlds.append((
            tk.Label(this.frame, text=name + ':'),
            HyperlinkLabel(this.frame, wraplength=100),  # edsm
            near,                                        # near
            tk.Label(this.frame),                        # dash
            far,                                         # far
            tk.Label(this.frame),                        # ls
        ))

    this.spacer = tk.Frame(this.frame)   # Main frame can't be empty or it doesn't resize
    update_visibility()
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

    # V2: distance formatting toggle
    nb.Label(frame, text='Formatting:').grid(padx=10, pady=(10, 0), sticky=tk.W)
    this.abbrev_setting = tk.IntVar(value=config.get_int(CFG_ABBREV))
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

    # V2: save abbrev toggle
    config.set(CFG_ABBREV, '1' if this.abbrev_setting.get() else '0')

    this.settings = None
    this.edsm_setting = None
    this.abbrev_setting = None
    update_visibility()




def journal_entry(cmdr, is_beta, system, station, entry, state):

    if entry.get('event') == 'Scan':
        try:
            if not float(entry.get('DistanceFromArrivalLS', 0.0)):  # Only calculate for arrival star
                r = float(entry['Radius'])
                t = float(entry['SurfaceTemperature'])

                abbreviate = bool(config.get_int(CFG_ABBREV))

                for i in range(len(WORLDS)):
                    (name, high, low, subType) = WORLDS[i]
                    (label, edsm, near, dash, far, ls) = this.worlds[i]

                    far_dist = int(0.5 + dfort(r, t, low))
                    radius = int(0.5 + r / LS)

                    if far_dist <= radius:
                        near['text'] = ''
                        dash['text'] = u'×'
                        far['text'] = ''
                        ls['text'] = ''
                        near._exact = ''
                        far._exact = ''
                    else:
                        if not high:
                            near_val = radius
                        else:
                            near_val = int(0.5 + dfort(r, t, high))
                        far_val = far_dist

                        near['text'] = format_distance(near_val, abbreviate)
                        dash['text'] = '-'
                        far['text'] = format_distance(far_val, abbreviate)
                        ls['text'] = 'ls'

                        if abbreviate:
                            near._exact = 'Exact distance: %s ls' % Locale.string_from_number(near_val, 0)
                            far._exact  = 'Exact distance: %s ls' % Locale.string_from_number(far_val, 0)
                        else:
                            near._exact = ''
                            far._exact = ''
        except Exception:
            if __debug__:
                print_exc()
            for (label, edsm, near, dash, far, ls) in this.worlds:
                near['text'] = ''
                dash['text'] = ''
                far['text'] = ''
                ls['text'] = '?'
                near._exact = ''
                far._exact = ''

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

    if entry.get('event') in ['Location', 'FSDJump'] and get_setting() & SETTING_EDSM:
        thread = threading.Thread(target=edsm_worker, name='EDSM worker', args=(entry.get('StarSystem', ''),))
        thread.daemon = True
        thread.start()



def cmdr_data(data, is_beta):
    # Manual Update
    if get_setting() & SETTING_EDSM and not data['commander']['docked']:
        thread = threading.Thread(target=edsm_worker, name='EDSM worker', args=(data['lastSystem']['name'],))
        thread.daemon = True
        thread.start()


# Distance for target black-body temperature
# From Jackie Silver's Hab-Zone Calculator https://forums.frontier.co.uk/showthread.php?p=5452081
def dfort(r, t, target):
    return (((r ** 2) * (t ** 4) / (4 * (target ** 4))) ** 0.5) / LS


# EDSM lookup
def edsm_worker(systemName):

    if not this.edsm_session:
        this.edsm_session = requests.Session()

    try:
        r = this.edsm_session.get(
            'https://www.edsm.net/api-system-v1/bodies?systemName=%s' % quote(systemName),
            timeout=10
        )
        r.raise_for_status()
        this.edsm_data = r.json() or {}    # Unknown system represented as empty list
    except Exception:
        if __debug__:
            print_exc()
        this.edsm_data = None

    # Tk is not thread-safe, so can't access widgets in this thread.
    # event_generate() is the only safe way to poke the main thread from this thread.
    this.frame.event_generate('<<HabZoneData>>', when='tail')


# EDSM data received
def edsm_data(event):

    if this.edsm_data is None:
        # error
        for (label, edsm, near, dash, far, ls) in this.worlds:
            edsm['text'] = '?'
            edsm['url'] = None
        return

    # Collate
    bodies = defaultdict(list)
    for body in this.edsm_data.get('bodies', []):
        if body.get('terraformingState') == 'Candidate for terraforming':
            bodies['terraformable'].append(body['name'])
        else:
            bodies[body['subType']].append(body['name'])

    # Display
    systemName = this.edsm_data.get('name', '')
    url = 'https://www.edsm.net/show-system?systemName=%s&bodyName=ALL' % quote(systemName)
    for i in range(len(WORLDS)):
        (name, high, low, subType) = WORLDS[i]
        (label, edsm, near, dash, far, ls) = this.worlds[i]
        edsm['text'] = ' '.join([x[len(systemName):].replace(' ', '') if x.startswith(systemName) else x for x in bodies[subType]])
        edsm['url'] = (
            len(bodies[subType]) == 1 and
            'https://www.edsm.net/show-system?systemName=%s&bodyName=%s' % (quote(systemName), quote(bodies[subType][0]))
            or url
        )



def get_setting():
    setting = config.get_int('habzone')
    if setting == 0:
        return SETTING_DEFAULT    # Default to Earth-Like
    elif setting == SETTING_NONE:
        return 0    # Explicitly set by the user to display nothing
    else:
        return setting



def update_visibility():
    setting = get_setting()
    row = 1
    for (label, edsm, near, dash, far, ls) in this.worlds:
        if setting & row:
            label.grid(row=row, column=0, sticky=tk.W)
            edsm.grid(row=row, column=1, sticky=tk.W, padx=(0, 10))
            near.grid(row=row, column=2, sticky=tk.E)
            dash.grid(row=row, column=3, sticky=tk.E)
            far.grid(row=row, column=4, sticky=tk.E)
            ls.grid(row=row, column=5, sticky=tk.W)
        else:
            label.grid_remove()
            edsm.grid_remove()
            near.grid_remove()
            dash.grid_remove()
            far.grid_remove()
            ls.grid_remove()
        row *= 2
    if setting:
        this.spacer.grid_remove()
    else:
        this.spacer.grid(row=0)
