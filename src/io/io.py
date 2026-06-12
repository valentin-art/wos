import json
import os
from typing import List, Optional

from src.struct.battle import (
    TroopComposition,
    ArmyBonuses,
    BattleOutcomeStats,
    Hero,
    Side,
    Battle,
)


def parse_army_bonuses(bonuses_dict: dict) -> ArmyBonuses:
    inf = bonuses_dict["inf"]
    spr = bonuses_dict["spr"]
    arc = bonuses_dict["arc"]
    return ArmyBonuses(
        inf_atk=inf["atk"],
        inf_def=inf["def"],
        inf_lth=inf["lth"],
        inf_hp=inf["hp"],
        spr_atk=spr["atk"],
        spr_def=spr["def"],
        spr_lth=spr["lth"],
        spr_hp=spr["hp"],
        arc_atk=arc["atk"],
        arc_def=arc["def"],
        arc_lth=arc["lth"],
        arc_hp=arc["hp"],
    )


def parse_composition(comp_dict: dict) -> TroopComposition:
    return TroopComposition(
        infantry=comp_dict.get("infantry") or 0,
        spearman=comp_dict.get("spearman") or 0,
        archer=comp_dict.get("archer") or 0,
    )


def parse_outcome_stats(stats_dict: Optional[dict]) -> Optional[BattleOutcomeStats]:
    if stats_dict is None:
        return None
    return BattleOutcomeStats(
        losses=stats_dict.get("losses") or 0,
        wounded=stats_dict.get("wounded") or 0,
        lightly_wounded=stats_dict.get("lightly_wounded") or 0,
        survivors=stats_dict.get("survivors") or 0,
    )


def parse_heroes(heroes_list: list) -> List[Hero]:
    heroes = []
    for h in heroes_list:
        name = h.get("name", "") if h is not None else ""
        level = h.get("level") or 0 if h is not None else 0
        stars = h.get("stars") or 0 if h is not None else 0
        # skip placeholder entries
        if not name or name.lower() in ("none", "none_infantry", ""):
            continue
        heroes.append(Hero(name=name, level=float(level), stars=float(stars)))
    return heroes


def parse_side(side_dict: dict) -> Side:
    return Side(
        N=float(side_dict["N"]),
        power_change=float(side_dict.get("power_change", 0)),
        composition=parse_composition(side_dict.get("composition", {})),
        bonuses=parse_army_bonuses(side_dict["bonuses"]),
        heroes=parse_heroes(side_dict.get("heroes", [])),
        outcome_stats=parse_outcome_stats(side_dict.get("outcome_stats")),
    )


def parse_battle(battle_dict: dict) -> Battle:

    battle = Battle(
        battle_id=battle_dict["battle_id"],
        outcome=int(battle_dict["outcome"]),
        blue=parse_side(battle_dict["blue"]),
        red=parse_side(battle_dict["red"]),
    )
    return battle


def load_battles_from_json(path: str) -> List[Battle]:
    """
    Load battles from either:
      - a single JSON file containing a list of battle dicts, or
      - a single JSON file containing one battle dict, or
      - a directory of JSON files (one battle per file, or lists)

    Args:
        path: path to a .json file or a directory

    Returns:
        List of Battle objects ready for model estimation
    """
    battles = []

    if os.path.isdir(path):
        files = sorted(f for f in os.listdir(path) if f.endswith(".json"))
        if not files:
            raise ValueError(f"No .json files found in directory: {path}")
        for fname in files:
            fpath = os.path.join(path, fname)
            battles.extend(_load_from_file(fpath))

    elif os.path.isfile(path):
        battles.extend(_load_from_file(path))

    else:
        raise FileNotFoundError(f"Path not found: {path}")

    # sort by battle_id for reproducibility
    battles.sort(key=lambda b: b.battle_id)

    print(f"Loaded {len(battles)} battles.")
    _print_summary(battles)
    return battles


def _load_from_file(fpath: str) -> List[Battle]:
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [parse_battle(d) for d in data]
    elif isinstance(data, dict):
        return [parse_battle(data)]
    else:
        raise ValueError(f"Unexpected JSON structure in {fpath}")


def _print_summary(battles: List[Battle]) -> None:
    """Print a quick sanity-check table after loading."""
    print(
        f"\n{'ID':>4}  {'Outcome':>8}  {'Blue':>12}  {'Red':>12}  "
        f"{'Blue heroes':<30}  {'Red heroes':<30}"
    )
    print("-" * 105)
    for b in battles:
        blue_h = ", ".join(h.name for h in b.blue.heroes) or "—"
        red_h = ", ".join(h.name for h in b.red.heroes) or "—"
        result = "WIN" if b.outcome == 1 else "LOSE"
        print(
            f"{b.battle_id:>4}  {result:>8}  {b.blue.power_change:>12,.0f}  "
            f"{b.red.power_change:>12,.0f}  {blue_h:<30}  {red_h:<30}"
        )
    wins = sum(b.outcome for b in battles)
    print("-" * 105)
    print(f"       Wins: {wins}/{len(battles)}  ({100 * wins / len(battles):.1f}%)\n")


# ── Convenience: load from inline dict list ───────────────────────────────────


def load_battles_from_dicts(battle_dicts: list) -> List[Battle]:
    """
    Load directly from a Python list of dicts
    (useful when JSON data is already in memory).
    """
    battles = [parse_battle(d) for d in battle_dicts]
    battles.sort(key=lambda b: b.battle_id)
    print(f"Loaded {len(battles)} battles.")
    _print_summary(battles)
    return battles


# ── Validation ────────────────────────────────────────────────────────────────


def validate_battles(battles: List[Battle]) -> None:
    """
    Basic sanity checks on loaded data.
    Prints warnings for suspicious entries.
    """
    issues = []
    for b in battles:
        for side_name, side in [("blue", b.blue), ("red", b.red)]:
            # check N matches composition
            comp_total = (
                side.composition.infantry
                + side.composition.spearman
                + side.composition.archer
            )
            if comp_total > 0 and abs(comp_total - side.N) / side.N > 0.05:
                issues.append(
                    f"Battle {b.battle_id} [{side_name}]: "
                    f"composition sum {comp_total:,.0f} vs N {side.N:,.0f} "
                    f"(>{5:.0f}% diff)"
                )
            # check bonuses are positive
            for t in ["inf", "spr", "arc"]:
                for stat in ["atk", "def", "lth", "hp"]:
                    val = getattr(side.bonuses, f"{t}_{stat}")
                    if val <= 0:
                        issues.append(
                            f"Battle {b.battle_id} [{side_name}]: "
                            f"{t}_{stat} = {val} (non-positive)"
                        )
            # check heroes present
            if not side.heroes:
                issues.append(f"Battle {b.battle_id} [{side_name}]: no heroes found")

    if issues:
        print(f"\n⚠️  {len(issues)} validation issue(s):")
        for issue in issues:
            print(f"   • {issue}")
    else:
        print("✅ All battles passed validation.")


# ── Usage ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Option A: load from a single file with list of battles
    # battles = load_battles_from_json("battles.json")

    # Option B: load from a directory of json files
    # battles = load_battles_from_json("battles/")

    # Option C: load from dicts already in memory
    # battles = load_battles_from_dicts([battle_1_dict, battle_2_dict, ...])

    # After loading:
    # validate_battles(battles)
    # params, nll, hero_index = fit_model(battles, n_restarts=10)
    # summarize_params(params, hero_index)
    # evaluate_model(battles, params, hero_index)
    pass
