"""What the game derives from a save when it loads it - for the save editor's preview and for "normalising" an edited save.

The game recomputes or repairs a number of fields (see BLURSAVE_FORMAT.md, section 9, tests A to D). This module does the
same on a decoded doc (blursave.make_doc), so an edited save already is what the game would make of it. Every rule
carries a status: "Game" = seen in the game, "Guess" = guessed, not checked. Nothing here writes a file.
"""
import json
import os

import blurdisplay
import blursave as bs

HERE = os.path.dirname(os.path.abspath(__file__))
RANKS = json.load(open(os.path.join(HERE, "blursave_ranks.json")))
CAMPAIGN = json.load(open(os.path.join(HERE, "blursave_campaign.json")))
TEXT = blurdisplay.load()

PLACE_LIGHTS = {3: 5, 2: 4, 1: 3, 0: 0}          # flags[1]: 3 = first place, 2 = second, 1 = third, 0 = no podium
LOCKED, AVAILABLE, PLAYED = 0, 1, 2              # flags[0]

# Boss reward cars. "unlock" comes with the boss demands (boss status byte 0), "defeat" with the win (byte 1).
# Revoked by the game when the status is missing: tiers 4 to 9 (test D) and tiers 1 to 3 (test of 2026-11-01).
REWARDS = {
    1: ({"Renault_MeganeSportR26_Stock"}, {"Renault_MeganeSportR26_Stock_Shannon"}),
    2: ({"Foose_Stallion_Stock"}, {"Foose_Stallion_Stock_Khan"}),
    3: ({"Chevrolet_CamaroSS_Stock", "Chevrolet_Camaro_Legend_II"}, {"Chevrolet_CamaroSS_Stock_Rymer"}),
    4: ({"Hummer_H2_OffRoad"}, {"Hummer_H2_OffRoad_Drayke"}),
    5: ({"BMW_1SeriesTii_Race"}, {"BMW_1SeriesTii_Race_Natalya"}),
    6: ({"Corvette_ZR1_Stock"}, {"Corvette_ZR1_Stock_Talon"}),
    7: ({"Nissan_SkylineR34ZTune_Stock"}, {"Nissan_SkylineR34ZTune_Stock_Ayumi", "Nissan_SkylineR34ZTune_Stock_Harumi"}),
    8: ({"Dodge_ViperGTSR_Stock"}, {"Dodge_ViperGTSR_Stock_Carver"}),
    9: ({"Opel_AstraExtreme_Stock", "Opel_Astra_Extreme_Legend_VIII"}, {"Opel_AstraExtreme_Stock_Shannon"}),
}
REWARD_CARS = {n for a, b in REWARDS.values() for n in a | b}


def rank_for_fans(fans):
    """(rank, fans needed for this rank, fans for the next rank or None)"""
    cur = max(r["rank"] for r in RANKS if r["fans"] <= fans)
    nxt = [r["fans"] for r in RANKS if r["rank"] == cur + 1]
    return cur, [r["fans"] for r in RANKS if r["rank"] == cur][0], (nxt[0] if nxt else None)


def event_lights(ev, tdef):
    """lights of one event record (ev from the doc, tdef the matching entry of blursave_campaign.json)"""
    st, place, _, tunnel = ev["flags"]
    if st == LOCKED:                                    # also a One-on-One that the game locked again (test F: 426 instead of 450)
        return 0
    if tdef["type"] == "BossEvent":
        return 8 if (st == PLAYED and place == 3) else 0
    return PLACE_LIGHTS.get(place, 0) + int(ev["info_a"] >= tdef["fan_par"]) + int(bool(tunnel))


def tier_defs():
    """[(tier entry of the doc, tier entry of blursave_campaign.json), ...] - same order"""
    return CAMPAIGN


def total_lights(doc):
    total = 0
    for t, tdef in zip(doc["campaign"], CAMPAIGN):
        for ev, edef in zip(t["events"], tdef["events"]):
            total += event_lights(ev, dict(edef))
    return total


def tier_lights(t, tdef):
    return sum(event_lights(ev, edef) for ev, edef in zip(t["events"], tdef["events"]))


def boss_met(t):
    return all(c >= g for c, g in zip(t["boss"]["counters"], t["boss"]["targets"]))


def car_text(v):
    return TEXT["vehicles"].get(v["id"], v["name"])


def event_text(n, i):
    return "Group %d, %s" % (n, "One-on-One" if i == 6 else "Event %d" % (i + 1))


def normalise(doc):
    """Applies the game's repairs to `doc` in place. Returns a list of (status, text) for everything that changed."""
    changes = []
    note = lambda status, text: changes.append((status, text))
    p = doc["profile"]
    lvl = rank_for_fans(p["fans"]["value"])[0]
    if p["fan_level"]["value"] != lvl:
        p["fan_level"]["value"] = lvl
        note("Game", "Fan Status set to %d (worked out from the fans)" % lvl)
    veh = {v["name"]: v for v in doc["vehicles"]}
    for r in RANKS:                                      # rank cars: only for ranks the fans reach (test E)
        for name in r["vehicles"]:
            v = veh.get(name)
            if v is None:
                continue
            if r["rank"] > lvl and v["state"] != 0:
                v["state"] = 0
                note("Game", "%s taken back (only from Fan Status %d)" % (car_text(v), r["rank"]))
            elif r["rank"] <= lvl and v["state"] == 0 and name not in REWARD_CARS:
                v["state"] = 1
                note("Guess", "%s awarded (Fan Status %d reached)" % (car_text(v), r["rank"]))
    total = total_lights(doc)
    for t, tdef in zip(doc["campaign"], CAMPAIGN):
        n = t["tier"]
        unlocked = total >= tdef["lights_needed_to_unlock"]
        st = t["state"]["value"]
        if not unlocked and st != 0:
            t["state"]["value"] = 0
            note("Game", "Group %d locked (%d lights, %d needed)" % (n, total, tdef["lights_needed_to_unlock"]))
        elif unlocked and st == 0:
            t["state"]["value"] = 1
            note("Guess", "Group %d unlocked, marked as new" % n)
        ev = t["events"]
        for i, e in enumerate(ev[:6]):
            f = e["flags"]
            if f[0] == PLAYED:
                continue
            want = LOCKED
            if unlocked and (i < 3 or (ev[0]["flags"][0] == PLAYED and ev[1]["flags"][0] == PLAYED)):
                want = AVAILABLE
            if f[0] != want:
                f[0] = want
                # seen: E0-E2 open with the tier, E3-E5 shut again while E0/E1 are not played (tests B, D);
                # guessed: E3-E5 open once E0 and E1 are played (seen in the game, but not forced by a test)
                note("Guess" if (want == AVAILABLE and i >= 3) else "Game",
                     "%s: %s" % (event_text(n, i), "unlocked" if want else "locked"))
        met = boss_met(t)
        b = t["boss"]["status"]
        if b[0] != int(met):
            b[0] = int(met)
            note("Game", "Group %d: rival demands %s" % (n, "met" if met else "not met"))
        boss = ev[6]
        if boss["flags"][0] != PLAYED:
            want = AVAILABLE if (met and unlocked) else LOCKED
            if boss["flags"][0] != want:
                boss["flags"][0] = want
                note("Game", "%s: %s" % (event_text(n, 6), "unlocked" if want else "locked"))
        elif not met:                  # tiers 1 to 3 seen in the game (2026-11-01); the same is assumed for the other tiers
            boss["flags"][0] = LOCKED
            note("Game" if n <= 3 else "Guess", "%s: locked again (rival demands not met)" % event_text(n, 6))
        won = boss["flags"][0] == PLAYED and boss["flags"][1] == 3
        if b[1] != int(won):
            b[1] = int(won)
            note("Guess", "Group %d: rival %s" % (n, "defeated" if won else "not defeated"))
        unlock_cars, defeat_cars = REWARDS[n]
        for names, have in ((unlock_cars, bool(b[0])), (defeat_cars, bool(b[1]))):
            for name in names:
                v = veh.get(name)
                if v is None:
                    continue
                if have and v["state"] == 0:
                    v["state"] = 1
                    note("Game", "%s awarded" % car_text(v))
                elif not have and v["state"] != 0:
                    v["state"] = 0
                    note("Game", "%s taken back" % car_text(v))
    total = total_lights(doc)                            # again: events the game locked again no longer count
    lights = p.get("lights")
    if lights and lights["value"] != total:
        lights["value"] = float(total)
        note("Guess", "Lights counter set to %d (the game shows the total of the events)" % total)
    return changes
