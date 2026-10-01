"""Cell-level feature extraction using only cycles 1--100."""
from __future__ import annotations

import re
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew

from .preprocess import BatteryCell, finite_count

EPSILON = 1e-12
POLICY_PATTERN = re.compile(r"([0-9.]+)C\(([0-9.]+)%\)-([0-9.]+)C", re.I)


def parse_policy(policy: str) -> tuple[float, float, float]:
    match = POLICY_PATTERN.search(policy.replace(" ", ""))
    if not match:
        return np.nan, np.nan, np.nan
    return float(match.group(1)), float(match.group(2)) / 100.0, float(match.group(3))


def _at(values: np.ndarray | None, cycle: int) -> float:
    if values is None or len(values) < cycle:
        return np.nan
    value = float(values[cycle - 1])
    return value if np.isfinite(value) else np.nan


def _window(values: np.ndarray | None, start: int = 10, end: int = 100) -> np.ndarray:
    if values is None or len(values) < end:
        return np.asarray([], dtype=float)
    return np.asarray(values[start - 1:end], dtype=float)


def _slope(values: np.ndarray | None, start: int = 10, end: int = 100) -> float:
    window = _window(values, start, end)
    finite = np.isfinite(window)
    return float(np.polyfit(np.arange(start, end + 1)[finite], window[finite], 1)[0]) if finite.sum() >= 2 else np.nan


def aligned_delta_q(cell: BatteryCell, points: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate cycle 10/100 Qdlin onto their common voltage interval."""
    if cell.qdlin_10 is None or cell.qdlin_100 is None:
        return np.array([]), np.array([])
    q10, q100, voltage = cell.qdlin_10, cell.qdlin_100, cell.vdlin
    if min(len(q10), len(q100), len(voltage)) < 2:
        return np.array([]), np.array([])
    v10, v100 = voltage[:len(q10)], voltage[:len(q100)]
    valid10, valid100 = np.isfinite(v10) & np.isfinite(q10), np.isfinite(v100) & np.isfinite(q100)
    if valid10.sum() < 2 or valid100.sum() < 2:
        return np.array([]), np.array([])
    lo = max(float(v10[valid10].min()), float(v100[valid100].min()))
    hi = min(float(v10[valid10].max()), float(v100[valid100].max()))
    if lo >= hi:
        return np.array([]), np.array([])
    grid = np.linspace(lo, hi, points)
    order10, order100 = np.argsort(v10[valid10]), np.argsort(v100[valid100])
    dq = np.interp(grid, v100[valid100][order100], q100[valid100][order100]) - np.interp(grid, v10[valid10][order10], q10[valid10][order10])
    return grid, dq


def extract_cell_features(cell: BatteryCell) -> tuple[dict[str, object], dict[str, object]]:
    first_c, switch_soc, second_c = parse_policy(cell.charging_policy)
    qd, ir = cell.summary.get("qd"), cell.summary.get("ir")
    grid, dq = aligned_delta_q(cell)
    arrays = list(cell.summary.values()) + [a for a in (cell.qdlin_10, cell.qdlin_100) if a is not None]
    missing, infinite = finite_count(arrays)
    num_cycles = max((len(a) for a in cell.summary.values()), default=0)
    valid = np.isfinite(cell.cycle_life) and num_cycles >= 100 and dq.size > 0 and np.isfinite(dq).all()
    row: dict[str, object] = {
        "cell_id": cell.cell_id, "batch": cell.batch, "cycle_life": cell.cycle_life,
        "charging_policy": cell.charging_policy, "first_c_rate": first_c,
        "switch_soc": switch_soc, "second_c_rate": second_c,
        "qd_10": _at(qd, 10), "qd_100": _at(qd, 100),
        "qd_change_10_100": _at(qd, 100) - _at(qd, 10), "qd_slope_10_100": _slope(qd),
        "qd_slope_2_100": _slope(qd, 2, 100),
        "qd_std_10_100": float(np.nanstd(_window(qd), ddof=1)) if len(_window(qd)) else np.nan,
        "ir_10": _at(ir, 10), "ir_100": _at(ir, 100),
        "ir_change_10_100": _at(ir, 100) - _at(ir, 10),
    }
    for key, mode in (("tavg", "mean"), ("tmin", "mean"), ("tmax", "max"), ("charge_time", "mean")):
        window = _window(cell.summary.get(key))
        row[f"{key}_{mode}_10_100"] = float(np.nanmean(window) if mode == "mean" else np.nanmax(window)) if len(window) else np.nan
    ct = cell.summary.get("charge_time")
    row["charge_time_change_10_100"] = _at(ct, 100) - _at(ct, 10)
    if dq.size:
        variance = float(np.var(dq))
        row.update(dq_mean=float(np.mean(dq)), dq_min=float(np.min(dq)), dq_max=float(np.max(dq)),
                   dq_std=float(np.std(dq)), dq_var=variance, log_dq_var=float(np.log10(max(variance, EPSILON))),
                   dq_range=float(np.ptp(dq)), dq_skew=float(skew(dq)), dq_kurtosis=float(kurtosis(dq)))
    else:
        row.update({key: np.nan for key in ("dq_mean", "dq_min", "dq_max", "dq_std", "dq_var", "log_dq_var", "dq_range", "dq_skew", "dq_kurtosis")})
    quality = {
        "cell_id": cell.cell_id, "batch": cell.batch, "cycle_life": cell.cycle_life,
        "charging_policy": cell.charging_policy, "summary_length": len(qd) if qd is not None else 0,
        "num_cycles": cell.num_cycle_records, "has_cycle_10": cell.num_cycle_records >= 10,
        "has_cycle_100": cell.num_cycle_records >= 100,
        "has_qdlin_10": cell.qdlin_10 is not None, "has_qdlin_100": cell.qdlin_100 is not None,
        "num_missing": missing, "num_inf": infinite, "valid_for_model": valid,
        "exclusion_reason": "" if valid else ("missing cycle_life target" if not np.isfinite(cell.cycle_life) else "missing/invalid cycle 10 or 100 Qdlin/summary"),
    }
    return row, quality


def extract_batch(cells: Iterable[BatteryCell]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, tuple[np.ndarray, np.ndarray]], dict[str, np.ndarray]]:
    rows, quality_rows, curves, degradation = [], [], {}, {}
    for cell in cells:
        row, quality = extract_cell_features(cell)
        rows.append(row); quality_rows.append(quality)
        curves[cell.cell_id] = aligned_delta_q(cell)
        degradation[cell.cell_id] = np.asarray(cell.summary.get("qd", []), dtype=float)
    return pd.DataFrame(rows), pd.DataFrame(quality_rows), curves, degradation
