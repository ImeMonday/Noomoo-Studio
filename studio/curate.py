"""Deterministic grid curation.

1. Select 9 of N images: brand-palette affinity + visual impact, with a diversity bonus
   so the grid covers different subjects (exterior, food, interior, detail...).
2. Arrange them 3x3 by exhaustively scoring all 9! = 362,880 layouts and keeping the
   lowest-energy one. Same inputs always produce the same grid.
"""
from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass

import numpy as np

from . import colors
from .config import Brand

# 3x3 grid, row-major. Checkerboard: arch-framed tiles on the odd cells.
ARCH_CELLS = (1, 3, 5, 7)
EDGES = [(0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (7, 8),
         (0, 3), (3, 6), (1, 4), (4, 7), (2, 5), (5, 8)]
POS_WEIGHT = np.array([1.0, .8, .8, .6, .5, .5, .4, .3, .3]) * 0.9
DIVERSITY_BONUS = (0.35, 0.10, -0.25, -0.60)

_PERMS = None


def _perms() -> np.ndarray:
    global _PERMS
    if _PERMS is None:
        _PERMS = np.array(list(itertools.permutations(range(9))), dtype=np.int8)
    return _PERMS


@dataclass
class GridPlan:
    order: list          # image ids, row-major
    arch_bg: dict        # cell index -> palette role used behind the arch image
    report: dict


def _norm(values: np.ndarray) -> np.ndarray:
    span = values.max() - values.min()
    return (values - values.min()) / span if span else np.zeros_like(values)


def scores(infos: list, brand: Brand) -> tuple:
    """Return (affinity, impact), both 0..1, aligned with infos."""
    pal = colors.rgb_to_lab([colors.hex_to_rgb(brand.palette[k]) for k in ("primary", "accent", "soft", "paper")])
    affinity = np.array([np.exp(-min(colors.delta_e(i.lab, p) for p in pal) / 45) for i in infos])
    impact = 0.5 * _norm(np.array([i.chroma for i in infos])) + 0.3 * _norm(np.array([i.edge for i in infos])) \
        + 0.2 * _norm(np.array([abs(i.lightness - 50) for i in infos]))
    return affinity, impact


def select(infos: list, brand: Brand, n: int = 9) -> list:
    affinity, impact = scores(infos, brand)
    base = 0.6 * affinity + 0.4 * impact
    chosen, seen = [], Counter()
    remaining = list(range(len(infos)))
    while len(chosen) < n and remaining:
        def gain(k):
            return base[k] + DIVERSITY_BONUS[min(seen[infos[k].category], 3)]
        best = max(remaining, key=lambda k: (round(gain(k), 9), infos[k].id))
        chosen.append(best)
        seen[infos[best].category] += 1
        remaining.remove(best)
    return chosen


def edge_cost(infos: list) -> np.ndarray:
    """Pairwise cost of putting two images next to each other."""
    labs = np.array([i.lab for i in infos])
    d_e = np.linalg.norm(labs[:, None] - labs[None], axis=2)
    d_l = np.abs(labs[:, None, 0] - labs[None, :, 0])
    same = np.array([[a.category == b.category for b in infos] for a in infos], dtype=float)
    return 0.8 * d_e / 60 + 1.2 * same + 0.6 * np.clip((14 - d_l) / 14, 0, 1)


def arrange(infos: list, brand: Brand) -> tuple:
    """Exhaustive search for the minimum-energy 3x3 arrangement."""
    cost = edge_cost(infos)
    _, impact = scores(infos, brand)
    perms = _perms()
    energy = np.zeros(len(perms))
    for a, b in EDGES:
        energy += cost[perms[:, a], perms[:, b]]
    for p in range(9):
        energy -= POS_WEIGHT[p] * impact[perms[:, p]]
    best = int(np.argmin(energy))      # first minimum -> deterministic tie-break
    stats = {"energy_best": round(float(energy[best]), 3), "energy_median": round(float(np.median(energy)), 3),
             "energy_worst": round(float(energy.max()), 3), "layouts_searched": int(len(perms))}
    return [int(v) for v in perms[best]], stats


def pick_arch_backgrounds(infos_in_order: list, brand: Brand) -> dict:
    """Choose the palette role behind each arch image: contrast with the photo, spread across tiles."""
    used, out = Counter(), {}
    for cell in ARCH_CELLS:
        info = infos_in_order[cell]
        lab = info.lab

        def gain(role):
            bg = colors.rgb_to_lab([colors.hex_to_rgb(brand.palette[role])])[0]
            return colors.delta_e(lab, bg) / 50 - 0.6 * used[role]
        role = max(brand.tile_backgrounds, key=lambda r: (round(gain(r), 9), r))
        used[role] += 1
        out[cell] = role
    return out


def plan_grid(library: dict, brand: Brand, locked: dict | None = None) -> tuple:
    """Return (GridPlan, leftover image ids). `locked` maps cell -> image id to keep in place."""
    infos = sorted(library.values(), key=lambda i: i.id)
    locked = locked or {}
    if locked:
        free_infos = [i for i in infos if i.id not in locked.values()]
        free_cells = [c for c in range(9) if c not in locked]
        pick = [free_infos[k] for k in select(free_infos, brand, len(free_cells))]
        order = [None] * 9
        for c, iid in locked.items():
            order[c] = library[iid]
        # fill free cells with the best-ordered picks (energy over the free sub-grid is approximated by position weight)
        pick.sort(key=lambda i: -scores([i], brand)[1][0])
        for c, info in zip(free_cells, pick):
            order[c] = info
        stats = {"note": "partial re-curation with locked cells", "locked": sorted(locked)}
        chosen = order
    else:
        idx = select(infos, brand)
        sel = [infos[k] for k in idx]
        perm, stats = arrange(sel, brand)
        chosen = [sel[k] for k in perm]
    bg = pick_arch_backgrounds(chosen, brand)
    leftovers = [i.id for i in infos if i.id not in {c.id for c in chosen}]
    report = {**stats, "cells": [{"cell": n, "image": c.id, "category": c.category,
                                  "template": "arch" if n in ARCH_CELLS else "full"} for n, c in enumerate(chosen)]}
    return GridPlan([c.id for c in chosen], bg, report), leftovers


def pick_story_images(library: dict, brand: Brand, specs: list, leftovers: list, taken: set) -> list:
    """Assign one image per story: best category match from leftovers, else from anything unused."""
    chosen = []
    for spec in specs:
        pools = [[library[i] for i in leftovers if i not in chosen],
                 [i for i in library.values() if i.id not in chosen and i.id not in taken],
                 [i for i in library.values() if i.id not in chosen]]
        pool = next(p for p in pools if p)
        affinity, impact = scores(pool, brand)

        def gain(k):
            cat = 0.6 if pool[k].category in spec.prefer else 0.0
            return cat + 0.4 * affinity[k] + 0.3 * impact[k]
        best = max(range(len(pool)), key=lambda k: (round(gain(k), 9), pool[k].id))
        chosen.append(pool[best].id)
    return chosen
