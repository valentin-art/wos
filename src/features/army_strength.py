from typing import Dict, List
import numpy as np
from src.struct.battle import Hero, ArmyBonuses


def compute_B_off(bonuses: ArmyBonuses) -> Dict[str, float]:
    return {
        "inf": (1 + bonuses.inf_atk) * (1 + bonuses.inf_lth),
        "spr": (1 + bonuses.spr_atk) * (1 + bonuses.spr_lth),
        "arc": (1 + bonuses.arc_atk) * (1 + bonuses.arc_lth),
    }


def compute_B_def(bonuses: ArmyBonuses) -> Dict[str, float]:
    return {
        "inf": (1 + bonuses.inf_def) * (1 + bonuses.inf_hp),
        "spr": (1 + bonuses.spr_def) * (1 + bonuses.spr_hp),
        "arc": (1 + bonuses.arc_def) * (1 + bonuses.arc_hp),
    }


def compute_Q(B: Dict[str, float], w: np.ndarray, power: float) -> np.ndarray:
    vals = np.array([B["inf"], B["spr"], B["arc"]])
    return w * (vals ** power)


def hero_factor(
    heroes: List[Hero], hero_index: Dict[str, int], beta: np.ndarray
) -> float:
    """
    H = 1 + Σ_h β_h * I(hero h present)
    beta: vector of length n_heroes
    """
    excess = 0.0
    for h in heroes:
        name = h.name
        stars = h.stars
        if name and name.lower() not in ("none", "none_infantry", ""):
            idx = hero_index.get(name)
            if idx is not None:
                excess += beta[idx]**round(stars, 0)
    return 1.0 + excess
