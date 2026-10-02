"""Build the DAY1 batch-comparison evidence used by the presentation.

The script reuses the repository's preprocessing and feature definitions.  It
does not retrain a model.  Output is a compact JSON payload for editable charts
and CSV tables that make the reported numbers easy to audit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from src.features import extract_batch
from src.preprocess import BatteryBatchReader
from src.train import MODEL_FEATURES


BATCH_PATHS = {
    "Batch1": "2017-05-12_batchdata_updated_struct_errorcorrect.mat",
    "Batch2": "2018-02-20_batchdata_updated_struct_errorcorrect.mat",
    "Batch3": "2018-04-12_batchdata_updated_struct_errorcorrect.mat",
}
GROUPS = (
    ("단수명", lambda s: s < 500),
    ("중간", lambda s: s.between(500, 1000, inclusive="both")),
    ("장수명", lambda s: s > 1000),
)


def corr_pair(frame: pd.DataFrame, x: str, y: str = "cycle_life") -> dict[str, float | int | None]:
    data = frame[[x, y]].dropna()
    if len(data) < 3 or data[x].nunique() < 2 or data[y].nunique() < 2:
        return {"n": int(len(data)), "pearson": None, "spearman": None}
    return {
        "n": int(len(data)),
        "pearson": float(pearsonr(data[x], data[y]).statistic),
        "spearman": float(spearmanr(data[x], data[y]).statistic),
    }


def finite_list(values) -> list[float | None]:
    return [float(v) if np.isfinite(v) else None for v in values]


def downsample_xy(x: np.ndarray, y: np.ndarray, max_points: int) -> dict[str, list[float | None]]:
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    if len(x) > max_points:
        indices = np.linspace(0, len(x) - 1, max_points).round().astype(int)
        x, y = x[indices], y[indices]
    return {"x": finite_list(x), "y": finite_list(y)}


def knee_point(qd: np.ndarray, cycle_life: float) -> float | None:
    """Exploratory post-hoc knee: max deviation from a start/end chord.

    The full-life QD curve is median-smoothed (11 cycles), restricted to cycle
    10 through observed EOL, then normalized.  This quantity is descriptive and
    must never be used as an early-life model feature.
    """
    end = min(len(qd), int(cycle_life))
    if end < 120:
        return None
    values = pd.Series(qd[:end], dtype=float).rolling(11, center=True, min_periods=1).median().to_numpy()
    x = np.arange(1, end + 1, dtype=float)[9:]
    y = values[9:]
    finite = np.isfinite(y)
    x, y = x[finite], y[finite]
    if len(x) < 100 or np.ptp(y) == 0:
        return None
    xn = (x - x[0]) / (x[-1] - x[0])
    yn = (y - y[0]) / np.ptp(y)
    chord = yn[0] + (yn[-1] - yn[0]) * xn
    deviation = yn - chord
    return float(x[int(np.nanargmax(deviation))])


def histogram_counts(values: pd.Series) -> dict[str, list[float | int]]:
    edges = np.arange(150, 2401, 150)
    counts, _ = np.histogram(values, bins=edges)
    centers = ((edges[:-1] + edges[1:]) / 2).astype(int)
    return {"centers": centers.tolist(), "counts": counts.astype(int).tolist(), "edges": edges.tolist()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("/Users/nak/Downloads/archive"))
    parser.add_argument("--results", type=Path, default=Path("results"))
    args = parser.parse_args()
    table_dir = args.results / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    frames: dict[str, pd.DataFrame] = {}
    qualities: dict[str, pd.DataFrame] = {}
    curves: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    degradation: dict[str, dict[str, np.ndarray]] = {}
    valid: dict[str, pd.DataFrame] = {}

    for batch, filename in BATCH_PATHS.items():
        frames[batch] = pd.read_csv(args.results / f"feature_dataset_{batch.lower()}.csv")
        qualities[batch] = pd.read_csv(table_dir / f"quality_report_{batch.lower()}.csv")
        ids = set(qualities[batch].loc[qualities[batch].valid_for_model, "cell_id"])
        valid[batch] = frames[batch][frames[batch].cell_id.isin(ids)].copy().reset_index(drop=True)
        _, _, curves[batch], degradation[batch] = extract_batch(
            BatteryBatchReader(args.archive / filename, batch).iter_cells()
        )

    payload: dict[str, object] = {"source": "repository preprocessing and feature CSVs", "batches": {}}
    summary_rows, shortest_rows, relation_rows = [], [], []

    for batch in BATCH_PATHS:
        data = valid[batch]
        counts = {
            "short": int((data.cycle_life < 500).sum()),
            "middle": int(data.cycle_life.between(500, 1000, inclusive="both").sum()),
            "long": int((data.cycle_life > 1000).sum()),
        }
        summary = {
            "n": int(len(data)),
            "mean": float(data.cycle_life.mean()),
            "median": float(data.cycle_life.median()),
            "std": float(data.cycle_life.std(ddof=1)),
            "min": float(data.cycle_life.min()),
            "max": float(data.cycle_life.max()),
            "short_n": counts["short"],
            "middle_n": counts["middle"],
            "long_n": counts["long"],
            "short_pct": float(100 * counts["short"] / len(data)),
            "middle_pct": float(100 * counts["middle"] / len(data)),
            "long_pct": float(100 * counts["long"] / len(data)),
        }
        summary_rows.append({"batch": batch, **summary})

        quality = qualities[batch][["cell_id", "valid_for_model", "exclusion_reason"]]
        shortest = frames[batch].merge(quality, on="cell_id", how="left").nsmallest(3, "cycle_life")
        shortest_items = []
        for row in shortest.itertuples():
            status = "분석 포함" if bool(row.valid_for_model) else f"제외: {row.exclusion_reason}"
            item = {"cell_id": row.cell_id, "cycle_life": float(row.cycle_life), "status": status}
            shortest_items.append(item)
            shortest_rows.append({"batch": batch, **item})

        qd_lines = []
        early_lines = []
        knees = []
        knee_fractions = []
        for row in data.itertuples():
            qd = np.asarray(degradation[batch].get(row.cell_id, []), dtype=float)
            if len(qd) == 0:
                continue
            full = downsample_xy(np.arange(1, len(qd) + 1, dtype=float), qd, 120)
            qd_lines.append({"cell_id": row.cell_id, "life": float(row.cycle_life), **full})
            early_n = min(100, len(qd))
            early = downsample_xy(np.arange(1, early_n + 1, dtype=float), qd[:early_n], 100)
            early_lines.append({"cell_id": row.cell_id, "life": float(row.cycle_life), **early})
            knee = knee_point(qd, row.cycle_life)
            if knee is not None:
                knees.append(knee)
                knee_fractions.append(knee / float(row.cycle_life))

        representatives = []
        for group_name, condition in GROUPS:
            subset = data[condition(data.cycle_life)]
            if subset.empty:
                continue
            median_life = subset.cycle_life.median()
            selected = subset.iloc[(subset.cycle_life - median_life).abs().argsort()[:1]].iloc[0]
            grid, dq = curves[batch].get(selected.cell_id, (np.array([]), np.array([])))
            if len(grid):
                representatives.append({
                    "group": group_name,
                    "cell_id": selected.cell_id,
                    "life": float(selected.cycle_life),
                    **downsample_xy(np.asarray(grid), np.asarray(dq), 140),
                })

        policy = (
            data.groupby("charging_policy", dropna=False).cycle_life
            .agg(["count", "mean", "std"])
            .sort_values(["count", "mean"], ascending=[False, False])
            .head(6)
            .reset_index()
        )
        policy_records = []
        for row in policy.itertuples():
            label = str(row.charging_policy).replace("-", " / ")
            policy_records.append({
                "policy": str(row.charging_policy), "label": label, "n": int(row.count),
                "mean": float(row.mean), "std": None if pd.isna(row.std) else float(row.std),
            })

        relationships = {}
        for feature in ("qd_slope_10_100", "log_dq_var", "first_c_rate"):
            relationships[feature] = corr_pair(data, feature)
            relation_rows.append({"batch": batch, "x": feature, "y": "cycle_life", **relationships[feature]})
        relationships["c_rate_vs_qd_slope"] = corr_pair(data, "first_c_rate", "qd_slope_10_100")
        relationships["c_rate_vs_log_dq_var"] = corr_pair(data, "first_c_rate", "log_dq_var")
        relation_rows.extend([
            {"batch": batch, "x": "first_c_rate", "y": "qd_slope_10_100", **relationships["c_rate_vs_qd_slope"]},
            {"batch": batch, "x": "first_c_rate", "y": "log_dq_var", **relationships["c_rate_vs_log_dq_var"]},
        ])

        feature_target = {}
        for feature in MODEL_FEATURES:
            if feature in data:
                feature_target[feature] = corr_pair(data, feature)

        payload["batches"][batch] = {
            "summary": summary,
            "histogram": histogram_counts(data.cycle_life),
            "shortest": shortest_items,
            "qd_full": qd_lines,
            "qd_early": early_lines,
            "qd_slope_median": float(data.qd_slope_10_100.median()),
            "qd_slope_positive_pct": float(100 * (data.qd_slope_10_100 > 0).mean()),
            "knee_median_cycle": None if not knees else float(np.median(knees)),
            "knee_median_fraction": None if not knee_fractions else float(np.median(knee_fractions)),
            "delta_q_representatives": representatives,
            "delta_q_scatter": {
                "x": finite_list(data.log_dq_var.to_numpy()),
                "y": finite_list(data.cycle_life.to_numpy()),
                "pearson": relationships["log_dq_var"]["pearson"],
                "spearman": relationships["log_dq_var"]["spearman"],
            },
            "charging_policy": policy_records,
            "c_rate_scatter": {
                "x": finite_list(data.first_c_rate.to_numpy()),
                "y": finite_list(data.cycle_life.to_numpy()),
                "pearson": relationships["first_c_rate"]["pearson"],
                "spearman": relationships["first_c_rate"]["spearman"],
            },
            "relationships": relationships,
            "feature_target": feature_target,
        }

    b1 = valid["Batch1"]
    feature_columns = [name for name in MODEL_FEATURES if name in b1 and b1[name].notna().any()]
    feature_corr = b1[feature_columns].corr()
    pairs = []
    for i, left in enumerate(feature_columns):
        for right in feature_columns[i + 1:]:
            value = feature_corr.loc[left, right]
            if np.isfinite(value):
                pairs.append({"left": left, "right": right, "pearson": float(value)})
    pairs.sort(key=lambda item: abs(item["pearson"]), reverse=True)
    payload["correlation"] = {
        "features": feature_columns,
        "batch_target": {
            batch: [payload["batches"][batch]["feature_target"].get(f, {}).get("pearson") for f in feature_columns]
            for batch in BATCH_PATHS
        },
        "batch1_matrix": [[float(v) if np.isfinite(v) else None for v in feature_corr.loc[row, feature_columns]] for row in feature_columns],
        "high_pairs": pairs[:8],
    }

    (table_dir / "day1_batch_comparison.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    pd.DataFrame(summary_rows).to_csv(table_dir / "day1_batch_summary.csv", index=False)
    pd.DataFrame(shortest_rows).to_csv(table_dir / "day1_shortest_cells.csv", index=False)
    pd.DataFrame(relation_rows).to_csv(table_dir / "day1_relationships.csv", index=False)
    print(json.dumps({"summary": summary_rows, "high_pairs": pairs[:5]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
