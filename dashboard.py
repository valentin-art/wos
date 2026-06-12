import os
import sys

import json
import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from src.io.io import load_battles_from_json
from src.optimizers.battle_model import (
    compute_margin,
    fit_model,
    predict_p_win,
    summarize_params,
    unpack,
)
from src.optimizers.casualty_model import (
    load_casualty_params,
    predict_casualties,
)
from src.struct.battle import ArmyBonuses, Battle, Hero, Side, TroopComposition

# ── Constants ────────────────────────────────────────────────────────────────

HERO_NAMES = ["None", "Alonso", "Flint", "Geronimo", "Greg", "Jessy", "Jina", "Logan", "Mia"]
BONUS_FIELDS = [
    ("inf_atk", "Infantry ATK"),
    ("inf_def", "Infantry DEF"),
    ("inf_lth", "Infantry Lethality"),
    ("inf_hp", "Infantry HP"),
    ("spr_atk", "Lancers ATK"),
    ("spr_def", "Lancers DEF"),
    ("spr_lth", "Lancers Lethality"),
    ("spr_hp", "Lancers HP"),
    ("arc_atk", "Marksman ATK"),
    ("arc_def", "Marksman DEF"),
    ("arc_lth", "Marksman Lethality"),
    ("arc_hp", "Marksman HP"),
]
DEFAULT_BONUS_PCT = 1000  # shown as %, stored as /100 internally


# ── Model fitting (cached) ───────────────────────────────────────────────────


@st.cache_resource(show_spinner="Loading models…")
def load_model():
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        battles = load_battles_from_json("./data")

    params = np.load("./settings/battle_params.npy")
    with open("./settings/battle_heroes.json", "r", encoding="utf-8") as f:
        hero_index = json.load(f)

    cas_params = load_casualty_params("./settings/casualty_params.json")

    return params, hero_index, battles, cas_params


# ── Helper: build Side from UI inputs ────────────────────────────────────────


def build_side(
    mode: str,
    inf: float,
    lanc: float,
    mark: float,
    total: float,
    inf_ratio: float,
    lanc_ratio: float,
    mark_ratio: float,
    bonuses_pct: dict,
    hero1: str,
    hero2: str,
    hero3: str,
) -> Side:
    if mode == "By count":
        n_inf, n_lanc, n_mark = inf, lanc, mark
        N = n_inf + n_lanc + n_mark
    else:
        ratio_sum = inf_ratio + lanc_ratio + mark_ratio
        if ratio_sum == 0:
            ratio_sum = 1.0
        n_inf = total * inf_ratio / ratio_sum
        n_lanc = total * lanc_ratio / ratio_sum
        n_mark = total * mark_ratio / ratio_sum
        N = total

    # bonuses_pct values are percentages, convert to multiplier
    b = {k: v / 100.0 for k, v in bonuses_pct.items()}

    heroes = []
    for name in [hero1, hero2, hero3]:
        if name and name.lower() != "none":
            heroes.append(Hero(name=name, level=80, stars=5))

    return Side(
        N=max(N, 1.0),
        power_change=0.0,
        composition=TroopComposition(infantry=n_inf, spearman=n_lanc, archer=n_mark),
        bonuses=ArmyBonuses(
            inf_atk=b["inf_atk"],
            inf_def=b["inf_def"],
            inf_lth=b["inf_lth"],
            inf_hp=b["inf_hp"],
            spr_atk=b["spr_atk"],
            spr_def=b["spr_def"],
            spr_lth=b["spr_lth"],
            spr_hp=b["spr_hp"],
            arc_atk=b["arc_atk"],
            arc_def=b["arc_def"],
            arc_lth=b["arc_lth"],
            arc_hp=b["arc_hp"],
        ),
        heroes=heroes,
    )


# ── Side input panel ─────────────────────────────────────────────────────────


def side_panel(label: str, color: str) -> tuple:
    st.markdown(f"### :{color}[{label} side]")

    # Heroes
    st.markdown("**Heroes**")
    hcols = st.columns(3)
    hero1 = hcols[0].selectbox("Hero 1", HERO_NAMES, key=f"{label}_h1")
    hero2 = hcols[1].selectbox("Hero 2", HERO_NAMES, key=f"{label}_h2")
    hero3 = hcols[2].selectbox("Hero 3", HERO_NAMES, key=f"{label}_h3")

    # Troops
    st.markdown("**Troops**")
    mode = st.radio(
        "Input mode",
        ["By count", "Ratio + total"],
        horizontal=True,
        key=f"{label}_mode",
    )

    inf = lanc = mark = 0.0
    total = inf_r = lanc_r = mark_r = 0.0

    if mode == "By count":
        tcols = st.columns(3)
        inf = float(tcols[0].number_input("Infantry", min_value=0, value=100_000, step=10_000, key=f"{label}_inf"))
        lanc = float(tcols[1].number_input("Lancers", min_value=0, value=100_000, step=10_000, key=f"{label}_lanc"))
        mark = float(tcols[2].number_input("Marksman", min_value=0, value=100_000, step=10_000, key=f"{label}_mark"))
        shown_total = int(inf + lanc + mark)
        st.caption(f"Total: {shown_total:,}")
    else:
        total = float(
            st.number_input("Total troops", min_value=1, value=300_000, step=10_000, key=f"{label}_total")
        )
        rcols = st.columns(3)
        inf_r = float(rcols[0].number_input("Infantry %", min_value=0.0, max_value=100.0, value=33.0, step=1.0, format="%.1f", key=f"{label}_infr"))
        lanc_r = float(rcols[1].number_input("Lancers %", min_value=0.0, max_value=100.0, value=33.0, step=1.0, format="%.1f", key=f"{label}_lancr"))
        mark_r = float(rcols[2].number_input("Marksman %", min_value=0.0, max_value=100.0, value=34.0, step=1.0, format="%.1f", key=f"{label}_markr"))
        rs = inf_r + lanc_r + mark_r
        if rs > 0:
            st.caption(
                f"Effective split — Infantry: {100*inf_r/rs:.1f}%  "
                f"Lancers: {100*lanc_r/rs:.1f}%  "
                f"Marksman: {100*mark_r/rs:.1f}%"
            )

    # Bonuses
    with st.expander("Battle bonuses (% bonus, e.g. 1000 = ×10)", expanded=False):
        bonus_vals = {}
        rows = [BONUS_FIELDS[:4], BONUS_FIELDS[4:8], BONUS_FIELDS[8:]]
        labels = ["Infantry", "Lancers", "Marksman"]
        for troop_label, row in zip(labels, rows):
            st.markdown(f"*{troop_label}*")
            bcols = st.columns(4)
            for col, (key, display) in zip(bcols, row):
                bonus_vals[key] = float(
                    col.number_input(
                        display.split()[-1],  # ATK / DEF / Lethality / HP
                        min_value=0.0,
                        max_value=5000.0,
                        value=float(DEFAULT_BONUS_PCT),
                        step=10.0,
                        format="%.0f",
                        key=f"{label}_{key}",
                    )
                )

    return mode, inf, lanc, mark, total, inf_r, lanc_r, mark_r, bonus_vals, hero1, hero2, hero3


# ── Model parameter display ───────────────────────────────────────────────────


def show_model_params(params: np.ndarray, hero_index: dict) -> None:
    p = unpack(params, len(hero_index))
    idx_to_name = {v: k for k, v in hero_index.items()}

    st.subheader("Structural parameters")
    struct_df = pd.DataFrame(
        [
            {
                "Parameter": "δ (army scale exponent)",
                "Value": f"{p['delta']:.4f}",
                "Interpretation": "N^δ army size scaling — larger δ = bigger armies hit harder",
            },
            {
                "Parameter": "α (offensive power)",
                "Value": f"{p['alpha']:.4f}",
                "Interpretation": "Exponent on B_off — amplifies attack bonuses",
            },
            {
                "Parameter": "β (defensive power)",
                "Value": f"{p['beta_s']:.4f}",
                "Interpretation": "Exponent on B_def — amplifies defence bonuses",
            },
            {
                "Parameter": "w_inf / w_lanc / w_mark",
                "Value": f"{p['w'][0]:.3f} / {p['w'][1]:.3f} / {p['w'][2]:.3f}",
                "Interpretation": "Troop-type weights in combat quality Q (softmax-normalised)",
            },
            {
                "Parameter": "κ (margin scale)",
                "Value": f"{p['kappa']:.4f}",
                "Interpretation": "Scales the raw margin before the Φ win-probability function",
            },
        ]
    )
    st.dataframe(struct_df, use_container_width=True, hide_index=True)

    st.subheader("Hero coefficients")
    hero_rows = []
    for idx in range(len(hero_index)):
        name = idx_to_name[idx]
        hero_rows.append(
            {
                "Hero": name,
                "β_off (offensive bonus)": round(p["beta_off"][idx], 4),
                "β_def (defensive bonus)": round(p["beta_def"][idx], 4),
            }
        )
    hero_df = pd.DataFrame(hero_rows).sort_values("Hero").reset_index(drop=True)

    st.markdown(
        "Each hero contributes additively to the army's offensive and defensive factors: "
        "H = 1 + Σ β_h.  A β_off close to 0.5 means a neutral-to-moderate offensive boost."
    )
    st.dataframe(hero_df, use_container_width=True, hide_index=True)


# ── Main app ─────────────────────────────────────────────────────────────────


def main():
    st.set_page_config(page_title="WOS Battle Dashboard", layout="wide")
    st.title("Whiteout Survival — Battle Outcome Dashboard")

    params, hero_index, battles, cas_params = load_model()

    tab_sim, tab_params = st.tabs(["Battle Simulator", "Model Parameters"])

    with tab_sim:
        col_blue, col_red = st.columns(2)

        with col_blue:
            (
                mode_b, inf_b, lanc_b, mark_b,
                total_b, inf_rb, lanc_rb, mark_rb,
                bonuses_b, h1_b, h2_b, h3_b,
            ) = side_panel("Blue", "blue")

        with col_red:
            (
                mode_r, inf_r, lanc_r, mark_r,
                total_r, inf_rr, lanc_rr, mark_rr,
                bonuses_r, h1_r, h2_r, h3_r,
            ) = side_panel("Red", "red")

        st.divider()

        blue_side = build_side(
            mode_b, inf_b, lanc_b, mark_b,
            total_b, inf_rb, lanc_rb, mark_rb,
            bonuses_b, h1_b, h2_b, h3_b,
        )
        red_side = build_side(
            mode_r, inf_r, lanc_r, mark_r,
            total_r, inf_rr, lanc_rr, mark_rr,
            bonuses_r, h1_r, h2_r, h3_r,
        )

        dummy_battle = Battle(
            battle_id=0,
            outcome=1,
            blue=blue_side,
            red=red_side,
        )

        try:
            p_win = predict_p_win(dummy_battle, params, hero_index)
            margin = compute_margin(dummy_battle, params, hero_index)
            cas_blue = predict_casualties(blue_side, red_side, params, hero_index, cas_params)
            cas_red = predict_casualties(red_side, blue_side, params, hero_index, cas_params)

            st.subheader("Predicted outcome")

            res_cols = st.columns([1, 1, 1])
            with res_cols[0]:
                st.metric("Blue win probability", f"{round(p_win * 100, 1)}%")
                st.progress(p_win)
            with res_cols[1]:
                st.metric("Red win probability", f"{round((1 - p_win) * 100, 1)}%")
                st.progress(1.0 - p_win)
            with res_cols[2]:
                sign = "+" if margin >= 0 else ""
                winner = ":blue[Blue]" if margin >= 0 else ":red[Red]"
                st.metric("Battle margin", f"{sign}{margin:.2f}")
                st.caption(f"Positive = Blue advantage. Predicted winner: {winner}")

            st.divider()
            st.subheader("Predicted casualties")

            cas_cols = st.columns(2)
            for col, side_label, cas, side_obj in [
                (cas_cols[0], "Blue", cas_blue, blue_side),
                (cas_cols[1], "Red", cas_red, red_side),
            ]:
                with col:
                    color = "blue" if side_label == "Blue" else "red"
                    st.markdown(f"**:{color}[{side_label}]**")
                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Casualty rate", f"{cas.cas_rate * 100:.1f}%")
                    mc2.metric("Survivors", f"{cas.survivors:,}")
                    mc3.metric("Total casualties", f"{cas.total_casualties:,}")
                    st.progress(min(cas.cas_rate, 1.0))
                    st.caption(
                        f"Wounded (hospital): {cas.wounded:,}  ·  "
                        f"Lightly wounded: {cas.lightly_wounded:,}"
                    )

            st.divider()
            st.subheader("Input summary")
            summary_data = []
            for side_label, side_obj in [("Blue", blue_side), ("Red", red_side)]:
                c = side_obj.composition
                n = side_obj.N
                summary_data.append(
                    {
                        "Side": side_label,
                        "Total troops": f"{int(n):,}",
                        "Infantry": f"{int(c.infantry):,} ({100*c.infantry/n:.0f}%)" if n > 0 else "0",
                        "Lancers": f"{int(c.spearman):,} ({100*c.spearman/n:.0f}%)" if n > 0 else "0",
                        "Marksman": f"{int(c.archer):,} ({100*c.archer/n:.0f}%)" if n > 0 else "0",
                        "Heroes": ", ".join(h.name for h in side_obj.heroes) or "None",
                    }
                )
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

        except Exception as exc:
            st.error(f"Prediction failed: {exc}")

    with tab_params:
        show_model_params(params, hero_index)
        st.divider()
        st.subheader("Casualty model")
        st.markdown(
            "Fitted independently on non-censored battles (survivors > 0).  "
            "Uses the same OFF/DEF scores as the win model — no new structural parameters."
        )
        cas_struct_df = pd.DataFrame(
            [
                {
                    "Parameter": "a (intercept)",
                    "Value": f"{cas_params.intercept:.4f}",
                    "Interpretation": "logit-scale baseline casualty rate when log(pressure) = 0",
                },
                {
                    "Parameter": "b (pressure coefficient)",
                    "Value": f"{cas_params.pressure_coef:.4f}",
                    "Interpretation": "logit(cas_rate) rises by b for each unit increase in log(pressure)",
                },
                {
                    "Parameter": "wounded share",
                    "Value": f"{cas_params.wounded_share:.2f}",
                    "Interpretation": "fixed game constant: 35% of casualties go to hospital, 65% lightly wounded",
                },
            ]
        )
        st.dataframe(cas_struct_df, use_container_width=True, hide_index=True)
        st.markdown(
            "**Model:** `logit(cas_rate) = a + b · log(pressure)`,  "
            "where `pressure = OFF_opponent / DEF_self`  ·  "
            "R² = 0.81 on 30 non-censored observations"
        )


if __name__ == "__main__":
    main()
