import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.struct.gear import Gear, RESOURCE_KEYS
from src.struct.charm import Charm, CHARM_RESOURCE_KEYS
from src.optimizers.gears import upgrade_chief_gears
from src.optimizers.charms import upgrade_charms

# ── Constants ────────────────────────────────────────────────────────────────

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Equipment slots, in tie-break priority order (Jacket > Pants > ... > Watch).
GEAR_NAMES = ["Jacket", "Pants", "Ring", "Cane", "Helmet", "Watch"]
N_CHARMS = 3  # charms per equipment type

DEFAULT_GEAR_RESOURCES = {"Alloy": 214760, "Polish": 2587, "Plans": 605, "Amber": 0}
DEFAULT_CHARM_RESOURCES = {"Guide": 1122, "Design": 687}


# ── Data loading ─────────────────────────────────────────────────────────────


@st.cache_data
def load_gear_df() -> pd.DataFrame:
    return pd.read_excel(os.path.join(ROOT, "chief_gears.xlsx"))


@st.cache_data
def load_charm_df() -> pd.DataFrame:
    df = pd.read_excel(os.path.join(ROOT, "chief_charms.xlsx"))
    df["Level"] = pd.Categorical(df["Level"], ordered=True)
    return df


def resource_table(resources: dict, cost: dict, remaining: dict, keys: list) -> pd.DataFrame:
    """Build the used / rest resources table."""
    return pd.DataFrame({
        "resource": keys,
        "available": [resources[k] for k in keys],
        "used": [cost[k] for k in keys],
        "rest": [remaining[k] for k in keys],
    })


# ── Page ─────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Chief Upgrades", layout="wide")
st.title("Chief Gear & Charm Upgrade Optimizer")
st.caption(
    "Enter your resources and current levels, then calculate the upgrade plan "
    "that maximizes the SvS score within your budget."
)

gear_tab, charm_tab = st.tabs(["⚙️ Gears", "💎 Charms"])


# ── Gears tab ────────────────────────────────────────────────────────────────

with gear_tab:
    gear_df = load_gear_df()
    tiers = list(gear_df["Tier"])

    with st.form("gears_form"):
        st.subheader("Resources")
        res_cols = st.columns(len(RESOURCE_KEYS))
        gear_resources = {}
        for col, key in zip(res_cols, RESOURCE_KEYS):
            gear_resources[key] = col.number_input(
                key, min_value=0, value=int(DEFAULT_GEAR_RESOURCES.get(key, 0)),
                step=1000, key=f"gear_res_{key}",
            )

        st.subheader("Current tiers")
        current_tiers = {}
        tier_cols = st.columns(3)
        for i, name in enumerate(GEAR_NAMES):
            current_tiers[name] = tier_cols[i % 3].selectbox(
                name, tiers, index=0, key=f"gear_tier_{name}",
            )

        gear_submitted = st.form_submit_button("Calculate upgrades", type="primary")

    if gear_submitted:
        with st.spinner("Calculating..."):
            gears = [Gear(name, current_tiers[name], gear_df) for name in GEAR_NAMES]
            upgrade_table, cost, remaining, score, _ = upgrade_chief_gears(
                gears, gear_resources
            )

        st.metric("Total SvS score", f"{int(score):,}")

        st.subheader("Upgrades")
        st.dataframe(upgrade_table, hide_index=True, use_container_width=True)

        st.subheader("Used / rest resources")
        st.dataframe(
            resource_table(gear_resources, cost, remaining, RESOURCE_KEYS),
            hide_index=True, use_container_width=True,
        )


# ── Charms tab ───────────────────────────────────────────────────────────────

with charm_tab:
    charm_df = load_charm_df()
    levels = list(charm_df["Level"])
    default_level_index = levels.index(2.0) if 2.0 in levels else 0

    with st.form("charms_form"):
        st.subheader("Resources")
        res_cols = st.columns(len(CHARM_RESOURCE_KEYS))
        charm_resources = {}
        for col, key in zip(res_cols, CHARM_RESOURCE_KEYS):
            charm_resources[key] = col.number_input(
                key, min_value=0, value=int(DEFAULT_CHARM_RESOURCES.get(key, 0)),
                step=10, key=f"charm_res_{key}",
            )

        st.subheader("Current levels")
        st.caption(f"{N_CHARMS} independent charms per equipment type.")
        current_levels = {}
        for name in GEAR_NAMES:
            st.markdown(f"**{name}**")
            charm_cols = st.columns(N_CHARMS)
            current_levels[name] = [
                charm_cols[j].selectbox(
                    f"Charm {j + 1}", levels, index=default_level_index,
                    key=f"charm_lvl_{name}_{j}", label_visibility="collapsed",
                )
                for j in range(N_CHARMS)
            ]

        charm_submitted = st.form_submit_button("Calculate upgrades", type="primary")

    if charm_submitted:
        with st.spinner("Calculating..."):
            charms = [Charm(name, current_levels[name], charm_df) for name in GEAR_NAMES]
            upgrade_table, cost, remaining, score, _ = upgrade_charms(
                charms, charm_resources
            )

        st.metric("Total SvS score", f"{int(score):,}")

        st.subheader("Upgrades")
        st.dataframe(upgrade_table, hide_index=True, use_container_width=True)

        st.subheader("Used / rest resources")
        st.dataframe(
            resource_table(charm_resources, cost, remaining, CHARM_RESOURCE_KEYS),
            hide_index=True, use_container_width=True,
        )
