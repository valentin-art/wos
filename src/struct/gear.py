import pandas as pd

# Ресурсы апгрейда снаряжения.
RESOURCE_KEYS = ["Alloy", "Polish", "Plans", "Amber"]


class Gear:
    """Одно снаряжение (предмет): лестница апгрейдов по tier.

    Хранит таблицу кумулятивных апгрейдов от текущего tier, посчитанную под
    конкретный бюджет ресурсов в :meth:`compute_upgrades`.
    """

    def __init__(self, name: str, current_tier: str, df: pd.DataFrame):
        self.name = name
        self.current_tier = current_tier  # текущее состояние снаряжения
        self.df = df.copy()
        self.upgrade_table: pd.DataFrame | None = None

    def compute_upgrades(self, resources: dict) -> pd.DataFrame:
        """Строит таблицу кумулятивных апгрейдов, начиная с ТЕКУЩЕГО tier.

        - Отсечение снизу: апгрейды ниже текущего состояния в перебор не попадают
          (текущий tier добавляется как базовый вариант с нулевой стоимостью и
          нулевым приростом — снаряжение может остаться без изменений).
        - Отсечение сверху: эффективный максимум для ЭТОГО снаряжения — самый
          высокий уровень, который оно может достичь при ПОЛНОМ объёме ресурсов
          (остальные снаряжения при этом не трогаются). Выше этого уровня апгрейд
          в принципе недостижим, поэтому такие уровни не строятся.

        Строки таблицы упорядочены по возрастанию стоимости (стоимость кумулятивна),
        что используется для отсечения веток в переборе.
        """
        table = []
        cumulative = {"Alloy": 0, "Polish": 0, "Plans": 0, "Amber": 0, "SvS": 0}
        started = False

        for _, row in self.df.iterrows():

            # базовый вариант "остаться на текущем уровне"
            if row["Tier"] == self.current_tier:
                started = True
                table.append({
                    "gear": self.name,
                    "tier": row["Tier"],
                    "Alloy": 0, "Polish": 0, "Plans": 0, "Amber": 0, "SvS": 0,
                })
                continue

            if not started:
                continue

            # накапливаем стоимость апгрейда
            for r in RESOURCE_KEYS:
                if pd.notna(row[r]):
                    cumulative[r] += row[r]
            cumulative["SvS"] += row["SvS score"]

            # отсечение сверху по индивидуальному максимуму снаряжения
            if any(cumulative[r] > resources.get(r, 0) for r in RESOURCE_KEYS):
                break

            table.append({
                "gear": self.name,
                "tier": row["Tier"],
                "Alloy": cumulative["Alloy"],
                "Polish": cumulative["Polish"],
                "Plans": cumulative["Plans"],
                "Amber": cumulative["Amber"],
                "SvS": cumulative["SvS"],
            })

        self.upgrade_table = pd.DataFrame(table)
        return self.upgrade_table
