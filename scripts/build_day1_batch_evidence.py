"""Build the DAY1 batch-comparison evidence used by the presentation.

The script reuses the repository's preprocessing and feature definitions.  It
does not retrain a model.  Output is a compact JSON payload for editable charts
and CSV tables that make the reported numbers easy to audit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr

from src.features import MODEL_FEATURES, extract_batch
from src.preprocess import BatteryBatchReader


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


def _report_style() -> None:
    pretendard = Path.home() / "Library" / "Fonts" / "Pretendard-Regular.otf"
    if pretendard.exists():
        font_manager.fontManager.addfont(pretendard)
    available = {font.name for font in font_manager.fontManager.ttflist}
    family = next((name for name in ("Pretendard", "Apple SD Gothic Neo", "NanumGothic") if name in available), "DejaVu Sans")
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update({
        "font.family": family, "axes.unicode_minus": False,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.edgecolor": "#D7E3E8", "grid.color": "#E3EBEF",
        "axes.titleweight": "bold", "axes.titlesize": 14,
        "axes.labelsize": 12, "xtick.labelsize": 10, "ytick.labelsize": 10,
        "legend.fontsize": 9,
    })


def build_report_figures(
    valid: dict[str, pd.DataFrame],
    curves: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]],
    degradation: dict[str, dict[str, np.ndarray]],
    payload: dict[str, object],
    figure_dir: Path,
) -> None:
    """Generate the five report figures from the same evidence payload."""
    _report_style()
    figure_dir.mkdir(parents=True, exist_ok=True)
    colors = {"Batch1": "#2F73B7", "Batch2": "#F28C28", "Batch3": "#009B96"}
    batches = tuple(BATCH_PATHS)

    # EDA 01: identical bins and axes for the three Cycle Life distributions.
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharex=True, sharey=True)
    bins = np.arange(150, 2401, 150)
    for ax, batch in zip(axes, batches):
        values = valid[batch].cycle_life
        ax.hist(values, bins=bins, color=colors[batch], edgecolor="white", alpha=.9)
        ax.axvline(500, color="#F28C28", linestyle="--", linewidth=1.5)
        ax.axvline(1000, color="#009B96", linestyle="--", linewidth=1.5)
        ax.set(title=batch, xlabel="Cycle Life", xlim=(150, 2300))
    axes[0].set_ylabel("Cell count")
    fig.suptitle("EDA 01 | Batch별 Cycle Life 분포", fontsize=18, fontweight="bold")
    fig.tight_layout(); fig.savefig(figure_dir / "day1_eda01_cycle_life_by_batch.png", dpi=200); plt.close(fig)

    # EDA 02: all valid QD curves over the full life and the first 100 cycles.
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharey=True)
    for column, batch in enumerate(batches):
        data = valid[batch].set_index("cell_id")
        median_life = data.cycle_life.median()
        highlight = (data.cycle_life - median_life).abs().idxmin()
        for cell_id in data.index:
            qd = np.asarray(degradation[batch].get(cell_id, []), dtype=float)
            if not len(qd):
                continue
            style = {"color": colors[batch], "linewidth": 2.2, "alpha": .95} if cell_id == highlight else {"color": "#B9C9D2", "linewidth": .7, "alpha": .55}
            axes[0, column].plot(np.arange(1, len(qd) + 1), qd, **style)
            axes[1, column].plot(np.arange(1, min(100, len(qd)) + 1), qd[:100], **style)
        axes[0, column].set(title=f"{batch} | 전체", xlim=(0, 2300), ylim=(.75, 1.15))
        axes[1, column].set(title=f"{batch} | 초기 100", xlim=(0, 100), ylim=(.75, 1.15), xlabel="Cycle")
    axes[0, 0].set_ylabel("QD (Ah)"); axes[1, 0].set_ylabel("QD (Ah)")
    fig.suptitle("EDA 02 | 전체 수명 열화와 초기 100 Cycle", fontsize=18, fontweight="bold")
    fig.tight_layout(); fig.savefig(figure_dir / "day1_eda02_qd_degradation_by_batch.png", dpi=200); plt.close(fig)

    # EDA 03: representative ΔQ(V) curves plus the key log-variance relation.
    group_colors = {"단수명": "#F28C28", "중간": "#2F73B7", "장수명": "#009B96"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for column, batch in enumerate(batches):
        report = payload["batches"][batch]
        for item in report["delta_q_representatives"]:
            axes[0, column].plot(item["x"], item["y"], label=f'{item["group"]} ({item["life"]:.0f})', color=group_colors[item["group"]], linewidth=2)
        axes[0, column].set(title=f"{batch} | ΔQ(V)", xlim=(2.0, 3.6), ylim=(-.12, .12), xlabel="Voltage (V)", ylabel="ΔQ (Ah)")
        axes[0, column].legend()
        sns.regplot(data=valid[batch], x="log_dq_var", y="cycle_life", ax=axes[1, column], color=colors[batch], scatter_kws={"s": 28, "alpha": .85}, line_kws={"linestyle": "--"})
        r = report["delta_q_scatter"]["pearson"]
        axes[1, column].set(title=f"{batch} | Pearson r={r:+.2f}", xlabel="log10 Var(ΔQ)", ylabel="Cycle Life", xlim=(-5.5, -3.0), ylim=(150, 2300))
    fig.suptitle("EDA 03 | 초기 ΔQ(V)와 장기 Cycle Life", fontsize=18, fontweight="bold")
    fig.tight_layout(); fig.savefig(figure_dir / "day1_eda03_delta_q_by_batch.png", dpi=200); plt.close(fig)

    # EDA 04: protocol means and the first C-rate relationship.
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for column, batch in enumerate(batches):
        report = payload["batches"][batch]
        policies = pd.DataFrame(report["charging_policy"]).sort_values("mean")
        labels = [label.replace("-newstructure", "") for label in policies.label]
        axes[0, column].barh(labels, policies["mean"], color=colors[batch])
        axes[0, column].set(title=f"{batch} | Protocol 평균", xlabel="Mean Cycle Life", xlim=(0, 2000))
        sns.regplot(data=valid[batch], x="first_c_rate", y="cycle_life", ax=axes[1, column], color=colors[batch], scatter_kws={"s": 28, "alpha": .85}, line_kws={"linestyle": "--"})
        r = report["relationships"]["first_c_rate"]["pearson"]
        axes[1, column].set(title=f"{batch} | Pearson r={r:+.2f}", xlabel="First C-rate", ylabel="Cycle Life", xlim=(3, 8.5), ylim=(150, 2300))
    fig.suptitle("EDA 04 | 충전 Protocol, C-rate와 수명", fontsize=18, fontweight="bold")
    fig.tight_layout(); fig.savefig(figure_dir / "day1_eda04_charging_by_batch.png", dpi=200); plt.close(fig)

    # EDA 05: target correlation across batches and Batch 1 collinearity.
    selected = ["log_dq_var", "dq_mean", "dq_min", "dq_range", "qd_slope_10_100", "qd_10", "first_c_rate", "ir_change_10_100"]
    target_matrix = pd.DataFrame({batch: [payload["batches"][batch]["feature_target"][feature]["pearson"] for feature in selected] for batch in batches}, index=selected)
    b1_corr = valid["Batch1"][selected].corr()
    fig, axes = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [1, 1.5]})
    sns.heatmap(target_matrix, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1, ax=axes[0], cbar=False)
    axes[0].set_title("Feature ↔ Cycle Life")
    sns.heatmap(b1_corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1, ax=axes[1], cbar=False)
    axes[1].set_title("Batch 1 Feature 간 상관")
    fig.suptitle("EDA 05 | Target 관계와 다중공선성", fontsize=18, fontweight="bold")
    fig.tight_layout(); fig.savefig(figure_dir / "day1_eda05_correlation_strategy.png", dpi=200); plt.close(fig)


def build_day1_artifacts(archive: Path | dict[str, Path], results: Path) -> dict[str, object]:
    """Rebuild every table and figure cited by the DAY1 report."""
    table_dir = results / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    batch_paths = (
        {batch: Path(path) for batch, path in archive.items()}
        if isinstance(archive, dict)
        else {batch: Path(archive) / filename for batch, filename in BATCH_PATHS.items()}
    )

    frames: dict[str, pd.DataFrame] = {}
    qualities: dict[str, pd.DataFrame] = {}
    curves: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    degradation: dict[str, dict[str, np.ndarray]] = {}
    valid: dict[str, pd.DataFrame] = {}

    for batch in BATCH_PATHS:
        frames[batch] = pd.read_csv(results / f"feature_dataset_{batch.lower()}.csv")
        qualities[batch] = pd.read_csv(table_dir / f"quality_report_{batch.lower()}.csv")
        ids = set(qualities[batch].loc[qualities[batch].valid_for_model, "cell_id"])
        valid[batch] = frames[batch][frames[batch].cell_id.isin(ids)].copy().reset_index(drop=True)
        _, _, curves[batch], degradation[batch] = extract_batch(
            BatteryBatchReader(batch_paths[batch], batch).iter_cells()
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
    strategy = {
        "input_x": MODEL_FEATURES,
        "raw_target_y": "cycle_life",
        "model_target": "log(cycle_life)",
        "forbidden_model_features": ["cycle_life", "knee_cycle", "knee_fraction"],
        "candidate_models": ["LinearRegression", "ElasticNet", "GradientBoosting"],
        "selection_data": "Batch1 train/validation only",
        "validation_group": "charging_policy",
        "external_evaluation": ["Batch2", "Batch3"],
        "external_results_used_for_tuning": False,
    }
    (table_dir / "day1_model_strategy.json").write_text(json.dumps(strategy, ensure_ascii=False, indent=2))
    build_report_figures(valid, curves, degradation, payload, results / "figures")
    return {"summary": summary_rows, "high_pairs": pairs[:5], "strategy": strategy}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("/Users/nak/Downloads/archive"))
    parser.add_argument("--results", type=Path, default=Path("results"))
    args = parser.parse_args()
    report = build_day1_artifacts(args.archive, args.results)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
