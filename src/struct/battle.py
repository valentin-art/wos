from dataclasses import dataclass, field
from typing import List
import warnings

warnings.filterwarnings("ignore")


@dataclass
class Hero:
    name: str
    level: float
    stars: float


@dataclass
class ArmyBonuses:
    inf_atk: float
    inf_def: float
    inf_lth: float
    inf_hp: float
    spr_atk: float
    spr_def: float
    spr_lth: float
    spr_hp: float
    arc_atk: float
    arc_def: float
    arc_lth: float
    arc_hp: float


@dataclass
class TroopComposition:
    infantry: float
    spearman: float
    archer: float


@dataclass
class BattleOutcomeStats:
    losses: float
    wounded: float
    lightly_wounded: float
    survivors: float


@dataclass
class Side:
    N: float
    power_change: float
    composition: TroopComposition
    bonuses: ArmyBonuses
    heroes: List[Hero] = field(default_factory=list)
    outcome_stats: BattleOutcomeStats | None = None


@dataclass
class Battle:
    battle_id: int
    outcome: int  # 1 = blue wins, 0 = red wins
    blue: Side
    red: Side
