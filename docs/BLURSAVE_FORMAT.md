# Blur save game (`blursave`): what we know

Unofficial notes on the save game of **Blur** (Bizarre Creations, 2010) on PC, with the differences found in PlayStation 3 and Xbox 360 saves.
They were worked out by comparing saves, reading the game's data files and, most of all, by changing saves and loading them in the game.
Reference implementation: `tools/blursave.py` (PC), `tools/ps3save.py` (PS3 / Xbox 360), `tools/blursave_rules.py` (what the game repairs on load).

Every statement carries one of three labels:

- **[Game]**: tested in the game, either by changing the save and loading it, or by an observation made while playing.
- **[Data]**: shown by comparing several saves or by the game's data files, but not tested by a change in the game.
- **[Guess]**: a conclusion from the data, not proven.

PC location of the file: `%APPDATA%\bizarre creations\blur\save\blursave` (the game and BlurRebuilt share it). "Amax" in names such as
`AmaxVehicle`, `AmaxEvent` and in the console file name `AMAXSAVE` is the internal project name of the game; the game's own texts never show it.

## 1. Container

[Game] The game loads such files and a round trip through our tools is byte-identical.

| Bytes | Content |
|---|---|
| 0-3 | magic `0xABCDE337` (PC: little-endian, bytes `37 e3 cd ab`; PS3 / Xbox 360: big-endian, bytes `ab cd e3 37`) |
| 4-7 | size of the unpacked data (PC: 51,973 to 53,270 bytes so far; new profile 50,903) |
| 8-11 | size of the packed part |
| 12- | one zlib stream (header `78 da`), ending with a sync flush (`00 00 ff ff`) and no final block |

No checksum was found. [Game] The game also loads files with changed bytes, but it **repairs** inconsistencies while loading (section 8).

The unpacked data are about 91 % zeros and have no field names. Records follow each other **unaligned**, and **offsets move between saves**
(new entries push everything behind them). Fields are therefore found by anchor values, never by fixed addresses.
"u32" in this document is a 4-byte integer in the byte order of the platform (PC little-endian, consoles big-endian).

## 2. IDs

Many fields are 32-bit IDs from the game's data files: vehicles (`AmaxVehicle`), events (`AmaxEvent`), routes (`Route`), drivers
(`RaceBookCharacter`) and paint jobs (`VEH_PaintJob`). [Data] The campaign's groups ("tiers"), rivals and events have **their own** IDs
(the `id` fields of `SP_TierData`), not the object IDs of the `AmaxEvent` objects. The IDs are the same on all platforms (only the byte order differs).

## 3. Profile

| Field | Layout | |
|---|---|---|
| Fan level | u32 | [Game] |
| Fans | the total (every race adds to it); u32 on PC. Consoles store 64 bits (the 4 bytes in front of the u32 are 0), so reading a u32 at the same place works on PC | [Game] |
| Last driven car | vehicle ID, 20 bytes behind the fan level (menu background, car preselected for events) | [Game] |
| Lights | float32, entry `0x1d` of the statistics table (section 6); the game does not use it for its display | [Game] |

- **Anchor:** the fan level lies 60 bytes in front of the first record of the tier table (tier ID `0x3F17A973`).
- **Level from fans:** the level is the highest one whose threshold the fans reach. [Game] The game recomputes it on load and ignores the stored level.
  Thresholds (level: fans): 1: 0, 2: 700, 3: 3,350, 4: 6,300, 5: 9,500, 6: 14,300, 7: 18,450, 8: 22,880, 9: 27,500, 10: 32,600, 11: 37,950,
  12: 43,450, 13: 53,900, 14: 60,600, 15: 67,700, 16: 75,100, 17: 82,800, 18: 90,850, 19: 99,250, 20: 116,900, 21: 126,750, 22: 136,750,
  23: 147,150, 24: 158,000, 25: 170,300 (maximum).

## 4. Vehicles

**Table "seen":** 80 entries of 8 bytes, sorted by vehicle ID: `[vehicle ID][state u8][3 bytes]` (the database has 81 vehicles). The 3 bytes are not
constant (PC `58 89 0f`, PS3 / Xbox `000000` or leftovers) and have no meaning. The end of the event record in front of the table (vehicle ID + flags)
looks like an entry and is not part of it.

| State | Meaning |
|---|---|
| 2 | seen, no marker [Game] |
| 0 or 1 | not seen yet; an unlocked car shows the "new" marker [Game] |

**This state is not the unlock.** [Game] Cars stay drivable with any state. Unlocking follows from the fan level (every level unlocks 1-3 cars, including the "Legend"
cars) and from rival rewards (section 5). [Game] When the game gives a car (reward, level) it sets the state from 0 to 1; driving does not remove the marker.
On load the game puts the cars that need a higher level than the current one back to 0 (12 cars when the level was lowered to 19). Classes: 0 = A, 1-3 = B, C, D [Data]. 43 of 81 cars can be resprayed in the game's UI (`UICanReSpray`; section 9).

## 5. Campaign

9 groups ("tiers"), each with one rival and 7 events `TnE0`-`TnE6`; `E6` is the rival's One-on-One.
Group names: 1 Proving Grounds (Shannon), 2 City Slickers (Khan), 3 Fan Favorite (Rhymer), 4 Crash and Burn (Drayke), 5 Ruthless Aggression (Natalya),
6 Midas Touch (Talon), 7 Double Damage (Ayumi and Harumi), 8 Loose Cannon (Carver), 9 The Showdown (Show Down).

### Tier table
8 bytes per group, sorted by ID: `[tier ID][state]`. The state is the **first byte** (2 = seen, 1 = new marker, 0 = locked because the lights are not enough);
the 3 bytes behind it are leftovers that differ between saves ("01 7f 00 00"). [Game] Lights needed to unlock groups 1-9: 0, 25, 50, 75, 110, 140, 185, 215, 280.
A group is open when the lights reach its threshold; the game locks groups below it on load and opens `E0`-`E2` of open groups. [Game]

### Event record (24 bytes)
`[event ID][fans u32][? u32][float][vehicle ID][status][place][difficulty][tunnel]`

| Field | Meaning | |
|---|---|---|
| fans | fans of the saved run in this event | [Game] |
| ? | unknown, mostly 0 | |
| float | unknown; probably a time in seconds (races about 150-350, checkpoint 20-30, destruction 0) | [Guess] |
| vehicle ID | the car of the last run (overwritten by a repeat) | [Game] |
| status | 0 locked, 1 available, 2 played | [Game] |
| place | 3 = 1st, 2 = 2nd, 1 = 3rd; **0 = played without a podium** | [Game] |
| difficulty | 1 easy, 2 medium, 3 hard; 0 without a podium | [Game] |
| tunnel | 1 = the fan tunnel was driven | [Game] |

- The **fan target** is not a flag: it counts as reached when "fans" reaches the target in the game data (`fanPar`). [Game]
- A run without a podium sets status 2 and leaves place, difficulty, tunnel and fans at 0; only the car is recorded. [Game]
- **Repeating an event:** a worse run in every respect only replaces the car; a better run replaces everything; a better place with an easier difficulty replaces
  everything, including the difficulty. [Game] Total fans always include the new run. Whether "place" or "lights" decides is not separated.
- Events unlock in order: `E0`-`E2` first, `E3`-`E5` after playing `E0` and `E1`; the rival event `E6` after the four demands are met. [Game]

### Lights
- Race, destruction, checkpoint: place (1st = 5, 2nd = 4, 3rd = 3) + 1 for the fan target + 1 for the tunnel (at most 7). A won rival event: 8.
  A group gives at most 6 x 7 + 8 = 50 lights, the nine groups 450.
- [Game] The display is computed from the event records, not from the stored counter. A reset event keeps counting its fan light while `fans` stays above the target.
  The stored counter (statistics entry `0x1d`) often lags one run behind; the sum over the events decides.

### Rival record (24 bytes)
`[rival ID][counter 1][counter 2][counter 3][counter 4][status, 4 bytes]`, counters u32 (a drift value is a float32 bit pattern: 1500.0 = 1153138688).

- The counters are the progress of the four demands in the order of the game data. [Game] The in-game progress (e.g. 1/1, 8/15, 4/20, 2/6) matches the stored counters one by one.
- Status byte 0 becomes 1 when all four demands are met: the rival event `E6` becomes available (`[0,0,0,0]` -> `[1,0,0,0]`) and the group's "unlock" car is given. [Game]
- Status byte 1 becomes 1 after the rival is beaten; the reward car is given. [Game]
- Status bytes 2 and 3 are **leftovers**. The PC game usually writes 174 in byte 2, but Xbox 360 saves have 211 / 144 and PS3 saves 0 / 0, so no value is required.
- Demands (order of the counters) and cars:

| Group | Demands | Unlocks | Beaten |
|---|---|---|---|
| 1 | power-ups 80, fans 7,000, a different car 4, events 5 | Renault Megane Sport R26 | Shannon's car |
| 2 | power-up shields 3, dodged full shocks 3, stopwatches 40, finish an event with 14 s left | Foose Stallion | Khan's car |
| 3 | fan demands 5, fan runs 2, fan targets 4, 5-combo 1 | Camaro SS, Camaro Legend II | Camaro SS "Rhymer" |
| 4 | ram into the sea 1, wrecks 100, barge hits 5, all lights in an event 6 | Hummer H2 | Drayke's car |
| 5 | shunt hits 5, multi barges 5, shocks 10, fan run 1 | BMW 1 Series Race | Natalya's car |
| 6 | drift 1,500, defend against weapons 4, clean triple nitros 4, lights 25 | Corvette ZR1 | Talon's car |
| 7 | forward mines 5, nitro rams 5, destruction bonus 10, wreck and win 1 | Skyline | Ayumi's / Harumi's car |
| 8 | shield mines 3, 3-bolt 8, no S/R 1, win in Natalya's BMW 1 | Dodge Viper GTSR | Carver's Viper GTSR |
| 9 | speed 1, reverse bolts 15, mines 20, win all 6 events 6 | Astra Extreme, Astra Extreme Legend VIII | Astra Extreme "Shannon" |

Winning a rival event gives a status `[2,3,difficulty,0]`, fans, a float and 8 lights; a lost One-on-One is `[2,0,0,0]`. [Game] Finishing the campaign changes nothing else in the save.

## 6. Statistics table, stickers and cutscenes

The table of **118 entries** are the counters behind the stickers ("achievements"). The game knows 50 achievements (`achievements.bin`), each with 1-4 sub-goals (a "sticker":
`Type`, `Goal`, `OneShot`). [Game] The game stores **only these counters**; whether a goal is reached is computed as counter >= goal. No list of unlocked stickers exists in the save.

| Platform | Entry layout |
|---|---|
| PC | `[index u16][00 00][float32]`, little-endian |
| PS3 / Xbox 360 | `[index u32][float32]`, big-endian |

- The entry of a goal has `index = Type` for `Type <= 34` and `index = Type - 1` above that. 117 goals exist (index `0x38` has none). An entry whose index reads all ones is unavailable.
  `Blur.exe` (not BlurRebuilt) marks `0x07` ("wreck a Blur developer on Xbox LIVE") and `0x63` ("share on Facebook/Twitter") that way on load; the PS3 save has 7, 56 and 99 marked, the Xbox 360 save 56.
- Values are floats (`0x5e` "shunt 250 cars" = 244.0). [Game] Examples: `0x1b/0x1c/0x1d` = primary lights / fan targets / all lights; `0x35` mines; `0x4e` repair; `0x73-0x75` destruction.
- [Game] Setting a counter changes the sticker in the game at once (244 -> 250 showed 250/250 and a green tick). Setting all counters made all stickers owned,
  even in an early save in which the rival was not beaten: the game does not check counters against campaign progress.
- "33/48" in the sticker screen is the **position of the selected sticker in the gallery**, not a progress value.
- Behind the table: `[ff 3f 00 00]` (PC; `d8 05 00 00` in an early save), one flag byte (1 in saves written by the game here, 0 in two downloaded ones), then the **mod** (see below).
  Four single bytes `0f 0c 0c 05` follow at fixed distances (mod + 91 / 155 / 207 / 259; on consoles +94 / 158 / 210 / 262 from the start of the 4-byte mod): meaning unknown.
- **Seen videos:** a u32 bit mask **8 bytes in front of the first table entry** (right in front of the entry count 0x76). [Game] The game remembers which videos/hints were seen
  (the gear symbol of the autosave appears after a video). New save `0`, after the first career video `0x8020`, early save `0x180b7`, played saves (PC, PS3, Xbox 360) `0x183f7`.
  Without it a copied save plays the videos and the intro race first.

### Mod
Selected boss mod: a u32 behind the table (PC: low byte first, so a byte read works; `ff` = none chosen yet). [Game] Written after the next finished race.

| No. | Mod |
|---|---|
| 24 | Quadshock |
| 25 | Overbolt |
| 26 | Titanium Shield |
| 27 | Fan Nitro |
| 28 | Nitro Rift |
| 29 | Armor Plating |
| 30 | Scatter Shot |
| 31 | Super Shunt |

The number is not an index of the in-game selection order. The game has 33 `MultiplayerAbility` entries (ids 1-33; slot 3 = ids 26-33 are exactly the eight campaign mods);
the save number is not simply id - 2. [Game] A mod byte of 0, 23 or 32 is kept by the game but the car selection of a race does not open; only 24-31 are usable.
The ninth mod, Modkit, is multiplayer only.

## 7. Other structures

- **History list:** header `01 00 00 [count u32]`, then 21-byte entries sorted by event ID (`[event ID][03]...`); grows by one entry per newly played event. Meaning unknown.
- **Start of the file** (about 140 bytes): an event ID and about ten vehicle IDs; meaning unknown.
- **Multiplayer:** the four multiplayer mod loadouts are **not stored** in the save [Game] (a restart brings loadout 1 back). After a multiplayer race three places change: the byte at mod + 10 (`01` -> `00`),
  the **vehicle ID** at mod + 303 (a valid car in all 92 PC saves checked; apparently a car used last), and the 16 bits at mod + 452. A block of five similar groups follows from mod + 315. Not fully understood.
- **Not found:** a flag "credits seen"; a list of unlocked stickers (it does not exist: the counters decide).

## 8. What the game repairs on load [Game]

The game loads changed saves but corrects these on load: the level (from fans); lights of groups (from the event records, display only); groups below their lights threshold become locked (state 0) and open
groups get `E0`-`E2` available; events `E3`-`E5` locked until `E0` and `E1` are played; rival status and reward cars follow the demands (unmet demands set the rival status to 0, lock a played
One-on-One and give the reward cars back); the 12 cars of higher levels are reset to 0; some counters are recounted. The offline predictor `tools/blursave_rules.py` reproduces these corrections byte for byte
in the saves tested; the editor applies them when writing so that the save stays as written.

## 9. Paint jobs

Table: `u32` count, then one 12-byte entry per resprayed car `[vehicle ID][paint ID][index]`, directly behind it the last chosen paint `[paint ID][index]` (8 bytes). A new car is appended
(count + 1, file 12 bytes longer); a car that already has one keeps its entry (replaced in place); the "last chosen" paint is overwritten each time. [Game]

The in-game colour picker is a hexagon of 37 cells (rows of 4, 5, 6, 7, 6, 5, 4) and 4 brightness levels:
- **index** = cell in reading order from the top left, 0-36 (centre = 18, white).
- **paint ID** = name `R<row>C<column>` plus the brightness letter: level 4 (brightest) `a`, level 3 `b`, level 2 `c`. Level 1 (darkest, always black) is `Picker_Black` whatever the cell.
- The data have duplicate names: `R1C4b` (`b8060363` is level 3, `fe76c1cc` is really `R1C4c`), `R2C5a` (`53cb2675` is used, `03499198` not), `R3C5a` (`2826eee5` used, `226947c9` not).
- **Finishes:** three further sets with a prefix, `P_` (Pearlescent), `C_` (Candy) and `M_` (Metallic), only brightness `a`; they can be set in LAN/online multiplayer but not in split screen.
  [Game] The game does not offer them in the single-player picker but accepts them from the save and keeps them. The assignment of the prefixes rests on how the cars look, not on game data.
  `C_R3C5a`, `M_R2C5a` and `P_R2C2a` do not exist; `P_R2C1a` exists twice (`90c82b58`, `a83f9d44`).
- [Game] Replacing, appending and removing entries (delete the entry and decrement the count) work. An entry also works for cars without `UICanReSpray`: all 80 cars took `C_R4C4a`.

## 10. Game options

Options live in two places. [Game] Offsets are relative to `a`, the offset of the byte in front of the pattern `00 00 70 43 00 00 96 43 00 00 a0 41 00 00 20 43` (the floats 240, 300, 20, 160; on consoles in big-endian order: `43 70 00 00 ...`).

| Offset | Option | Values |
|---|---|---|
| a-15 | Difficulty (the one chosen last) | 1 Easy, 2 Medium, 3 Hard; 0 = never chosen (the game shows Easy) |
| a-13 | Controller layout | 0-2 |
| a-11 | Audio quality | 0 Low, 1 Medium, 2 High |
| a-10 | Sound effects | 0-9 |
| a-9 | Licensed soundtrack | 0 Off, 1 On |
| a-8 | Music | 0-9 |
| a-6 | Menu music | 0-9 |
| a-5 | Output | 0 Stereo, 1 Surround |
| a-4 | Room size (Advanced Audio) | 0 Small, 1 Medium, 2 Large, 3 Auditorium |
| a-3 | Dynamic range | 0 TV, 1 Home theater |
| a-2 | Music mode (Advanced Audio) | 0 Stereo, 1 Quad, 2 Surround |
| a-1 | LFE boost (Advanced Audio) | 0-9 |
| a | Brightness Adjust | stored as brightness + 1 (slider 0-9 = byte 1-10) |
| (separate) | Keyboard layout | u32 at 275 and a byte at 444 in saves looked at, always equal; 0-1 |
| (separate) | Region rule (multiplayer) | 0 Any, 1 Local preferred, 2 Local only; found at the end of a second copy of the audio pattern |

Advanced Audio is shown only for Surround output; its values stay when switching to Stereo. Offset a-7 is always 0 (a changed value is reset).
**Graphics** are not in the save but in `%APPDATA%\bizarre creations\blur\settings.xml` (two lines, not a single XML document):
`<shared_graphical_settings width height x y multisample windowed vsync graphical_detail/>`: multisample 0 Off, 1 2x, 2 4x, 3 8x; windowed 0/1; vsync 0/1; graphical_detail 1-4 = quality level 0-3.
The PS3 version has a different options menu (no graphics options).

## 11. New profile

[Game] A new profile's save already holds **all** campaign records (9 groups, 9 rivals, 63 events; the size is the same 50,903 bytes as after the first race), but not initialised: the rivals
lack the 174 in the status and the group states have leftover bytes ("01 7f 00 00"). The game fills them in while the campaign is played; a tool can do the same
(`blursave.extend_campaign`). A save that is not touched plays an intro race on the first career start; the seen-videos mask (section 6) avoids that for copied saves.

## 12. PlayStation 3 saves

Folder `SAVEDATA/BLES00759-AUTO-` (EU) or `BLUS30295-AUTO-` (US) with `AMAXSAVE`, `PARAM.SFO`, `PARAM.PFD`, `ICON0.PNG`, `PIC1.PNG`.
- **Protection** [Data]: `AMAXSAVE` is encrypted by the PS3 (`PARAM.PFD` version 3). The key of the file comes from the PFD, protected by the game's "secure file ID"
  (`BEAUTIFUL_CHAOS!`, listed in the public `games.conf` of the PS3 save tools for `BLUS30295 / BLES00759 / BLJM60244`) and a console-independent system key.
  Per file: AES-128-CBC for the entry key, then per 16-byte block AES-ECB with a counter mask. The HMAC-SHA1 of the file stored in the PFD matches, which proves the secure file ID.
  The entry of `AMAXSAVE` has only one hash (file) in the PFD; the hashes of `PARAM.SFO` and the bottom hash of the PFD depend on the SFO and the console/account data.
- **Content:** the same container as on PC but **big-endian**, 58,601 bytes unpacked. The layout is the same as on PC with the differences listed above (fans 64 bit, mod u32, statistics index u32, no constant in the rival
  status, "seen" vehicle bytes not constant). The big zero area in the middle is 5,123 bytes longer than on PC.
- **RPCS3** [Game]: the emulator reads the files of a save folder **raw** (no decryption, no PFD check), so a **decrypted** `AMAXSAVE` loads (355/450 lights, level 25 for the test save);
  the encrypted original is reported as "damaged". A save written by our tools loaded in RPCS3 and showed the expected values.
- **Real console:** not tested. It needs the encrypted file and a matching `PARAM.PFD`; our tools produce neither.

## 13. Xbox 360 saves

`41560845/00000001/AMAXSAVE` (title ID of Blur, content type "saved game"). [Data] The file is an **STFS package** (`CON `, signed by a console; the signature was not checked): header up to `0xA000`, two
hash blocks, block 0 (`0xC000`) = file table with **one file `savegame`** (2 blocks from block 1 = `0xD000`; blocks of 4096 bytes; the block `n` lies at `first + (n + 2 * (n div 0xAA + 1)) * 0x1000` for small packages).
The file inside is **not encrypted**: the same container as the PS3's (big-endian), 52,725 bytes unpacked, the same layout. The big zero area (41,230 bytes) is about as long as on PC (41,224).

## 14. Tested and not tested

Tested in the game: byte-identical round trip; loading changed saves (section 8); vehicle states; difficulty; paints and finishes; options; mod numbers 24-31 and the refusal of others;
counters and stickers; new profile; PS3 and Xbox 360 saves converted to PC saves (the game showed their level, lights and campaign); PC saves converted to PS3 saves in RPCS3.
Not tested: a real PS3 or Xbox 360; Modkit and other mod numbers; the meaning of the three places that change after a multiplayer race, of the four bytes `0f 0c 0c 05`, of the history list and of the start of the file;
online-service data.

## 15. Tools and sources

`blursave.py` (unpack / pack / check: a JSON form of the save and back), `blursave_editor.py` (the editor; button "Import PS3/Xbox" and "Export PS3"), `ps3save.py` (PS3 and Xbox 360 saves),
`blursave_rules.py` (repairs of the game). The data tables (`blursave_vehicles.json`, `blursave_ranks.json`, `blursave_campaign.json`, `blursave_stats.json`, `blursave_events.json`,
`blursave_paints.json`) were derived from the game's data files. The file readers `blurpak.py`, `blurbpr.py`, `blurico.py` follow the description in the *Blur Map Builder* (MIT, MDPRO);
the PS3 decryption follows the sources of *apollo-ps3* and *pfdtool* (Flatz). Always close the game before changing a save (it rewrites the file on exit) and keep a backup.
