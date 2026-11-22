"""Campaign data; all maps are original scenario layouts for this prototype."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Mission:
    title: str
    location: str
    width: int
    height: int
    terrain: str
    objective: str
    objective_tile: tuple[int, int]
    objective_time: float
    enemy_count: int
    ally_count: int
    briefing: str
    mode: str = "capture"
    holdout_seconds: float = 120.0


CAMPAIGNS = [
        Mission("FIRST WAVE", "OMAHA BEACH", 104, 58, "beach", "SILENCE THE BEACH BUNKER", (79, 17), 8, 50, 8,
            "Get off the shingle. Break the wire, flank the bunker, and clear the seawall."),
        Mission("THE SUNKEN LANE", "VIERVILLE APPROACH", 100, 64, "bocage", "TAKE THE FARM CROSSROADS", (74, 32), 10, 52, 8,
            "The hedgerows hide a gun line. Scout the lanes and keep moving between cover."),
        Mission("HEDGEROW HELL", "LA CAMBE", 112, 68, "bocage", "HOLD THE ORCHARD", (83, 25), 12, 56, 9,
            "The enemy has turned every field into a strongpoint. Hold the orchard through the counterattack.", "holdout", 100),
        Mission("CROSSROADS AT ST. CLAIRE", "ST. CLAIRE", 100, 64, "town", "CLEAR THE TOWN SQUARE", (75, 38), 12, 56, 9,
            "Clear each street corner. German patrols are moving between the ruins."),
        Mission("BRIDGE AT ROUVRES", "ROUVRES", 104, 66, "river", "DESTROY THE BRIDGE", (78, 29), 12, 58, 9,
            "Reach the far bank and demolish the bridge before the defenders regroup.", "destroy"),
        Mission("NIGHT RAID", "RADAR RIDGE", 112, 68, "ridge", "HOLD THE RADAR RIDGE", (84, 22), 10, 60, 10,
            "Searchlights sweep the ridge. Secure the station and survive the counterattack.", "holdout", 110),
        Mission("THE FIRING BATTERY", "LONGUES-SUR-MER", 116, 68, "ridge", "DESTROY THE COASTAL GUN", (88, 42), 14, 62, 10,
            "Infantry and armor defend the battery. Destroy the coastal gun.", "destroy"),
        Mission("BREAKOUT AT FALAISE", "FALAISE ROAD", 120, 72, "town", "OPEN THE INLAND ROAD", (91, 34), 16, 64, 10,
            "The final road is defended in depth. Stay with your squad and punch through."),
]
