# blursave editor

**blursave editor by ZR1Legend**: an unofficial save game editor for *Blur* (Bizarre Creations, 2010, PC), plus notes on how the save game is built.

> Not made, supported or approved by Activision, Bizarre Creations or any other rights holder of Blur. Use at your own risk; the editor makes a backup before every write.

## Download

Get `BlurSaveEditor.exe` from the [Releases](../../releases) page (one file, nothing to install). Check it against the SHA-256 checksum in the release notes.
Windows SmartScreen or a virus scanner may warn on first start: the file is not code-signed. If you do not trust it, build it yourself from the source (below).

## What it can do

- Profile: fans, fan level, boss mod, last driven car
- Career: groups and events (status, place, difficulty, fans), rival demands, defeat a rival; a **new** profile's campaign can be edited at once
- Cars: the "new" marker, paint (colour, brightness, Pearlescent / Candy / Metallic finishes)
- Stickers: the counters behind the stickers (achievements)
- Settings: audio, controls, difficulty, graphics (`settings.xml`)
- Preview: what the game would repair in the save when it loads it
- **Import PS3/Xbox**: takes the progress of a PlayStation 3 or Xbox 360 save game into a new PC save game
- **Export PS3**: writes the PC save as a PS3 save for the emulator RPCS3 (not encrypted, not for a real console)

Close Blur before editing: the game rewrites its save when it loads and exits. Details: [release/README.txt](release/README.txt).

## The save game format

[docs/BLURSAVE_FORMAT.md](docs/BLURSAVE_FORMAT.md) describes the `blursave` file (PC) and the differences in PS3 and Xbox 360 saves: container, profile, vehicles, campaign,
statistics table / stickers, mods, paint jobs, options and what the game repairs on load. Every statement is labelled *Game* (tested in the game), *Data* or *Guess*.

## Limits

- Developed and tested with the PC version on one Windows 11 computer.
- Import PS3/Xbox does not take paint jobs or options. Xbox 360 packages are read without checking their signature, and cannot be written.
- Export PS3 has only been tried in RPCS3, never on a real PlayStation 3.

## Build from source

Python 3 with Tkinter, then `pip install pyinstaller` and run `tools\build_exe.bat`; the exe lands in `release\`. Run the editor directly with `python tools\blursave_editor.py [blursave]`.
The self test needs a save game: `python tools\blursave_editor.py --selftest tools\blursave_new.bin`.
The command line `python tools\blursave.py unpack|pack|check` needs `blursave_names.json` (an extract of the game's database; not part of this repository).

## Licence

The code is under the [MIT licence](LICENSE). The pictures and texts taken from the game (car silhouettes, manufacturer logos, mod symbols, sticker texts, car and event names) belong to
their rights holders and are included only to identify cars, mods and goals; they will be removed on request.

## Thanks

Bizarre Creations (the developers of Blur, published by Activision); Blur Map Builder (MDPRO) for the description of the game's file formats; apollo-ps3 (bucanero) and pfdtool (Flatz) for the PS3 save
protection; RPCS3; BlurRebuilt (0x90v1) and the Amax-Emu project.
