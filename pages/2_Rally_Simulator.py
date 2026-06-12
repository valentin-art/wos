import os
import sys
import json
import numpy as np
import streamlit as st
import boto3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.optimizers.battle_model import compute_margin, predict_p_win
from src.optimizers.casualty_model import load_casualty_params, predict_casualties
from src.struct.battle import ArmyBonuses, Battle, Hero, Side, TroopComposition

# ── Constants ────────────────────────────────────────────────────────────────

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
DEFAULT_BONUS_PCT = 1000


# ── R2 sync ──────────────────────────────────────────────────────────────────


def _sync_from_r2() -> None:
    r2 = st.secrets["r2"]
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{r2['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=r2["access_key_id"],
        aws_secret_access_key=r2["secret_access_key"],
        region_name="auto",
    )
    bucket = r2["bucket"]
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            local_path = os.path.join(base, key)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket, key, local_path)


# ── Model loading ─────────────────────────────────────────────────────────────


@st.cache_resource(show_spinner="Loading models…")
def load_model():
    try:
        has_r2 = "r2" in st.secrets
    except Exception:
        has_r2 = False
    if has_r2:
        _sync_from_r2()

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    params = np.load(os.path.join(base, "settings/battle_params.npy"))
    with open(os.path.join(base, "settings/battle_heroes.json"), "r", encoding="utf-8") as f:
        hero_index = json.load(f)
    cas_params = load_casualty_params(os.path.join(base, "settings/casualty_params.json"))
    with open(os.path.join(base, "settings/hero_roles.json"), "r", encoding="utf-8") as f:
        hero_roles = json.load(f)

    return params, hero_index, cas_params, hero_roles


# ── Side helpers ──────────────────────────────────────────────────────────────


def build_side(inf: float, lanc: float, mark: float, bonuses_pct: dict,
               hero_inf: str, hero_lanc: str, hero_mark: str) -> Side:
    b = {k: v / 100.0 for k, v in bonuses_pct.items()}
    heroes = [
        Hero(name=name, level=80, stars=5)
        for name in [hero_inf, hero_lanc, hero_mark]
        if name and name.lower() != "none"
    ]
    N = max(inf + lanc + mark, 1.0)
    return Side(
        N=N,
        power_change=0.0,
        composition=TroopComposition(infantry=inf, spearman=lanc, archer=mark),
        bonuses=ArmyBonuses(
            inf_atk=b["inf_atk"], inf_def=b["inf_def"],
            inf_lth=b["inf_lth"], inf_hp=b["inf_hp"],
            spr_atk=b["spr_atk"], spr_def=b["spr_def"],
            spr_lth=b["spr_lth"], spr_hp=b["spr_hp"],
            arc_atk=b["arc_atk"], arc_def=b["arc_def"],
            arc_lth=b["arc_lth"], arc_hp=b["arc_hp"],
        ),
        heroes=heroes,
    )


def scale_side(side: Side, new_N: float) -> Side:
    """Return side with troops scaled proportionally to new_N."""
    new_N = max(new_N, 1.0)
    ratio = new_N / max(side.N, 1.0)
    c = side.composition
    return Side(
        N=new_N,
        power_change=0.0,
        composition=TroopComposition(
            infantry=c.infantry * ratio,
            spearman=c.spearman * ratio,
            archer=c.archer * ratio,
        ),
        bonuses=side.bonuses,
        heroes=side.heroes,
    )


# ── Shared bonus input block ─────────────────────────────────────────────────


def bonus_inputs(key_prefix: str) -> dict:
    bonus_vals = {}
    with st.expander("Battle bonuses (% bonus, e.g. 1000 = ×10)", expanded=False):
        for troop_label, row in zip(
            ["Infantry", "Lancers", "Marksman"],
            [BONUS_FIELDS[:4], BONUS_FIELDS[4:8], BONUS_FIELDS[8:]],
        ):
            st.markdown(f"*{troop_label}*")
            bcols = st.columns(4)
            for col, (key, display) in zip(bcols, row):
                bonus_vals[key] = float(
                    col.number_input(
                        display.split()[-1],
                        min_value=0.0, max_value=5000.0,
                        value=float(DEFAULT_BONUS_PCT),
                        step=10.0, format="%.0f",
                        key=f"{key_prefix}_{key}",
                    )
                )
    return bonus_vals


# ── Red panel ─────────────────────────────────────────────────────────────────


def red_panel(heroes_by_role: dict) -> Side:
    st.markdown("**Heroes**")
    hcols = st.columns(3)
    hero_inf  = hcols[0].selectbox("Infantry hero",  heroes_by_role["infantry"],  key="red_h_inf")
    hero_lanc = hcols[1].selectbox("Lancer hero",    heroes_by_role["lancer"],    key="red_h_lanc")
    hero_mark = hcols[2].selectbox("Marksman hero",  heroes_by_role["marksman"],  key="red_h_mark")

    st.markdown("**Troops**")
    tcols = st.columns(3)
    inf  = float(tcols[0].number_input("Infantry",  min_value=0, value=100_000, step=10_000, key="red_inf"))
    lanc = float(tcols[1].number_input("Lancers",   min_value=0, value=100_000, step=10_000, key="red_lanc"))
    mark = float(tcols[2].number_input("Marksman",  min_value=0, value=100_000, step=10_000, key="red_mark"))
    st.caption(f"Total: {int(inf + lanc + mark):,}")

    bonuses = bonus_inputs("red")
    return build_side(inf, lanc, mark, bonuses, hero_inf, hero_lanc, hero_mark)


# ── Rally (blue) panel ────────────────────────────────────────────────────────


def rally_panel(i: int, heroes_by_role: dict) -> Side:
    st.markdown("**Heroes**")
    hcols = st.columns(3)
    hero_inf  = hcols[0].selectbox("Infantry hero",  heroes_by_role["infantry"],  key=f"b{i}_h_inf")
    hero_lanc = hcols[1].selectbox("Lancer hero",    heroes_by_role["lancer"],    key=f"b{i}_h_lanc")
    hero_mark = hcols[2].selectbox("Marksman hero",  heroes_by_role["marksman"],  key=f"b{i}_h_mark")

    st.markdown("**Troops**")
    tcols = st.columns(3)
    inf  = float(tcols[0].number_input("Infantry",  min_value=0, value=100_000, step=10_000, key=f"b{i}_inf"))
    lanc = float(tcols[1].number_input("Lancers",   min_value=0, value=100_000, step=10_000, key=f"b{i}_lanc"))
    mark = float(tcols[2].number_input("Marksman",  min_value=0, value=100_000, step=10_000, key=f"b{i}_mark"))
    st.caption(f"Total: {int(inf + lanc + mark):,}")

    bonuses = bonus_inputs(f"b{i}")
    return build_side(inf, lanc, mark, bonuses, hero_inf, hero_lanc, hero_mark)


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    st.set_page_config(page_title="WOS Rally Simulator", layout="wide")
    st.title("Whiteout Survival — Rally Simulator")
    st.caption(
        "Simulates a sequence of blue rallies against one red squad. "
        "Red's hospital casualties are subtracted from its army before each next rally."
    )

    params, hero_index, cas_params, hero_roles = load_model()

    heroes_by_role = {
        role: ["None"] + sorted(
            name for name, r in hero_roles.items()
            if r == role and name in hero_index
        )
        for role in ("infantry", "lancer", "marksman")
    }

    # ── Red side ──────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("🔴 Red side (defender)")
        red_side = red_panel(heroes_by_role)

    st.divider()

    # ── Rally rows ────────────────────────────────────────────────────────────
    st.subheader("🔵 Blue rallies")

    if "n_battles" not in st.session_state:
        st.session_state.n_battles = 1

    btn1, btn2, _ = st.columns([1.2, 1.6, 5])
    if btn1.button("➕ Add rally"):
        st.session_state.n_battles += 1
    if btn2.button("🗑 Delete last rally") and st.session_state.n_battles > 1:
        st.session_state.n_battles -= 1

    st.markdown("")

    red_N = float(red_side.N)

    for i in range(st.session_state.n_battles):
        with st.container(border=True):
            st.markdown(f"**Rally {i + 1}**")

            if red_N <= 0:
                st.warning("Red army fully depleted — no further battles.")
                break

            lcol, rcol = st.columns(2)

            with lcol:
                blue_side = rally_panel(i, heroes_by_role)

            red_current = scale_side(red_side, red_N)

            with rcol:
                st.caption(f"Red army entering this rally: **{int(red_N):,}**")
                try:
                    dummy = Battle(battle_id=0, outcome=1, blue=blue_side, red=red_current)
                    p_win = predict_p_win(dummy, params, hero_index)
                    margin = compute_margin(dummy, params, hero_index)
                    blue_wins = margin >= 0

                    cas_blue = predict_casualties(
                        blue_side, red_current, params, hero_index, cas_params, won=blue_wins,
                    )
                    cas_red = predict_casualties(
                        red_current, blue_side, params, hero_index, cas_params, won=not blue_wins,
                    )

                    if blue_wins:
                        st.success(f"🔵 Blue WINS  (p = {p_win * 100:.0f}%)")
                    else:
                        st.error(f"🔴 Red WINS  (p = {(1 - p_win) * 100:.0f}%)")

                    m1, m2 = st.columns(2)
                    m1.metric("Blue survivors", f"{cas_blue.survivors:,}")
                    m2.metric("Red survivors",  f"{cas_red.survivors:,}")

                    m3, m4 = st.columns(2)
                    m3.metric("Blue wounded (hosp)", f"{cas_blue.wounded:,}")
                    red_hosp = cas_red.wounded
                    red_N_next = max(red_N - red_hosp, 0.0)
                    m4.metric(
                        "Red wounded (hosp)", f"{red_hosp:,}",
                        delta=f"→ {int(red_N_next):,} remain",
                        delta_color="inverse",
                    )

                    red_N = red_N_next

                except Exception as exc:
                    st.error(f"Prediction failed: {exc}")


if __name__ == "__main__":
    main()
