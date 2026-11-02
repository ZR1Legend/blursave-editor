"""Writes tools/LICENSES.txt: notices that go with the shared BlurSaveEditor.exe (bundled into it, shown by its Info button).
Run after updating Python:  py tools/make_licenses.py"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.dirname(sys.executable)

LICENSE_TEXT = open(os.path.join(HERE, "..", "LICENSE"), encoding="utf-8").read().strip()
LIMITS = """Limits
------

- The editor was developed and tested with the PC version of Blur on one Windows 11 computer. Other setups may behave differently.
- Import PS3/Xbox takes level, fans, last car, mod, counters, car states, campaign and seen cutscenes. It does not take paint jobs or options.
- Export PS3 writes an unencrypted file without PARAM.PFD. It has been tried only in the emulator RPCS3, never on a real PlayStation 3, and will
  not load on a real console. Xbox 360 saves can be read, not written.
- Xbox 360 packages are read without checking their signature.
- What the game does with a save that it does not like (it repairs it while loading) is only known for the cases we tested; see docs/BLURSAVE_FORMAT.md."""
ACK = """Thanks
------

- Bizarre Creations, the developers of Blur (published by Activision): for making the game this tool is about.
- Blur Map Builder (MDPRO, MIT licence): the description of the game's PAK and picture formats, from which our small readers were written.
- apollo-ps3 (bucanero) and pfdtool / Bruteforce Save Data (Flatz): how PS3 save games are protected (PARAM.PFD). The "secure file ID" of Blur comes from the
  public games.conf lists of these tools.
- RPCS3: the PS3 emulator in which the PS3 save games were tested. BlurRebuilt (0x90v1) and the Amax-Emu project: the community that keeps the game running.
- Python, Tcl/Tk and PyInstaller (see below)."""


HEAD = """blursave editor by ZR1Legend
============================

Unofficial fan tool. Not made, supported or approved by Activision, Bizarre Creations or any other rights holder of Blur.
"Blur" and all game content belong to their rights holders.

The editor reads and writes only save games (the file "blursave"; PS3 and Xbox 360 saves it reads or writes only when you ask it to) and the game's settings.xml.
It does not access the game's files at run time. The program contains material taken from the game: the car silhouettes, class badges, status symbols,
manufacturer logos, the Blur logo, header icons and mod symbols (drawn from the game's own icon files), the descriptions of the stickers (achievements), event
and car names, and the details it needs to read and write a save (IDs, internal model names, numbers such as fan levels, the layout of the career). These pictures
and texts (the manufacturer logos are trademarks of the manufacturers) are the property of their rights holders. They are included in the unofficial tool only to
identify cars, mods and goals, and will be removed on request of the rights holder.

The colour scheme is modelled on the game's menus (palette taken from screenshots, no game files).

The code of the editor is under the MIT licence (see below); this does not apply to the game material named above.
Use at your own risk: before every write the editor makes a backup of the save game. The software is provided without any warranty.


""" + LIMITS + """

""" + ACK + """

""" + LICENSE_TEXT + """

Included third-party software
-----------------------------

Python (PSF licence) and Tcl/Tk (BSD-style licence), packed into the .exe as the runtime with PyInstaller (GPLv2 with an
exception for the generated .exe). The licence texts follow.
"""


def section(title, text):
    return "\n\n" + "=" * 78 + "\n" + title + "\n" + "=" * 78 + "\n\n" + text.strip() + "\n"


def main():
    out = HEAD
    with zipfile.ZipFile(os.path.join(PY, "tcl", "libtcl9.0.4.zip")) as z:
        out += section("Tcl/Tk - license.terms", z.read("tcl_library/license.terms").decode("utf-8", "replace"))
    out += section("Python - LICENSE.txt", open(os.path.join(PY, "LICENSE.txt"), encoding="utf-8").read())
    open(os.path.join(HERE, "LICENSES.txt"), "w", encoding="utf-8", newline="\n").write(out)
    print("LICENSES.txt: %d bytes" % len(out.encode("utf-8")))


if __name__ == "__main__":
    main()
