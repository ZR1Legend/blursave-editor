"""The game's graphics settings file: %APPDATA%\\bizarre creations\\blur\\settings.xml

Two lines (not one XML document):
    <application_settings version="1"/>
    <shared_graphical_settings width="1024" height="768" x="0" y="0" multisample="3" windowed="1" vsync="0" graphical_detail="4"/>
Values (found by changing them in the game's Graphics menu, 2026-11-01):
    multisample       0 Off, 1 2x, 2 4x, 3 8x (all measured in the game)
    windowed          0 fullscreen, 1 windowed
    vsync             0 Off, 1 On
    graphical_detail  1 to 4 = Graphics Quality step 0 to 3 (the menu's lowest step writes 1, the highest 4)
    width, height     resolution
The rest of the file is kept as it is; only the attributes of shared_graphical_settings are replaced.
"""
import os
import re

NAMES = ("width", "height", "x", "y", "multisample", "windowed", "vsync", "graphical_detail")
_TAG = re.compile(r"<shared_graphical_settings\b([^>]*?)(/?)>")
_ATTR = re.compile(r'(\w+)="([^"]*)"')


def default_path(save_path=None):
    """settings.xml lies next to the save folder (…\\blur\\save\\blursave -> …\\blur\\settings.xml)"""
    if save_path:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(save_path))), "settings.xml")
        if os.path.isfile(p):
            return p
    return os.path.join(os.environ.get("APPDATA", ""), "bizarre creations", "blur", "settings.xml")


def read(path):
    """{name: int} of the graphics attributes, None when the file or the element is missing"""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return None
    m = _TAG.search(text)
    if not m:
        return None
    vals = {k: v for k, v in _ATTR.findall(m.group(1))}
    try:
        return {n: int(vals[n]) for n in NAMES}
    except (KeyError, ValueError):
        return None


def write(path, values):
    """replaces the attributes in place; returns the new text"""
    text = open(path, encoding="utf-8").read()
    m = _TAG.search(text)
    if not m:
        raise ValueError("no shared_graphical_settings element in %s" % path)

    def sub(mm):
        k = mm.group(1)
        return '%s="%d"' % (k, values[k]) if k in values else mm.group(0)

    new_attrs = _ATTR.sub(sub, m.group(1))
    out = text[:m.start()] + "<shared_graphical_settings" + new_attrs + m.group(2) + ">" + text[m.end():]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    return out
