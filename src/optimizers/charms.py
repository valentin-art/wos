from typing import List

import pandas as pd

from src.struct.charm import Charm, CHARM_RESOURCE_KEYS

# Множитель целевой функции (итоговый SvS-счёт по всем талисманам).
SCORE_MULTIPLIER = 70


def upgrade_charms(charms: List[Charm], resources: dict):
    """Оптимальное распределение ресурсов по апгрейдам талисманов.

    Перебор реализован как DFS с отсечением веток по бюджету. Внутри типа симметрия
    сворачивается только среди ВЗАИМОЗАМЕНЯЕМЫХ талисманов (один тип + один текущий
    уровень) — это убирает лишь дубликаты-перестановки, не теряя игровых состояний.
    Тай-брейк: при равной целевой функции предпочитается более прокачанный тип в
    порядке ПРИОРИТЕТА = порядок в ``charms``.

    Опции каждого типа пересчитываются здесь под ``resources``, поэтому результат
    самосогласован независимо от того, что было посчитано ранее.

    Returns:
        upgrade_table : pd.DataFrame  — выбранный оптимум (строка на талисман)
        cost          : dict          — потраченные ресурсы
        remaining     : dict          — остатки ресурсов
        score         : int|float     — целевая функция (SvS * SCORE_MULTIPLIER)
        all_combos    : pd.DataFrame   — все допустимые комбинации с целевой функцией
    """
    # Опции пересчитываются под ТОТ ЖЕ бюджет, что и перебор (иначе рассинхрон ->
    # заниженный оптимум, недотрата ресурсов).
    for c in charms:
        c.compute_upgrades(resources)
    groups = [c.options for c in charms]
    names = [c.name for c in charms]

    # Лучшее решение. Ключ выбора = (целевая функция, тай-брейк).
    # Тай-брейк: при равной целевой функции предпочитаем более прокачанный тип в
    # порядке приоритета (порядок charms). Суммарный прирост SvS типа монотонен по
    # уровню апгрейда. Стартовый ключ (-1,) меньше любого реального (SvS >= 0).
    best = {"key": (-1,), "combo": None, "cost": None}

    # Полный список всех ДОПУСТИМЫХ комбинаций с целевой функцией.
    all_combos = []

    acc = {"Guide": 0, "Design": 0, "SvS": 0}

    def dfs(i, chosen):
        if i == len(groups):
            prio = tuple(opt["SvS"] for opt in chosen)
            all_combos.append({
                **{names[k]: chosen[k]["levels"] for k in range(len(chosen))},
                "Guide": acc["Guide"],
                "Design": acc["Design"],
                "SvS": acc["SvS"],
                "score": acc["SvS"] * SCORE_MULTIPLIER,
                "_prio": prio,
            })
            candidate = (acc["SvS"],) + prio
            if candidate > best["key"]:
                best["key"] = candidate
                best["combo"] = list(chosen)
                best["cost"] = {r: acc[r] for r in CHARM_RESOURCE_KEYS}
            return

        for opt in groups[i]:
            # варианты отсортированы по Guide -> при превышении Guide все следующие
            # тоже не влезут, останавливаемся.
            if acc["Guide"] + opt["Guide"] > resources.get("Guide", 0):
                break
            # по Design отсортированности нет -> просто пропускаем вариант.
            if acc["Design"] + opt["Design"] > resources.get("Design", 0):
                continue

            for r in CHARM_RESOURCE_KEYS:
                acc[r] += opt[r]
            acc["SvS"] += opt["SvS"]
            chosen.append(opt)

            dfs(i + 1, chosen)

            chosen.pop()
            acc["SvS"] -= opt["SvS"]
            for r in CHARM_RESOURCE_KEYS:
                acc[r] -= opt[r]

    dfs(0, [])

    remaining = {r: resources[r] - best["cost"][r] for r in CHARM_RESOURCE_KEYS}

    # сортировка по убыванию цели, при равенстве — по приоритету типа,
    # чтобы верхняя строка совпадала с выбранным оптимумом
    all_combos = (
        pd.DataFrame(all_combos)
        .sort_values(["score", "_prio"], ascending=False)
        .drop(columns="_prio")
        .reset_index(drop=True)
    )

    # таблица апгрейдов (лучшее решение): old -> new уровни талисманов по типу
    best_row = all_combos.iloc[0]
    upgrade_table = pd.DataFrame({
        "gear": names,
        "old_tier": [c.current_levels for c in charms],
        "new_tier": [list(best_row[name]) for name in names],
    })

    score = best["key"][0] * SCORE_MULTIPLIER
    return upgrade_table, best["cost"], remaining, score, all_combos
