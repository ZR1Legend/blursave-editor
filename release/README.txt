blursave editor by ZR1Legend
============================

Unofficial fan tool for viewing and editing the single-player save game of Blur (PC).
Not made by Activision or Bizarre Creations. Use at your own risk.

Starting
--------
Run BlurSaveEditor.exe - nothing to install. The editor opens your save game automatically:
  %APPDATA%\bizarre creations\blur\save\blursave
Close Blur first (the game overwrites the save game when it loads and when it exits).
Before every save the editor makes a copy:
  %APPDATA%\bizarre creations\blur\editor_backups\

What it can do
--------------
- New: creates a new save game (as the game writes it for a new profile; its campaign can be edited at once)
- Import PS3/Xbox: reads a PlayStation 3 save game (the file AMAXSAVE; PARAM.PFD must be in the same folder) or an Xbox 360 save game (the package file AMAXSAVE) and writes its progress into a NEW PC save game
  (level, fans, last car, mod, counters, car states, campaign, seen cutscenes; paint jobs and settings are not taken over)
- Export PS3: writes the open save game as a PS3 save game (AMAXSAVE) into a folder. You choose a PS3 save game as the template; its values are replaced, the rest stays.
  The file is NOT encrypted and has no PARAM.PFD: this is the form the emulator RPCS3 reads (dev_hdd0/home/00000001/savedata/BLES00759-AUTO-). Not for a real console.
- Profile: fans, Fan Status, mod, last driven car
- Career: groups and events (status, place, difficulty, fans, Fan Run), meet or reset a rival's demands, defeat a rival
- Cars: the "seen" / "new" marker; cars are unlocked by Fan Status or as a rival reward; paint (colour, brightness and the Pearlescent/Candy/Metallic finishes)
  of any car (set or remove)
- Stickers: the counters behind the stickers (achievements), e.g. "Shunt 250 cars": set a counter or reach the goal of one sticker or of all of them.
  The game does not store which stickers you have, only these counters.
- Settings: audio options, controller and keyboard layout, Difficulty, Region Rule, Brightness Adjust (stored in the save game) and graphics options
  (settings.xml, written with its own button; a backup is made in editor_backups first)
- Preview: what the game would correct in a save when it loads it. The editor applies these corrections when saving,
  so the save stays as it was written.

Game files
----------
The editor does not access the game's files while it runs. It reads and writes only the save game and, in the Settings
tab, the game's settings.xml in the same %APPDATA% folder. Cars are shown by their names in the game
(for example "Carver's Viper GTSR"). The car silhouettes, class badges, status symbols, manufacturer logos, the Blur logo, header icons and mod symbols in the program are taken from the game's
icon files, and the program contains texts from the game (sticker descriptions, event and car names); they belong to their rights holders (the manufacturer logos are trademarks of the manufacturers) and will be removed on request.

Limits
------

- The editor was developed and tested with the PC version of Blur on one Windows 11 computer. Other setups may behave differently.
- Import PS3/Xbox takes level, fans, last car, mod, counters, car states, campaign and seen cutscenes. It does not take paint jobs or options.
- Export PS3 writes an unencrypted file without PARAM.PFD. It has been tried only in the emulator RPCS3, never on a real PlayStation 3, and will
  not load on a real console. Xbox 360 saves can be read, not written.
- Xbox 360 packages are read without checking their signature.
- What the game does with a save that it does not like (it repairs it while loading) is only known for the cases we tested; see docs/BLURSAVE_FORMAT.md.

Thanks
------

- Bizarre Creations, the developers of Blur (published by Activision): for making the game this tool is about.
- Blur Map Builder (MDPRO, MIT licence): the description of the game's PAK and picture formats, from which our small readers were written.
- apollo-ps3 (bucanero) and pfdtool / Bruteforce Save Data (Flatz): how PS3 save games are protected (PARAM.PFD). The "secure file ID" of Blur comes from the
  public games.conf lists of these tools.
- RPCS3: the PS3 emulator in which the PS3 save games were tested. BlurRebuilt (0x90v1) and the Amax-Emu project: the community that keeps the game running.
- Python, Tcl/Tk and PyInstaller (see below).

Licence
-------
The code is under the MIT licence (file LICENSE in the source; the text is also in the "Info" window). The pictures and texts from the game are not covered by it;
they belong to their rights holders. Notes on the save game format: docs/BLURSAVE_FORMAT.md in the source repository.

Notes
-----
- Windows SmartScreen or a virus scanner may warn on first start: the file is not code-signed.
- Licence notices for the software used: "Info" button in the program.
