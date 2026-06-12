import numpy as np
import pandas as pd
from dataclasses import asdict
from src.struct.battle import Battle
from src.features.army_strength import (
    compute_B_off,
    compute_B_def,
    compute_Q,
    hero_factor,
)
from typing import Dict, List, Set, Tuple

from scipy.optimize import minimize
from scipy.stats import norm


NO_SKILL_HEROES: Set[str] = set()  # heroes with no battle skills → treated as no-hero


def build_hero_index(
    battles: List[Battle],
    no_skill_heroes: Set[str] = NO_SKILL_HEROES,
) -> Dict[str, int]:
    """Assign a unique index to each hero that has battle skills.

    Heroes in `no_skill_heroes` are excluded and treated as H=1 (no-hero
    baseline), so the optimizer never wastes a parameter on them.
    """
    _exclude = {n.lower() for n in no_skill_heroes} | {"none", "none_infantry", ""}
    names: Set[str] = set()
    for b in battles:
        for h in b.blue.heroes + b.red.heroes:
            if h.name and h.name.lower() not in _exclude:
                names.add(h.name)
    return {name: idx for idx, name in enumerate(sorted(names))}


# ── Parameter layout ──────────────────────────────────────────────────────────
#
# params vector:
#   [0]        log_delta   → δ  = exp(...)   army scale exponent
#   [1]        log_alpha   → α  = exp(...)   B_off power
#   [2]        log_beta_s  → β  = exp(...)   B_def power  (β_s to avoid clash)
#   [3:6]      logit_w     → w via softmax   troop type weights
#   [6]        log_kappa   → κ  = exp(...)   margin scale
#   [7:7+H]    beta_off    → offensive hero bonuses  (unconstrained)
#   [7+H:7+2H] beta_def    → defensive hero bonuses  (unconstrained)
#
# Total: 7 + 2*H  parameters


def n_params(n_heroes: int) -> int:
    return 7 + 2 * n_heroes


def unpack(params: np.ndarray, n_heroes: int) -> dict:
    delta = np.exp(params[0])
    alpha = np.exp(params[1])
    beta_s = np.exp(params[2])
    w_logits = params[3:6]
    w = np.exp(w_logits) / np.exp(w_logits).sum()
    kappa = np.exp(params[6])
    beta_off = np.exp(params[7 : 7 + n_heroes]) / (np.exp(params[7 : 7 + n_heroes]) + 1)
    beta_def = np.exp(params[7 + n_heroes : 7 + 2 * n_heroes]) / (
        np.exp(params[7 + n_heroes : 7 + 2 * n_heroes]) + 1
    )
    return dict(
        delta=delta,
        alpha=alpha,
        beta_s=beta_s,
        w=w,
        kappa=kappa,
        beta_off=beta_off,
        beta_def=beta_def,
    )


# ── Core model ────────────────────────────────────────────────────────────────


def compute_margin(
    battle: Battle, params: np.ndarray, hero_index: Dict[str, int]
) -> float:
    """
    Margin = OFF_blue/DEF_red - OFF_red/DEF_blue
    Positive → blue wins
    """
    n_heroes = len(hero_index)
    p = unpack(params, n_heroes)

    results = {}
    for side_name, side in [("blue", battle.blue), ("red", battle.red)]:
        B_off = compute_B_off(side.bonuses)
        B_def = compute_B_def(side.bonuses)

        Q_off = compute_Q(B_off, p["w"], p["alpha"])
        Q_off = np.dot(list(asdict(side.composition).values()), Q_off) / side.N

        Q_def = compute_Q(B_def, p["w"], p["beta_s"])
        Q_def = np.dot(list(asdict(side.composition).values()), Q_def) / side.N

        H_off = hero_factor(side.heroes, hero_index, p["beta_off"])
        H_def = hero_factor(side.heroes, hero_index, p["beta_def"])

        N_sc = side.N ** p["delta"]

        results[side_name] = {
            "OFF": N_sc * Q_off * H_off,
            "DEF": N_sc * Q_def * H_def,
        }

    b, r = results["blue"], results["red"]
    margin = b["OFF"] / r["DEF"] - r["OFF"] / b["DEF"]
    return p["kappa"] * margin


def predict_p_win(
    battle: Battle, params: np.ndarray, hero_index: Dict[str, int]
) -> float:
    """P(blue wins) = Φ(margin)"""
    m = compute_margin(battle, params, hero_index)
    return float(norm.cdf(m))


# ── Estimation ────────────────────────────────────────────────────────────────


def neg_log_likelihood(
    params: np.ndarray, battles: List[Battle], hero_index: Dict[str, int]
) -> float:
    eps = 1e-9
    total = 0.0
    for b in battles:
        try:
            p = predict_p_win(b, params, hero_index)
            p = np.clip(p, eps, 1 - eps)
            total += b.outcome * np.log(p) + (1 - b.outcome) * np.log(1 - p)
        except Exception:
            total += np.log(eps)
    return -total


def fit_model(
    battles: List[Battle],
    n_restarts: int = 10,
    verbose: bool = True,
    no_skill_heroes: Set[str] = NO_SKILL_HEROES,
) -> Tuple[np.ndarray, float, Dict[str, int]]:

    hero_index = build_hero_index(battles, no_skill_heroes=no_skill_heroes)
    n_h = len(hero_index)
    np_ = n_params(n_h)

    if verbose:
        print(f"Heroes: {sorted(hero_index.keys())}")
        print(f"Parameters: {np_}  |  Battles: {len(battles)}\n")

    best_params: np.ndarray = np.zeros(np_)
    best_nll = np.inf

    for restart in range(n_restarts):
        x0 = np.zeros(np_) if restart == 0 else np.random.randn(np_) * 0.2

        result = minimize(
            neg_log_likelihood,
            x0,
            args=(battles, hero_index),
            method="L-BFGS-B",
            options={"maxiter": 5000, "ftol": 1e-14, "gtol": 1e-9},
        )

        if result.fun < best_nll:
            best_nll = result.fun
            best_params = result.x
            if verbose:
                print(
                    f"Restart {restart + 1:2d}: NLL = {result.fun:.4f}  "
                    f"converged={result.success}"
                )

    return best_params, best_nll, hero_index


# ── Diagnostics ───────────────────────────────────────────────────────────────


def evaluate_model(
    battles: List[Battle],
    params: np.ndarray,
    hero_index: Dict[str, int],
    verbose: bool = True,
) -> pd.DataFrame:

    rows = []
    for b in battles:
        p = predict_p_win(b, params, hero_index)
        m = compute_margin(b, params, hero_index)
        rows.append(
            {
                "battle_id": b.battle_id,
                "outcome": b.outcome,
                "p_win": round(p, 3),
                "margin": round(m, 4),
                "correct": int((p >= 0.5) == b.outcome),
            }
        )

    df = pd.DataFrame(rows)

    if verbose:
        acc = df["correct"].mean()
        nll = neg_log_likelihood(params, battles, hero_index) / len(battles)
        brier = ((df.p_win - df.outcome) ** 2).mean()
        print(f"\nAccuracy    : {acc:.3f}")
        print(f"Mean NLL    : {nll:.4f}")
        print(f"Brier score : {brier:.4f}\n")
        print(df.to_string(index=False))

    return df


# ── Casualty-rate model (alternative to fit_model) ────────────────────────────
#
# Jointly estimates all structural parameters plus two OLS scalars using
# cas_rate as the dependent variable instead of binary win/lose.
#
# params vector:
#   [0]        log_delta
#   [1]        log_alpha
#   [2]        log_beta_s
#   [3:6]      logit_w
#   [6]        a  (OLS intercept, unconstrained)
#   [7]        log_b  → b = exp(...) > 0
#   [8:8+H]    raw beta_off  → sigmoid
#   [8+H:8+2H] raw beta_def  → sigmoid
#
# Total: 8 + 2*H


def n_params_cas(n_heroes: int) -> int:
    return 8 + 2 * n_heroes


def unpack_cas(params: np.ndarray, n_heroes: int) -> dict:
    delta = np.exp(params[0])
    alpha = np.exp(params[1])
    beta_s = np.exp(params[2])
    w_logits = params[3:6]
    w = np.exp(w_logits) / np.exp(w_logits).sum()
    a = float(params[6])
    b = float(np.exp(params[7]))
    raw_off = params[8 : 8 + n_heroes]
    raw_def = params[8 + n_heroes : 8 + 2 * n_heroes]
    beta_off = np.exp(raw_off) / (np.exp(raw_off) + 1)
    beta_def = np.exp(raw_def) / (np.exp(raw_def) + 1)
    return dict(
        delta=delta, alpha=alpha, beta_s=beta_s, w=w,
        a=a, b=b, beta_off=beta_off, beta_def=beta_def,
    )


def _pressure_from_dict(side, opponent, p: dict, hero_index: Dict[str, int]) -> float:
    """OFF_opponent / DEF_self from an unpacked params dict."""
    from dataclasses import asdict as _asdict

    B_off = compute_B_off(opponent.bonuses)
    Q_off = compute_Q(B_off, p["w"], p["alpha"])
    Q_off_sc = np.dot(list(_asdict(opponent.composition).values()), Q_off) / opponent.N
    H_off = hero_factor(opponent.heroes, hero_index, p["beta_off"])
    OFF = (opponent.N ** p["delta"]) * Q_off_sc * H_off

    B_def = compute_B_def(side.bonuses)
    Q_def = compute_Q(B_def, p["w"], p["beta_s"])
    Q_def_sc = np.dot(list(_asdict(side.composition).values()), Q_def) / side.N
    H_def = hero_factor(side.heroes, hero_index, p["beta_def"])
    DEF = (side.N ** p["delta"]) * Q_def_sc * H_def

    return OFF / max(DEF, 1e-12)


def _collect_cas_obs(battles: List, hero_index: Dict[str, int]) -> list:
    """Return (side, opponent, logit_cas_rate) for non-censored observations."""
    obs = []
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
            obs.append((side, opp, float(np.log(cas_rate / (1.0 - cas_rate)))))
    return obs


def ols_loss_cas(
    params: np.ndarray,
    obs: list,
    hero_index: Dict[str, int],
) -> float:
    """Sum of squared residuals on logit(cas_rate)."""
    p = unpack_cas(params, len(hero_index))
    a, b = p["a"], p["b"]
    ssr = 0.0
    for side, opp, logit_y in obs:
        try:
            pressure = _pressure_from_dict(side, opp, p, hero_index)
            logit_hat = a + b * np.log(max(pressure, 1e-12))
            ssr += (logit_y - logit_hat) ** 2
        except Exception:
            ssr += 1e6
    return ssr


def fit_model_cas(
    battles: List[Battle], n_restarts: int = 10, verbose: bool = True
) -> Tuple[np.ndarray, float, Dict[str, int]]:
    """
    Alternative to fit_model: estimates structural parameters by minimising
    OLS loss on logit(cas_rate) rather than NLL of binary win/lose outcomes.
    """
    hero_index = build_hero_index(battles)
    n_h = len(hero_index)
    np_ = n_params_cas(n_h)

    obs = _collect_cas_obs(battles, hero_index)

    if verbose:
        print(f"Heroes: {sorted(hero_index.keys())}")
        print(f"Parameters: {np_}  |  Observations (non-censored): {len(obs)}\n")

    best_params: np.ndarray = np.zeros(np_)
    best_ssr = np.inf

    for restart in range(n_restarts):
        x0 = np.zeros(np_) if restart == 0 else np.random.randn(np_) * 0.2

        result = minimize(
            ols_loss_cas,
            x0,
            args=(obs, hero_index),
            method="L-BFGS-B",
            options={"maxiter": 5000, "ftol": 1e-14, "gtol": 1e-9},
        )

        if result.fun < best_ssr:
            best_ssr = result.fun
            best_params = result.x
            if verbose:
                print(
                    f"Restart {restart + 1:2d}: SSR = {result.fun:.4f}  "
                    f"converged={result.success}"
                )

    return best_params, best_ssr, hero_index


def summarize_params_cas(params: np.ndarray, hero_index: Dict[str, int]) -> pd.DataFrame:
    n_h = len(hero_index)
    p = unpack_cas(params, n_h)
    idx_to_name = {v: k for k, v in hero_index.items()}

    print("=== Structural parameters (casualty model) ===")
    print(f"  delta (army scale)    : {p['delta']:.4f}")
    print(f"  alpha (B_off power)   : {p['alpha']:.4f}")
    print(f"  beta  (B_def power)   : {p['beta_s']:.4f}")
    print(f"  w_inf / w_spr / w_arc : {p['w'][0]:.3f} / {p['w'][1]:.3f} / {p['w'][2]:.3f}")
    print(f"  a (OLS intercept)     : {p['a']:.4f}")
    print(f"  b (log-pressure coef) : {p['b']:.4f}")

    rows = [
        {"hero": idx_to_name[i], "beta_off": round(p["beta_off"][i], 4), "beta_def": round(p["beta_def"][i], 4)}
        for i in range(n_h)
    ]
    df = pd.DataFrame(rows).sort_values("hero")
    print("\n=== Hero coefficients ===")
    print(df.to_string(index=False))
    return df


def evaluate_model_cas(
    battles: List[Battle],
    params: np.ndarray,
    hero_index: Dict[str, int],
    verbose: bool = True,
) -> pd.DataFrame:
    """Predicted vs actual cas_rate for the jointly-estimated casualty model."""
    from scipy.special import expit

    p = unpack_cas(params, len(hero_index))
    a, b = p["a"], p["b"]

    rows = []
    for battle in battles:
        for side_name, side, opp in [("Blue", battle.blue, battle.red), ("Red", battle.red, battle.blue)]:
            oc = side.outcome_stats
            if oc is None or side.N == 0:
                continue
            total_cas = (oc.losses or 0) + (oc.wounded or 0) + (oc.lightly_wounded or 0)
            actual_rate = total_cas / side.N
            censored = actual_rate >= 1.0

            pressure = _pressure_from_dict(side, opp, p, hero_index)
            pred_rate = float(expit(a + b * np.log(max(pressure, 1e-12))))

            rows.append({
                "battle_id": battle.battle_id,
                "side": side_name,
                "N": int(side.N),
                "actual": round(actual_rate, 4),
                "predicted": round(pred_rate, 4),
                "error": round(pred_rate - actual_rate, 4),
                "censored": censored,
            })

    df = pd.DataFrame(rows)

    if verbose:
        nc = df[~df["censored"]]
        mae  = nc["error"].abs().mean()
        rmse = (nc["error"] ** 2).mean() ** 0.5
        r2   = 1.0 - nc["error"].var() / nc["actual"].var() if nc["actual"].var() > 0 else float("nan")
        print(f"Non-censored observations: {len(nc)}")
        print(f"  MAE  (cas_rate) : {mae:.4f}")
        print(f"  RMSE (cas_rate) : {rmse:.4f}")
        print(f"  R²   (cas_rate) : {r2:.4f}")
        print()
        print(df.to_string(index=False))

    return df


def summarize_params(params: np.ndarray, hero_index: Dict[str, int]) -> pd.DataFrame:

    n_h = len(hero_index)
    p = unpack(params, n_h)
    idx_to_name = {v: k for k, v in hero_index.items()}

    print("=== Structural parameters ===")
    print(f"  delta (army scale)   : {p['delta']:.4f}")
    print(f"  alpha (B_off power)  : {p['alpha']:.4f}")
    print(f"  beta  (B_def power)  : {p['beta_s']:.4f}")
    print(
        f"  w_inf / w_spr / w_arc: {p['w'][0]:.3f} / {p['w'][1]:.3f} / {p['w'][2]:.3f}"
    )
    print(f"  kappa (margin scale) : {p['kappa']:.4f}")

    rows = []
    for idx in range(n_h):
        rows.append(
            {
                "hero": idx_to_name[idx],
                "beta_off": round(p["beta_off"][idx], 4),
                "beta_def": round(p["beta_def"][idx], 4),
            }
        )

    df = pd.DataFrame(rows).sort_values("hero")
    print("\n=== Hero coefficients ===")
    print(df.to_string(index=False))
    return df
