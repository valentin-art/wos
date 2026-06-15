import itertools
from collections import Counter

import pandas as pd

# Ресурсы апгрейда талисманов.
CHARM_RESOURCE_KEYS = ["Guide", "Design"]


class Charm:
    """Один ТИП снаряжения = независимые талисманы (по умолчанию 3).

    Талисманы одного типа эквивалентны по свойствам, но независимы и могут стоять
    на разных текущих уровнях. :meth:`compute_upgrades` строит варианты типа
    (агрегаты по его талисманам) под конкретный бюджет ресурсов.
    """

    def __init__(self, name: str, current_levels, df: pd.DataFrame):
        self.name = name
        # текущий уровень КАЖДОГО талисмана этого типа (список длиной n_charms).
        self.current_levels = list(current_levels)
        self.df = df.copy()
        self.charm_tables: dict | None = None   # таблица талисмана для каждого встречающегося уровня
        self.options: list | None = None        # варианты типа (агрегаты по его талисманам)

    def _single_table(self, current_level, resources: dict) -> list:
        """Кумулятивная таблица апгрейдов одного талисмана начиная с current_level.

        Отсечение снизу (уровни ниже текущего) и сверху (индивидуальный максимум
        при полном бюджете). SvS — прирост относительно текущего уровня.
        """
        rows = []
        cumulative = {"Guide": 0, "Design": 0, "SvS": 0}
        started = False
        for _, row in self.df.iterrows():
            if row["Level"] == current_level:
                started = True
                rows.append({"level": row["Level"], "Guide": 0, "Design": 0, "SvS": 0})
                continue
            if not started:
                continue
            for r in CHARM_RESOURCE_KEYS:
                if pd.notna(row[r]):
                    cumulative[r] += row[r]
            cumulative["SvS"] += row["SvS score"]
            if any(cumulative[r] > resources.get(r, 0) for r in CHARM_RESOURCE_KEYS):
                break
            rows.append({
                "level": row["Level"],
                "Guide": cumulative["Guide"],
                "Design": cumulative["Design"],
                "SvS": cumulative["SvS"],
            })
        return rows

    def compute_upgrades(self, resources: dict) -> list:
        """Строит варианты ТИПА снаряжения из его независимых талисманов.

        Стоимость апгрейда зависит от ТЕКУЩЕГО уровня талисмана, поэтому таблица
        строится отдельно для каждого встречающегося уровня.

        Симметрия: талисманы взаимозаменяемы (мультимножество вместо упорядоченных
        кортежей) ТОЛЬКО если у них одинаковый текущий уровень — тогда их «лестницы»
        совпадают. Поэтому талисманы типа группируются по текущему уровню:
          - внутри подгруппы одинакового уровня — combinations_with_replacement
            (убираем перестановки одинаковых талисманов);
          - между подгруппами разного уровня — декартово произведение (они независимы).
        """
        # таблица для каждого встречающегося текущего уровня
        self.charm_tables = {
            lvl: self._single_table(lvl, resources) for lvl in set(self.current_levels)
        }

        # варианты по каждой подгруппе одинакового текущего уровня
        per_subgroup = []
        for lvl, count in Counter(self.current_levels).items():
            rows = self.charm_tables[lvl]
            sub = []
            for ms in itertools.combinations_with_replacement(range(len(rows)), count):
                sub.append({
                    "pairs": [(lvl, rows[j]["level"]) for j in ms],  # (текущий, целевой)
                    "Guide": sum(rows[j]["Guide"] for j in ms),
                    "Design": sum(rows[j]["Design"] for j in ms),
                    "SvS": sum(rows[j]["SvS"] for j in ms),
                })
            per_subgroup.append(sub)

        # объединяем подгруппы внутри типа
        options = []
        for combo in itertools.product(*per_subgroup):
            guide = sum(c["Guide"] for c in combo)
            design = sum(c["Design"] for c in combo)
            svs = sum(c["SvS"] for c in combo)
            # отсечение сверху на уровне типа (все его талисманы при полном бюджете)
            if guide > resources.get("Guide", 0) or design > resources.get("Design", 0):
                continue
            pairs = [p for c in combo for p in c["pairs"]]
            options.append({
                "charm": self.name,
                "pairs": pairs,
                "levels": tuple(sorted(t for _, t in pairs)),  # целевые уровни (для вывода)
                "Guide": guide,
                "Design": design,
                "SvS": svs,
            })

        # по возрастанию стоимости -> используется для отсечения веток
        options.sort(key=lambda o: (o["Guide"], o["Design"]))
        self.options = options
        return options
