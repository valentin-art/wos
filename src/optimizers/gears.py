from typing import List

import pandas as pd

from src.struct.gear import Gear, RESOURCE_KEYS

# Множитель целевой функции (итоговый SvS-счёт по всем снаряжениям).
SCORE_MULTIPLIER = 36


def upgrade_chief_gears(gears: List[Gear], resources: dict):
    """Оптимальное распределение ресурсов по апгрейдам снаряжения вождя.

    Перебор реализован как DFS с отсечением веток по бюджету (стоимости
    кумулятивны и аддитивны, поэтому невыполнимые ветки отсекаются без потери
    оптимума) и тай-брейком: при равной целевой функции предпочитается более
    прокачанное снаряжение в порядке ПРИОРИТЕТА = порядок в ``gears``.

    Опции каждого снаряжения пересчитываются здесь под ``resources``, поэтому
    результат самосогласован независимо от того, что было посчитано ранее.

    Returns:
        upgrade_table : pd.DataFrame  — выбранный оптимум (строка на снаряжение)
        cost          : dict          — потраченные ресурсы
        remaining     : dict          — остатки ресурсов
        score         : int|float     — целевая функция (SvS * SCORE_MULTIPLIER)
        all_combos    : pd.DataFrame   — все допустимые комбинации с целевой функцией
    """
    # Каждое снаряжение режется по своему индивидуальному эффективному максимуму
    # (полные ресурсы, остальные снаряжения без изменений).
    tables = [g.compute_upgrades(resources).to_dict("records") for g in gears]
    gear_names = [g.name for g in gears]

    # Лучшее решение. Ключ выбора = (целевая функция, тай-брейк).
    # Тай-брейк: при равной целевой функции предпочитаем более прокачанное
    # снаряжение в порядке приоритета (порядок gears). Прирост SvS отдельного
    # снаряжения монотонен по уровню апгрейда, поэтому больший per-gear SvS = более
    # высокий tier; лексикографическое сравнение кортежа per-gear SvS реализует
    # предпочтение. Стартовый ключ (-1,) меньше любого реального (SvS >= 0).
    best = {"key": (-1,), "combo": None, "cost": None}

    # Полный список всех ДОПУСТИМЫХ комбинаций с целевой функцией. Множество
    # допустимых комбинаций и оптимум совпадают с полным перебором: отсекаются
    # лишь ветки, превышающие бюджет (у них нет валидного значения цели).
    all_combos = []

    # текущая накопленная стоимость и прирост вдоль ветки перебора
    acc = {"Alloy": 0, "Polish": 0, "Plans": 0, "Amber": 0, "SvS": 0}

    def dfs(i, chosen):
        # все снаряжения распределены — допустимая полная комбинация
        if i == len(tables):
            prio = tuple(row["SvS"] for row in chosen)
            all_combos.append({
                **{name: row["tier"] for name, row in zip(gear_names, chosen)},
                "Alloy": acc["Alloy"],
                "Polish": acc["Polish"],
                "Plans": acc["Plans"],
                "Amber": acc["Amber"],
                "SvS": acc["SvS"],
                "score": acc["SvS"] * SCORE_MULTIPLIER,
                "_prio": prio,
            })
            candidate = (acc["SvS"],) + prio
            if candidate > best["key"]:
                best["key"] = candidate
                best["combo"] = list(chosen)
                best["cost"] = {r: acc[r] for r in RESOURCE_KEYS}
            return

        for row in tables[i]:
            # отсечение ветки: частичная сумма уже превысила бюджет. Строки
            # отсортированы по росту стоимости -> следующие уровни тоже не влезут.
            if any(acc[r] + row[r] > resources.get(r, 0) for r in RESOURCE_KEYS):
                break

            for r in RESOURCE_KEYS:
                acc[r] += row[r]
            acc["SvS"] += row["SvS"]
            chosen.append(row)

            dfs(i + 1, chosen)

            chosen.pop()
            acc["SvS"] -= row["SvS"]
            for r in RESOURCE_KEYS:
                acc[r] -= row[r]

    dfs(0, [])

    remaining = {r: resources[r] - best["cost"][r] for r in RESOURCE_KEYS}

    # сортировка по убыванию цели, при равенстве — по приоритету снаряжения,
    # чтобы верхняя строка совпадала с выбранным оптимумом
    all_combos = (
        pd.DataFrame(all_combos)
        .sort_values(["score", "_prio"], ascending=False)
        .drop(columns="_prio")
        .reset_index(drop=True)
    )

    # таблица апгрейдов (лучшее решение): old -> new tier по каждому снаряжению
    best_row = all_combos.iloc[0]
    upgrade_table = pd.DataFrame({
        "gear": gear_names,
        "old_tier": [g.current_tier for g in gears],
        "new_tier": [best_row[name] for name in gear_names],
    })

    score = best["key"][0] * SCORE_MULTIPLIER
    return upgrade_table, best["cost"], remaining, score, all_combos
