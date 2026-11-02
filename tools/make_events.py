"""Writes blursave_events.json: for every campaign event (T1E0 ... T9E6) its route, city, the name of the city's landmark shape (location_icons.ipf) and its kind.

Development tool. Needs the unpacked game database (gamedata/xt/singleplayer.bin, cityandroutenames.loc) and the KSLF reader of the
Blur Map Builder (MIT licence, kslf/dump.py); pass the folder that contains dump.py and the folder of the unpacked xt files:
    py make_events.py <map builder source>/kslf <...>/gamedata/xt
"""
import json
import os
import re
import sys

import blurloc

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = {"AmaxRaceModeStreetRace": "Race", "AmaxRaceModeDestruction": "Destruction", "AmaxRaceModeCheckpoint": "Checkpoint",
         "AmaxRaceModeBossBattle": "One-on-One"}
CITY_KEY = {"LongBeachDocks": "LA_DOCKS", "MHaruna": "MOUNT_HARUNA", "Hackney": "HACKNEY", "Observatory": "LA_OBSERVATORY"}


CITY_ICON = {"Barcelona Gracia": "barcelona", "Barcelona Oval": "oval", "Brighton": "brighton", "Hackney": "hackney",   # shapes of location_icons.ipf
             "Hollywood Hills": "la_observatory", "LA Docks": "la_docks", "LA Downtown": "la_downtown", "LA River": "la_river",
             "Mount Haruna": "mount_haruna", "NY Dumbo": "dumbo", "SanFran Russian Hill": "russian_hill",
             "SanFran Sausalito": "san_francisco", "Tokyo Shutoko": "japan_shutoko", "Amboy": "amboy"}


def city_key(route):
    """route name (USA_LA_Downtown_6) -> (picture name USA_LA_Downtown, key CRN_... of the city name)"""
    parts = route.split("_")
    picture = "_".join(parts[:-1])
    tail = parts[-2]
    key = CITY_KEY.get(tail) or "_".join(parts[1:-1]).upper()
    if parts[1] == "SanFran":
        key = "SANFRAN_" + parts[2].upper()
    if parts[1] == "NY":
        key = "NY_DUMBO"
    if parts[1] == "Tokyo":
        key = "TOKYO_SHUTOKO"
    return picture, "CRN_" + key


def main(kslf, xt):
    sys.path.insert(0, kslf)
    import dump
    names = json.load(open(os.path.join(HERE, "blursave_names.json"), encoding="utf-8"))
    text = blurloc.read_loc(os.path.join(xt, "loc", "cityandroutenames.loc"))
    f = dump.File(os.path.join(xt, "singleplayer.bin"))
    out = {}
    for o in f.O:
        if o["blocks"][0]["name"] != "AmaxEvent":
            continue
        v = f.top(o)
        n = v.get("Name", "")
        if not re.fullmatch(r"T\dE\d", n):
            continue
        route = names[v["Route"]["uid"].lower()]["name"]
        picture, key = city_key(route)
        out[n] = {"route": route, "city": text[key], "icon": CITY_ICON[text[key]], "kind": KINDS[v["RaceMode"]["_type"]]}
    json.dump(out, open(os.path.join(HERE, "blursave_events.json"), "w"), indent=0, sort_keys=True)
    print(len(out), "events;", len({e["city"] for e in out.values()}), "cities:", sorted({e["city"] for e in out.values()}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
