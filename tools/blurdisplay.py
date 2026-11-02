"""Display texts for the save editor, in English, made from the save's own internal names and public knowledge of the game
(group, rival and mod names as used on the Blur wiki and in the trophy guides). No game file is read.

Vehicles are shown by their model name made readable (Dodge_ViperGTSR_Stock_Carver -> "Dodge Viper GTSR (Carver)").
Rival demands use the wording of the Blur wiki's "One-on-One" page where it gives one ("%d" = the number to reach); for the
others the words of the internal id are shown.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
GROUPS = ["Proving Grounds", "City Slickers", "Fan Favorite", "Crash and Burn", "Ruthless Aggression", "Midas Touch",
          "Double Damage", "Loose Cannon", "Show Down"]
RIVALS = ["Shannon", "Khan", "Rhymer", "Drayke", "Natalya", "Talon", "Ayumi and Harumi", "Carver", "Shannon"]
EVENT_KINDS = {"RaceEvent": "Race", "DestructionEvent": "Destruction", "CheckpointEvent": "Checkpoint",
               "BossEvent": "One-on-One"}
DEMANDS = {
    "Tier_Use_Powerups": "Land %d offensive Power-ups",
    "Tier_Earn_Fans": "Earn %d Fans",
    "Tier_Finish_In_Different_Car": "Finish Events in %d different cars",
    "Tier_Finish_Events": "Pass %d Events",
    "Tier_Shield_Powerups": "Shield against %d Power-ups",
    "Tier_Evade_Full_Shocks": "Evade %d Shock fields",
    "Tier_Collect_Stopwatches": "Collect %d stopwatches",
    "Event_Time_Remaining": "Pass the Event with %d seconds left",
    "Tier_Complete_FanDemands": "Complete %d Fan Demands",
    "Tier_Complete_FanRuns": "Complete %d Fan Runs",
    "Tier_Complete_FanPars": "Complete %d Fan Targets",
    "Event_Get_5X_Combo": "Get an X5 fan combo in the Event",
    "Tier_Ram_Into_Sea": "Barge %d car(s) into water",
    "Tier_Wreck": "Wreck %d cars",
    "Tier_Barge_Hits": "Barge %d cars",
    "Event_Get_All_Lights": "Get %d Lights in the Event",
    "Tier_Shunt_Hits": "Reverse Shunt %d cars",
    "Tier_Multiple_Barge_Hits": "Hit multiple cars with %d Barges",
    "Tier_Shock_Opponents": "Shock %d opponents",
    "Event_Complete_FanRun": "Complete the Fan Run in the Event",
    "Event_Wreck_And_Win": "Wreck and win the Event",
    "Tier_Shield_Mines": "Shield through %d Mines",
    "Event_Finish_In_Nats_BMW": "Win an Event in Natalya's BMW",
    "Tier_Reach_Speed": "Keep your speed over 120 mph for an entire lap",
    "Tier_Reverse_Bolt_Hits": "Land %d reverse Bolt hits",
    "Tier_Mine_Hits": "Mine %d cars",
    "Tier_Win_All_Events": "Finish first in all %d Events",
}
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def words(s):
    return _CAMEL.sub(" ", s)


MAKERS = {          # first part of the model name -> manufacturer logo (name in blursave_icons.zip, logos/<name>.png)
    "ACSchnitzer": "ac_schnitzer", "Audi": "audi", "BMW": "bmw", "Bowler": "bowler", "Chevrolet": "chevrolet",
    "Corvette": "corvette2", "Dodge": "dodge", "Foose": "foose", "Ford": "ford", "Hennessey": "hennessey",
    "Hummer": "hummer", "Koenigsegg": "koenigsegg", "LandRover": "land_rover", "Lotus": "lotus", "Nissan": "nissan",
    "Opel": "opel", "RatRod": "rat_rod", "Renault": "renault", "Shelby": "shelby", "Toyota": "toyota",
    "Vauxhall": "vauxhall", "Volkswagen": "volkswagen"}
MAKER_EXCEPTIONS = {"Corvette_ZR1": "corvette", "Dodge_Viper": "viper"}      # (the game has two Corvette logos and one for Viper)


SHORT_NAMES = {      # model name -> the name shown in the car gallery (the game's own wording, without the manufacturer)
    'Nissan_SkylineR34ZTune_Stock_Harumi': "Harumi's Skyline GT-R NISMO Z-tune",
    'Nissan_SkylineR34ZTune_Stock_Ayumi': "Ayumi's Skyline GT-R NISMO Z-tune",
    'Dodge_ViperGTSR_Stock_Carver': "Carver's Viper GTSR",
    'Renault_MeganeTrophy_Stock': 'Mégane Trophy',
    'Dodge_Challenger_Race': 'Challenger SRT8 (Race)',
    'Chevrolet_CamaroSS_Drag': 'Camaro SS (Drag)',
    'Corvette_C3_Drag': 'C3 (Drag)',
    'Ford_Supervan_Stock': 'Transit Supervan3',
    'Audi_R8V10_Stock': 'R8 4.2 FSI quattro',
    'Ford_FR100_Stock': 'FR-100',
    'Ford_MustangGTR_Stock': 'Mustang GT-R Concept',
    'Vauxhall_MonaroVXR_Drift': 'Monaro VXR (Drift)',
    'Hennessey_ViperVenom1000Coupe_Stock': 'Viper Venom 1000',
    'Corvette_C3_Race': 'C3 (Race)',
    'Koenigsegg_CCXR_Stock': 'CCX-R',
    'Nissan_SkylineR34ZTune_Stock': 'Skyline GT-R NISMO Z-tune',
    'Dodge_ViperGTSR_Stock': 'Viper GTSR',
    'Opel_AstraExtreme_Stock': 'Astra Extreme',
    'Opel_AstraExtreme_Stock_Shannon': "Shannon's Astra Extreme",
    'BMW_1SeriesTii_Race_Natalya': "Natalya's Concept 1 Series tii (Race)",
    'Corvette_ZR1_Stock_Talon': "Talon's ZR1",
    'Volkswagen_Scirocco_24': 'Scirocco 24',
    'Bowler_Nemesis_Stock': 'Nemesis',
    'Corvette_C3_Rat': 'C3 (Rat)',
    'Dodge_Challenger_Tuner': 'Challenger SRT8 (Tuner)',
    'Dodge_ViperACR_Stock': 'Viper ACR',
    'Ford_F100_OffRoad': 'F-100 (Off-Road)',
    'BMW_M3E92_Drift': 'M3 E92 (Drift)',
    'Ford_GT_Stock': 'Ford GT',
    'Chevrolet_SoCalHHR_Stock': 'HHR (Race)',
    'Lotus_ExigeCup260_Stock': 'Exige Cup 260',
    'BMW_X548MSport_Stock': 'X5 xDrive48i M Sport',
    'Volkswagen_GolfW12650_Stock': 'Golf W12 650',
    'Ford_FocusRS_Race': 'Focus RS (Race)',
    'BMW_1SeriesTii_Race': 'Concept 1 Series tii (Race)',
    'Corvette_ZR1_Stock': 'ZR1',
    'Chevrolet_CamaroSS_Stock_Rymer': "Rhymer's Camaro SS",
    'Hummer_H2_OffRoad_Drayke': "Drayke's H2 (Off-Road)",
    'LandRover_LRX_Stock': 'LRX',
    'Audi_TT_Stock': 'TTS Coupé',
    'Nissan_350Z_Drift': '350Z (Drift)',
    'Ford_F150_OffRoad': 'F-150 SVT Raptor R (Off-Road)',
    'Ford_F100_Rat': 'F-100 (Rat)',
    'Toyota_Supra_Smooth': 'Supra (Smooth)',
    'Hummer_H2_Rat': 'H2 (Rat)',
    'Ford_Bronco_OffRoad': 'Bronco (Off-Road)',
    'BMW_M3E92_Tuner': 'M3 E92 (Tuner)',
    'Shelby_MustangGT500_Stock': 'Ford Shelby GT500',
    'Nissan_Navara_Rat': 'Navara (Rat)',
    'Volkswagen_Beetle_OffRoad': 'Beetle (Off-Road)',
    'Foose_69_Stock': '69 Camaro',
    'Chevrolet_CamaroSS_Stock': 'Camaro SS',
    'Hummer_H2_OffRoad': 'H2 (Off-Road)',
    'Renault_MeganeSportR26_Stock_Shannon': "Shannon's R230 F1 Team R26",
    'Foose_Stallion_Stock_Khan': "Khan's Stallion Ford Mustang",
    'Ford_FocusRS_Stock': 'Focus RS',
    'Chevrolet_Camaro_Stock': 'Camaro',
    'LandRover_DefenderSVX_Stock': 'Defender SVX',
    'Dodge_Challenger_Stock': 'Challenger SRT8',
    'Nissan_Navara_OffRoad': 'Navara (Off-Road)',
    'Volkswagen_Beetle_Rat': 'Beetle (Rat)',
    'Nissan_350ZNismo_Stock': '350Z NISMO S-tune',
    'BMW_1SeriesTii_Stock': 'Concept 1 Series tii',
    'Chevrolet_Camaro_Rat': 'Camaro (Rat)',
    'Audi_S3_Stock': 'S3',
    'Toyota_SupraTRD_Stock': 'Supra',
    'ACSchnitzer_ACS1Coupe_Stock': 'ACS1 Coupé',
    'RatRod_NA_Stock': 'Rat Rod',
    'Renault_MeganeSportR26_Stock': 'R230 F1 Team R26',
    'Foose_Stallion_Stock': 'Stallion Ford Mustang',
    'ACSchnitzer_ACS1Coupe_Legend_I': 'Legendary ACS1 Coupé',
    'Audi_TT_Legend_VI': 'Legendary TTS Coupé',
    'BMW_M3E92_Legend_IX': 'Legendary M3 (E92)',
    'Bowler_Nemesis_Legend_VII': 'Legendary Nemesis',
    'Chevrolet_Camaro_Legend_II': 'Legendary Camaro SS',
    'Dodge_Challenger_Legend_V': 'Legendary Challenger SRT8',
    'Dodge_ViperACR_Legend_III': 'Legendary Viper ACR',
    'Ford_MustangGTR_Legend_X': 'Legendary Mustang GT-R Concept',
    'Opel_Astra_Extreme_Legend_VIII': 'Legendary Astra Extreme',
    'Vauxhall_MonaroVXR_Legend_IV': 'Legendary Monaro VXR',
}
GALLERY_ORDER = {   # class -> the cars in the order of the game's car list; cars that are not named here follow at the end
    'A': [
        'Nissan_SkylineR34ZTune_Stock_Harumi',
        'Nissan_SkylineR34ZTune_Stock_Ayumi',
        'Dodge_ViperGTSR_Stock_Carver',
        'Renault_MeganeTrophy_Stock',
        'Dodge_Challenger_Race',
        'Chevrolet_CamaroSS_Drag',
        'Corvette_C3_Drag',
        'Ford_Supervan_Stock',
        'Audi_R8V10_Stock',
        'Ford_FR100_Stock',
        'Ford_MustangGTR_Stock',
        'Vauxhall_MonaroVXR_Drift',
        'Hennessey_ViperVenom1000Coupe_Stock',
        'Corvette_C3_Race',
        'Koenigsegg_CCXR_Stock',
        'Nissan_SkylineR34ZTune_Stock',
        'Dodge_ViperGTSR_Stock',
        'Opel_AstraExtreme_Stock',
        'Opel_AstraExtreme_Stock_Shannon',
    ],
    'B': [
        'BMW_1SeriesTii_Race_Natalya',
        'Corvette_ZR1_Stock_Talon',
        'Volkswagen_Scirocco_24',
        'Bowler_Nemesis_Stock',
        'Corvette_C3_Rat',
        'Dodge_Challenger_Tuner',
        'Dodge_ViperACR_Stock',
        'Ford_F100_OffRoad',
        'BMW_M3E92_Drift',
        'Ford_GT_Stock',
        'Chevrolet_SoCalHHR_Stock',
        'Lotus_ExigeCup260_Stock',
        'BMW_X548MSport_Stock',
        'Volkswagen_GolfW12650_Stock',
        'Ford_FocusRS_Race',
        'BMW_1SeriesTii_Race',
        'Corvette_ZR1_Stock',
    ],
    'C': [
        'Chevrolet_CamaroSS_Stock_Rymer',
        'Hummer_H2_OffRoad_Drayke',
        'LandRover_LRX_Stock',
        'Audi_TT_Stock',
        'Nissan_350Z_Drift',
        'Ford_F150_OffRoad',
        'Ford_F100_Rat',
        'Toyota_Supra_Smooth',
        'Hummer_H2_Rat',
        'Ford_Bronco_OffRoad',
        'BMW_M3E92_Tuner',
        'Shelby_MustangGT500_Stock',
        'Nissan_Navara_Rat',
        'Volkswagen_Beetle_OffRoad',
        'Foose_69_Stock',
        'Chevrolet_CamaroSS_Stock',
        'Hummer_H2_OffRoad',
    ],
    'D': [
        'Renault_MeganeSportR26_Stock_Shannon',
        'Foose_Stallion_Stock_Khan',
        'Ford_FocusRS_Stock',
        'Chevrolet_Camaro_Stock',
        'LandRover_DefenderSVX_Stock',
        'Dodge_Challenger_Stock',
        'Nissan_Navara_OffRoad',
        'Volkswagen_Beetle_Rat',
        'Nissan_350ZNismo_Stock',
        'BMW_1SeriesTii_Stock',
        'Chevrolet_Camaro_Rat',
        'Audi_S3_Stock',
        'Toyota_SupraTRD_Stock',
        'ACSchnitzer_ACS1Coupe_Stock',
        'RatRod_NA_Stock',
        'Renault_MeganeSportR26_Stock',
        'Foose_Stallion_Stock',
    ],
}


def maker_logo(model_name):
    """name of the manufacturer logo of a car, e.g. Dodge_ViperGTSR_Stock -> "viper"; None if there is none"""
    for prefix, logo in MAKER_EXCEPTIONS.items():
        if model_name.startswith(prefix):
            return logo
    return MAKERS.get(model_name.split("_")[0])


GAME_NAMES = {      # model name -> the car's name as it is listed on the Blur wiki (taken from the wiki's car list, 2026-11-01)
    "ACSchnitzer_ACS1Coupe_Legend_I": "AC Schnitzer Legendary ACS1 Coupé", "ACSchnitzer_ACS1Coupe_Stock": "AC Schnitzer ACS1 Coupé",
    "Audi_R8V10_Stock": "Audi R8 4.2 FSI Quattro", "Audi_S3_Stock": "Audi S3", "Audi_TT_Legend_VI": "Audi Legendary TTS Coupé",
    "Audi_TT_Stock": "Audi TTS Coupé", "BMW_1SeriesTii_Race": "BMW Concept 1 Series tii (Race)",
    "BMW_1SeriesTii_Race_Natalya": "Natalya's BMW Concept 1 Series tii (Race)", "BMW_1SeriesTii_Stock": "BMW Concept 1 Series tii",
    "BMW_M3E92_Drift": "BMW M3 E92 (Drift)", "BMW_M3E92_Legend_IX": "BMW Legendary M3 (E92)", "BMW_M3E92_Tuner": "BMW M3 E92 (Tuner)",
    "BMW_X548MSport_Stock": "BMW X5 xDrive48i M Sport", "Bowler_Nemesis_Legend_VII": "Bowler Legendary Nemesis",
    "Bowler_Nemesis_Stock": "Bowler Nemesis", "Chevrolet_CamaroSS_Drag": "Chevrolet Camaro SS (Drag)",
    "Chevrolet_CamaroSS_Stock": "Chevrolet Camaro SS", "Chevrolet_CamaroSS_Stock_Rymer": "Rhymer's Chevrolet Camaro SS",
    "Chevrolet_Camaro_Legend_II": "Chevrolet Legendary Camaro SS", "Chevrolet_Camaro_Rat": "Chevrolet Camaro (Rat)",
    "Chevrolet_Camaro_Stock": "Chevrolet Camaro", "Chevrolet_SoCalHHR_Stock": "Chevrolet HHR (Race)",
    "Corvette_C3_Drag": "Corvette C3 (Drag)", "Corvette_C3_Race": "Corvette C3 (Race)", "Corvette_C3_Rat": "Corvette C3 (Rat)",
    "Corvette_ZR1_Stock": "Chevrolet Corvette ZR1", "Corvette_ZR1_Stock_Talon": "Talon's Corvette ZR1",
    "Dodge_Challenger_Legend_V": "Dodge Legendary Challenger SRT8", "Dodge_Challenger_Race": "Dodge Challenger (Race)",
    "Dodge_Challenger_Stock": "Dodge Challenger SRT8", "Dodge_Challenger_Tuner": "Dodge Challenger (Tuner)",
    "Dodge_ViperACR_Legend_III": "Dodge Legendary Viper ACR", "Dodge_ViperACR_Stock": "Dodge Viper ACR",
    "Dodge_ViperGTSR_Stock": "Dodge Viper GTSR", "Dodge_ViperGTSR_Stock_Carver": "Carver's Dodge Viper GTSR",
    "Foose_69_Stock": "Foose 69 Camaro", "Foose_Stallion_Stock": "Foose Stallion Ford Mustang",
    "Foose_Stallion_Stock_Khan": "Khan's Foose Stallion Ford Mustang", "Ford_Bronco_OffRoad": "Ford Bronco (Off-Road)",
    "Ford_F100_OffRoad": "Ford F-100 (Off-Road)", "Ford_F100_Rat": "Ford F-100 (Rat)",
    "Ford_F150_OffRoad": "Ford F-150 SVT Raptor (Off-Road)", "Ford_FR100_Stock": "Ford FR-100",
    "Ford_FocusRS_Race": "Ford Focus RS (Race)", "Ford_FocusRS_Stock": "Ford Focus RS", "Ford_GT_Stock": "Ford GT",
    "Ford_MustangGTR_Legend_X": "Ford Legendary Mustang GT-R Concept", "Ford_MustangGTR_Stock": "Ford Mustang GT-R Concept",
    "Ford_Supervan_Stock": "Ford Transit Supervan3", "Hennessey_ViperVenom1000Coupe_Stock": "Dodge Viper Venom 1000",
    "Hummer_H2_OffRoad": "Hummer H2 (Off-Road)", "Hummer_H2_OffRoad_Drayke": "Drayke's Hummer H2 (Off-Road)",
    "Hummer_H2_Rat": "Hummer H2 (Rat)", "Koenigsegg_CCXR_Stock": "Koenigsegg CCX-R",
    "LandRover_DefenderSVX_Stock": "Land Rover Defender SVX", "LandRover_LRX_Stock": "Land Rover LRX",
    "Lotus_ExigeCup260_Stock": "Lotus Exige Cup 260", "Nissan_350ZNismo_Stock": "Nissan 350Z NISMO Z-tune",
    "Nissan_350Z_Drift": "Nissan 350Z (Drift)", "Nissan_Navara_OffRoad": "Nissan Navara (Off-Road)",
    "Nissan_Navara_Rat": "Nissan Navara (Rat)", "Nissan_SkylineR34ZTune_Stock": "Nissan Skyline GT-R NISMO Z-tune",
    "Nissan_SkylineR34ZTune_Stock_Ayumi": "Ayumi's Nissan Skyline GT-R NISMO Z-tune",
    "Nissan_SkylineR34ZTune_Stock_Harumi": "Harumi's Nissan Skyline GT-R NISMO Z-tune",
    "Opel_AstraExtreme_Stock": "Opel Astra Extreme", "Opel_AstraExtreme_Stock_Shannon": "Shannon's Opel Astra Extreme",
    "Opel_Astra_Extreme_Legend_VIII": "Opel Legendary Astra Extreme", "RatRod_NA_Stock": "Rat Rod",
    "Renault_MeganeSportR26_Stock": "Renault R230 F1 Team R26",
    "Renault_MeganeSportR26_Stock_Shannon": "Shannon's Renault R230 F1 Team R26",
    "Renault_MeganeTrophy_Stock": "Renault Mégane Trophy", "Shelby_MustangGT500_Stock": "Ford Shelby GT500",
    "Toyota_SupraTRD_Stock": "Toyota Supra", "Toyota_Supra_Smooth": "Toyota Supra (Smooth)",
    "Vauxhall_MonaroVXR_Drift": "Vauxhall Monaro VXR (Drift)", "Vauxhall_MonaroVXR_Legend_IV": "Vauxhall Legendary Monaro VXR",
    "Volkswagen_Beetle_OffRoad": "Volkswagen Beetle (Off-Road)", "Volkswagen_Beetle_Rat": "Volkswagen Beetle (Rat)",
    "Volkswagen_GolfW12650_Stock": "Volkswagen Golf W12 650", "Volkswagen_Scirocco_24": "Volkswagen Scirocco 24"}


def vehicle_text(model_name):
    """the wiki's name of the car; unknown models: Opel_AstraExtreme_Stock_Shannon -> "Opel Astra Extreme (Shannon)" """
    if model_name in GAME_NAMES:
        return GAME_NAMES[model_name]
    parts = [p for p in model_name.split("_") if p.lower() != "stock"]
    head = " ".join(words(p) for p in parts[:2])
    rest = " ".join(words(p) for p in parts[2:])
    return "%s (%s)" % (head, rest) if rest else head


def demand_text(demand_id):
    """known wording, or the id's words ("Tier_Nitro_Ram" -> "Nitro Ram: %d")"""
    return DEMANDS.get(demand_id) or words(demand_id.split("_", 1)[-1]) + ": %d"


def load():
    vehicles = json.load(open(os.path.join(HERE, "blursave_vehicles.json"), encoding="utf-8"))
    campaign = json.load(open(os.path.join(HERE, "blursave_campaign.json"), encoding="utf-8"))
    names = {uid: vehicle_text(e["name"]) for uid, e in vehicles.items()}
    seen = {}
    for uid, t in names.items():                          # names must be unique (the car list is picked by name)
        seen.setdefault(t, []).append(uid)
    for t, uids in seen.items():
        if len(uids) > 1:
            for uid in uids:
                names[uid] = "%s [%s]" % (t, uid[:4])
    return {
        "vehicles": names,
        "tiers": list(GROUPS),
        "bosses": list(RIVALS),
        "event_kinds": dict(EVENT_KINDS),
        "demands": {d: demand_text(d) for t in campaign for d in t["boss_demands"]},
    }
