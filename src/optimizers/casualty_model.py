"""
Casualty model — predicts what fraction of each side's troops are wounded.

Consistency with the win model
───────────────────────────────
The win model already fits δ, α, β, w (troop weights), κ and per-hero
β_off / β_def.  Those parameters define an offensive score (OFF) and a
defensive score (DEF) for every side.  The ratio

    pressure  =  OFF_opponent / DEF_self

is the natural "incoming damage" signal for a side, and it is exactly
the two terms whose difference drives the win-probability margin.

This model fixes all structural parameters from the win model and
estimates only two new scalars (intercept a, slope b) via OLS on

    logit(cas_rate)  =  a  +  b · log(pressure)

using battles where the side survived (non-censored: survivors > 0).

Data notes
──────────
- losses = 0 in every observed battle.
- wounded / (wounded + lightly_wounded) ≈ 0.35 (game constant).
- Losers are usually fully wiped out (cas_rate = 1.0, censored); these
  are excluded from the OLS fit but predicted at inference time.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np
from scipy.special import expit  # sigmoid

from src.features.army_strength import (
    compute_B_def,
    compute_B_off,
    compute_Q,
    hero_factor,
)
from src.optimizers.battle_model import n_params, neg_log_likelihood, unpack
from src.struct.battle import Battle, Side

# Game constant: share of total casualties that are "seriously wounded"
WOUNDED_SHARE = 0.35


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class CasualtyParams:
    intercept: float
    pressure_coef: float
    counter_pressure_coef: float = 0.0
    size_ratio_coef: float = 0.0
    opp_inf_coef: float = 0.0
    opp_spr_coef: float = 0.0
    wounded_share: float = WOUNDED_SHARE

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CasualtyParams":
        return cls(**d)


@dataclass
class CasualtyPrediction:
    cas_rate: float
    total_casualties: int
    wounded: int
    lightly_wounded: int
    survivors: int


# ── Core computation ──────────────────────────────────────────────────────────


def compute_pressure(
    side: Side,
    opponent: Side,
    params: np.ndarray,
    hero_index: Dict[str, int],
) -> float:
    """OFF_opponent / DEF_self — how hard `side` is being hit."""
    p = unpack(params, len(hero_index))

    # Opponent's offensive score
    B_off = compute_B_off(opponent.bonuses)
    Q_off = compute_Q(B_off, p["w"], p["alpha"])
    Q_off_scalar = np.dot(list(asdict(opponent.composition).values()), Q_off) / opponent.N
    H_off = hero_factor(opponent.heroes, hero_index, p["beta_off"])
    OFF = (opponent.N ** p["delta"]) * Q_off_scalar * H_off

    # This side's defensive score
    B_def = compute_B_def(side.bonuses)
    Q_def = compute_Q(B_def, p["w"], p["beta_s"])
    Q_def_scalar = np.dot(list(asdict(side.composition).values()), Q_def) / side.N
    H_def = hero_factor(side.heroes, hero_index, p["beta_def"])
    DEF = (side.N ** p["delta"]) * Q_def_scalar * H_def

    return OFF / max(DEF, 1e-12)


def compute_counter_pressure(
    side: Side,
    opponent: Side,
    params: np.ndarray,
    hero_index: Dict[str, int],
) -> float:
    """DEF_opponent / OFF_self — how hard the opponent resists `side`'s attack."""
    p = unpack(params, len(hero_index))

    # This side's offensive score
    B_off = compute_B_off(side.bonuses)
    Q_off = compute_Q(B_off, p["w"], p["alpha"])
    Q_off_scalar = np.dot(list(asdict(side.composition).values()), Q_off) / side.N
    H_off = hero_factor(side.heroes, hero_index, p["beta_off"])
    OFF = (side.N ** p["delta"]) * Q_off_scalar * H_off

    # Opponent's defensive score
    B_def = compute_B_def(opponent.bonuses)
    Q_def = compute_Q(B_def, p["w"], p["beta_s"])
    Q_def_scalar = np.dot(list(asdict(opponent.composition).values()), Q_def) / opponent.N
    H_def = hero_factor(opponent.heroes, hero_index, p["beta_def"])
    DEF = (opponent.N ** p["delta"]) * Q_def_scalar * H_def

    return OFF / max(DEF, 1e-12)


def opponent_type_shares(opponent: Side) -> tuple:
    """Return (inf_share, spr_share) of the opponent's army.

    Archer share is the omitted baseline. The coefficients on these features
    capture per-type lethality differences not explained by the bonus-weighted
    `pressure` term: e.g. a coefficient < 0 on infantry means infantry-heavy
    attackers cause fewer casualties than archer-heavy ones at the same pressure.
    """
    c = asdict(opponent.composition)
    return c["infantry"] / opponent.N, c["spearman"] / opponent.N


def compute_size_ratio(side: Side, opponent: Side) -> float:
    """N_opponent / N_self — numerical (head-count) disadvantage.

    `pressure` and `counter_pressure` are *per-capita* ratios (the strength
    terms are divided by N), so absolute army size cancels out of them. Yet a
    winner facing twice as many enemies still absorbs roughly twice the total
    incoming hits. This term re-introduces that head-count effect.
    """
    return opponent.N / max(side.N, 1e-12)


# ── Fitting ───────────────────────────────────────────────────────────────────


def fit_casualty_model(
    battles: List[Battle],
    params: np.ndarray,
    hero_index: Dict[str, int],
    verbose: bool = True,
) -> CasualtyParams:
    """
    OLS on non-censored (survivors > 0) observations.
    logit(cas_rate) = a + b·log(pressure) + c·log(counter_pressure) + d·log(size_ratio)
                        + e·opp_inf_share + f·opp_spr_share
    """
    X_pressure, X_counter, X_size, X_inf, X_spr, y_vals = [], [], [], [], [], []

    for b in battles:
        for side, opp in [(b.blue, b.red), (b.red, b.blue)]:
            oc = side.outcome_stats
            if oc is None:
                continue
            total_cas = (oc.losses or 0) + (oc.wounded or 0) + (oc.lightly_wounded or 0)
            if total_cas == 0 or side.N == 0:
                continue
            cas_rate = total_cas / side.N
            if cas_rate >= 1.0:
                continue  # fully wiped out — censored, skip

            pressure = compute_pressure(side, opp, params, hero_index)
            counter = compute_counter_pressure(side, opp, params, hero_index)
            size_ratio = compute_size_ratio(side, opp)
            opp_inf, opp_spr = opponent_type_shares(opp)
            if pressure <= 0 or counter <= 0 or size_ratio <= 0:
                continue

            X_pressure.append(np.log(pressure))
            X_counter.append(np.log(counter))
            X_size.append(np.log(size_ratio))
            X_inf.append(opp_inf)
            X_spr.append(opp_spr)
            y_vals.append(np.log(cas_rate / (1.0 - cas_rate)))  # logit

    X_p = np.array(X_pressure)
    X_c = np.array(X_counter)
    X_s = np.array(X_size)
    X_i = np.array(X_inf)
    X_sp = np.array(X_spr)
    y = np.array(y_vals)
    n = len(y)

    # OLS
    X_mat = np.column_stack([np.ones(n), X_p, X_c, X_s, X_i, X_sp])
    coeffs, *_ = np.linalg.lstsq(X_mat, y, rcond=None)
    intercept, slope_p, slope_c, slope_s, slope_i, slope_sp = [float(v) for v in coeffs]

    if verbose:
        y_hat = X_mat @ coeffs
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        print(f"Casualty model fitted on {n} non-censored observations")
        print(f"  intercept (a)             : {intercept:.4f}")
        print(f"  pressure coef (b)         : {slope_p:.4f}")
        print(f"  counter_pressure coef (c) : {slope_c:.4f}")
        print(f"  size_ratio coef (d)       : {slope_s:.4f}")
        print(f"  opp_inf_share coef (e)    : {slope_i:.4f}  (vs archers baseline)")
        print(f"  opp_spr_share coef (f)    : {slope_sp:.4f}  (vs archers baseline)")
        print(f"  R²                        : {r2:.4f}")

    return CasualtyParams(
        intercept=intercept,
        pressure_coef=slope_p,
        counter_pressure_coef=slope_c,
        size_ratio_coef=slope_s,
        opp_inf_coef=slope_i,
        opp_spr_coef=slope_sp,
    )


# ── Prediction ────────────────────────────────────────────────────────────────


def predict_casualties(
    side: Side,
    opponent: Side,
    params: np.ndarray,
    hero_index: Dict[str, int],
    cas_params: CasualtyParams,
    won: bool = True,
) -> CasualtyPrediction:
    """Predict casualties for `side` when facing `opponent`.

    Losing sides are fully wiped out (cas_rate=1.0); the wounded/lightly-wounded
    split is applied using WOUNDED_SHARE directly from the army size.
    Winning sides use the regression model (pressure + counter_pressure).
    """
    if not won:
        total_cas = round(side.N)
        wounded = round(total_cas * cas_params.wounded_share)
        lightly_wounded = total_cas - wounded
        return CasualtyPrediction(
            cas_rate=1.0,
            total_casualties=total_cas,
            wounded=wounded,
            lightly_wounded=lightly_wounded,
            survivors=0,
        )

    pressure = compute_pressure(side, opponent, params, hero_index)
    counter = compute_counter_pressure(side, opponent, params, hero_index)
    size_ratio = compute_size_ratio(side, opponent)
    opp_inf, opp_spr = opponent_type_shares(opponent)
    logit_val = (
        cas_params.intercept
        + cas_params.pressure_coef * np.log(max(pressure, 1e-12))
        + cas_params.counter_pressure_coef * np.log(max(counter, 1e-12))
        + cas_params.size_ratio_coef * np.log(max(size_ratio, 1e-12))
        + cas_params.opp_inf_coef * opp_inf
        + cas_params.opp_spr_coef * opp_spr
    )
    cas_rate = float(np.clip(expit(logit_val), 0.0, 1.0))

    total_cas = round(side.N * cas_rate)
    wounded = round(total_cas * cas_params.wounded_share)
    lightly_wounded = total_cas - wounded
    survivors = max(round(side.N) - total_cas, 0)

    return CasualtyPrediction(
        cas_rate=cas_rate,
        total_casualties=total_cas,
        wounded=wounded,
        lightly_wounded=lightly_wounded,
        survivors=survivors,
    )


# ── Diagnostics ───────────────────────────────────────────────────────────────


def evaluate_casualty_model(
    battles: List[Battle],
    params: np.ndarray,
    hero_index: Dict[str, int],
    cas_params: CasualtyParams,
    verbose: bool = True,
) -> "pd.DataFrame":
    import pandas as pd

    rows = []
    for b in battles:
        for side_name, side, opp in [("blue", b.blue, b.red), ("red", b.red, b.blue)]:
            oc = side.outcome_stats
            if oc is None:
                continue
            total_cas = (oc.losses or 0) + (oc.wounded or 0) + (oc.lightly_wounded or 0)
            actual_rate = total_cas / side.N if side.N > 0 else float("nan")
            won = (side_name == "blue") == (b.outcome == 1)
            pred = predict_casualties(side, opp, params, hero_index, cas_params, won=won)
            rows.append(
                {
                    "battle_id": b.battle_id,
                    "side": side_name,
                    "N": int(side.N),
                    "actual_cas_rate": round(actual_rate, 4),
                    "predicted_cas_rate": round(pred.cas_rate, 4),
                    "error": round(pred.cas_rate - actual_rate, 4),
                    "censored": actual_rate >= 1.0,
                }
            )

    df = pd.DataFrame(rows)

    if verbose:
        non_cens = df[~df["censored"]]
        mae = non_cens["error"].abs().mean()
        print(f"\nCasualty model diagnostics (non-censored observations: {len(non_cens)})")
        print(f"  MAE (cas_rate) : {mae:.4f}")
        print(df.to_string(index=False))

    return df


# ── Joint calibration ─────────────────────────────────────────────────────────


def _build_casualty_design(
    battles: List[Battle],
    params: np.ndarray,
    hero_index: Dict[str, int],
) -> Tuple[np.ndarray, np.ndarray]:
    """Build the 6-column OLS design matrix for the current structural params."""
    rows, ys = [], []
    for b in battles:
        for side, opp in [(b.blue, b.red), (b.red, b.blue)]:
            oc = side.outcome_stats
            if oc is None:
                continue
            total_cas = (oc.losses or 0) + (oc.wounded or 0) + (oc.lightly_wounded or 0)
            if total_cas == 0 or side.N == 0:
                continue
            cas_rate = total_cas / side.N
            if cas_rate >= 1.0:
                continue
            try:
                pressure = compute_pressure(side, opp, params, hero_index)
                counter = compute_counter_pressure(side, opp, params, hero_index)
                size_ratio = compute_size_ratio(side, opp)
                opp_inf, opp_spr = opponent_type_shares(opp)
                if pressure <= 0 or counter <= 0 or size_ratio <= 0:
                    continue
                rows.append([1.0, np.log(pressure), np.log(counter),
                              np.log(size_ratio), opp_inf, opp_spr])
                ys.append(np.log(cas_rate / (1.0 - cas_rate)))
            except Exception:
                continue
    return np.array(rows), np.array(ys)


def fit_joint_model(
    battles: List[Battle],
    hero_index: Dict[str, int],
    initial_params: np.ndarray,
    lam: float = 0.7,
    n_restarts: int = 5,
    verbose: bool = True,
) -> Tuple[np.ndarray, CasualtyParams]:
    """
    Jointly optimize structural battle params for both win/loss and casualty accuracy.

    Objective (both terms normalized per observation):
        lam * NLL_win / n_battles  +  (1 - lam) * SSR_cas / n_cas_obs

    lam=1.0 → pure win model (equivalent to fit_model)
    lam=0.0 → pure casualty model (equivalent to fit_model_cas)
    lam=0.5 → equal weight on both signals

    The 6 casualty linear params (intercept, pressure, counter_pressure,
    size_ratio, opp_inf, opp_spr) are profiled out analytically at every
    optimizer step — only the 7+2H structural params are searched by L-BFGS-B.

    Parameters
    ----------
    initial_params : starting point; use the output of fit_model() so the
                     optimizer starts from a win-accurate solution.
    lam            : weight on win/loss NLL; (1-lam) goes to casualty SSR.
    """
    from scipy.optimize import minimize as _minimize

    n_battles = len(battles)
    np_ = n_params(len(hero_index))

    def _joint_loss(p: np.ndarray) -> float:
        nll = neg_log_likelihood(p, battles, hero_index)
        X_mat, y = _build_casualty_design(battles, p, hero_index)
        if len(y) < 7:
            return lam * nll / n_battles + 1e6
        beta, *_ = np.linalg.lstsq(X_mat, y, rcond=None)
        ssr = float(np.dot(y - X_mat @ beta, y - X_mat @ beta))
        return lam * nll / n_battles + (1.0 - lam) * ssr / len(y)

    best_params = initial_params.copy()
    best_loss = np.inf

    for restart in range(n_restarts):
        x0 = initial_params.copy() if restart == 0 else initial_params + np.random.randn(np_) * 0.1
        result = _minimize(
            _joint_loss, x0, method="L-BFGS-B",
            options={"maxiter": 100000, "ftol": 1e-14, "gtol": 1e-9},
        )
        if result.fun < best_loss:
            best_loss = result.fun
            best_params = result.x
            if verbose:
                print(f"Restart {restart+1:2d}: loss={result.fun:.6f}  converged={result.success}")

    # Recover cas_params analytically from the best structural params
    X_mat, y = _build_casualty_design(battles, best_params, hero_index)
    beta, *_ = np.linalg.lstsq(X_mat, y, rcond=None)
    cas_params_final = CasualtyParams(
        intercept=float(beta[0]),
        pressure_coef=float(beta[1]),
        counter_pressure_coef=float(beta[2]),
        size_ratio_coef=float(beta[3]),
        opp_inf_coef=float(beta[4]),
        opp_spr_coef=float(beta[5]),
    )

    if verbose:
        y_hat = X_mat @ beta
        r2 = 1.0 - np.sum((y - y_hat) ** 2) / np.sum((y - y.mean()) ** 2)
        nll_final = neg_log_likelihood(best_params, battles, hero_index)
        print(f"\nJoint model results ({len(y)} casualty obs, {n_battles} battles):")
        print(f"  Win NLL        : {nll_final:.4f}")
        print(f"  Casualty R²    : {r2:.4f}")
        print(f"  intercept      : {cas_params_final.intercept:.4f}")
        print(f"  pressure_coef  : {cas_params_final.pressure_coef:.4f}")
        print(f"  counter_coef   : {cas_params_final.counter_pressure_coef:.4f}")
        print(f"  size_ratio_coef: {cas_params_final.size_ratio_coef:.4f}")
        print(f"  opp_inf_coef   : {cas_params_final.opp_inf_coef:.4f}")
        print(f"  opp_spr_coef   : {cas_params_final.opp_spr_coef:.4f}")

    return best_params, cas_params_final


# ── Persistence ───────────────────────────────────────────────────────────────


def save_casualty_params(cas_params: CasualtyParams, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cas_params.to_dict(), f, indent=2)


def load_casualty_params(path: str) -> CasualtyParams:
    with open(path, "r", encoding="utf-8") as f:
        return CasualtyParams.from_dict(json.load(f))
