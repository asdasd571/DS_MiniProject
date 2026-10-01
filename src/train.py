"""End-to-end extraction, EDA, training, and external-batch evaluation."""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, LinearRegression
from sklearn.model_selection import GridSearchCV, GroupKFold, GroupShuffleSplit, KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .evaluation import error_table, mape_percent, save_prediction_plots
from .features import extract_batch
from .preprocess import BatteryBatchReader

RANDOM_STATE = 42
# Cell indices documented by the authors' public Load Data notebook. Batch 2
# entries are physical continuations of Batch 1 cells; Batch 3 entries are noisy.
PAPER_EXCLUSIONS = {
    "Batch1": {8: "paper exclusion: did not reach 80% capacity", 10: "paper exclusion: did not reach 80% capacity", 12: "paper exclusion: did not reach 80% capacity", 13: "paper exclusion: did not reach 80% capacity", 22: "paper exclusion: did not reach 80% capacity"},
    "Batch2": {7: "paper exclusion: continuation of Batch1 cell", 8: "paper exclusion: continuation of Batch1 cell", 9: "paper exclusion: continuation of Batch1 cell", 15: "paper exclusion: continuation of Batch1 cell", 16: "paper exclusion: continuation of Batch1 cell"},
    "Batch3": {2: "paper exclusion: noisy channel", 23: "paper exclusion: noisy channel", 32: "paper exclusion: noisy channel", 37: "paper exclusion: noisy channel", 42: "paper exclusion: noisy channel", 43: "paper exclusion: noisy channel"},
}
MODEL_FEATURES = [
    "log_dq_var", "dq_mean", "dq_min", "dq_range", "qd_10", "qd_100",
    "qd_slope_10_100", "ir_10", "ir_change_10_100", "tavg_mean_10_100",
    "tmax_max_10_100", "charge_time_mean_10_100", "first_c_rate", "switch_soc", "second_c_rate",
]


def _log_mape_scorer(estimator, x, y_log) -> float:
    return -mape_percent(np.exp(y_log), np.exp(estimator.predict(x)))


def _valid(frame: pd.DataFrame, quality: pd.DataFrame) -> pd.DataFrame:
    ids = quality.loc[quality.valid_for_model, "cell_id"]
    return frame[frame.cell_id.isin(ids)].reset_index(drop=True)


def extract_all(paths: dict[str, Path], output: Path):
    frames, qualities, curves, degradation, schemas = {}, {}, {}, {}, {}
    for name, path in paths.items():
        reader = BatteryBatchReader(path, name)
        schemas[name] = reader.inspect()
        frame, quality, batch_curves, batch_degradation = extract_batch(reader.iter_cells())
        for index, reason in PAPER_EXCLUSIONS.get(name, {}).items():
            cell_id = f"{name}_cell_{index:03d}"
            mask = quality.cell_id.eq(cell_id)
            quality.loc[mask, "valid_for_model"] = False
            quality.loc[mask, "exclusion_reason"] = reason
        frame.to_csv(output / f"feature_dataset_{name.lower()}.csv", index=False)
        quality.to_csv(output / "tables" / f"quality_report_{name.lower()}.csv", index=False)
        frames[name], qualities[name], curves[name] = frame, quality, batch_curves
        degradation[name] = batch_degradation
    excluded = pd.concat([q[~q.valid_for_model] for q in qualities.values()], ignore_index=True)
    excluded[["cell_id", "batch", "exclusion_reason"]].to_csv(output / "tables" / "excluded_cells.csv", index=False)
    (output / "tables" / "data_schema.json").write_text(json.dumps(schemas, indent=2, ensure_ascii=False))
    return frames, qualities, curves, degradation


def eda(frames, qualities, curves, degradation, figures: Path, tables: Path) -> dict[str, float]:
    valid = {key: _valid(frames[key], qualities[key]) for key in frames}
    all_data = pd.concat(valid.values(), ignore_index=True)
    summary = all_data.groupby("batch")["cycle_life"].agg(["count", "mean", "median", "std", "min", "max"])
    for label, mask in {"short_pct": all_data.cycle_life < 500, "middle_pct": all_data.cycle_life.between(500, 1000), "long_pct": all_data.cycle_life > 1000}.items():
        summary[label] = all_data.assign(flag=mask).groupby("batch").flag.mean() * 100
    summary.to_csv(tables / "cycle_life_summary.csv")
    fig, ax = plt.subplots(figsize=(9, 6))
    for name, group in all_data.groupby("batch"): sns.histplot(group.cycle_life, bins=15, element="step", fill=False, label=name, ax=ax)
    ax.set(title="Cycle Life Distribution by Batch", xlabel="Cycle life (cycles)", ylabel="Cell count"); ax.legend(); fig.tight_layout(); fig.savefig(figures / "eda_cycle_life_hist.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5)); sns.boxplot(data=all_data, x="batch", y="cycle_life", ax=ax)
    ax.set(title="Cycle Life by Batch", xlabel="Dataset batch", ylabel="Cycle life (cycles)"); fig.tight_layout(); fig.savefig(figures / "eda_cycle_life_boxplot.png", dpi=180); plt.close(fig)

    b1 = valid["Batch1"]
    numeric = [c for c in b1.select_dtypes("number").columns if c != "cycle_life"]
    correlations = []
    for col in numeric:
        subset = b1[[col, "cycle_life"]].dropna()
        if len(subset) > 2 and subset[col].nunique() > 1:
            correlations.append({"feature": col, "pearson": pearsonr(subset[col], subset.cycle_life).statistic, "spearman": spearmanr(subset[col], subset.cycle_life).statistic})
    corr = pd.DataFrame(correlations).sort_values("pearson", key=abs, ascending=False)
    corr.to_csv(tables / "feature_target_correlations.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 7)); display = corr.head(15).sort_values("pearson")
    ax.barh(display.feature, display.pearson); ax.set(title="Batch 1 Feature vs Cycle Life", xlabel="Pearson correlation", ylabel="Feature"); fig.tight_layout(); fig.savefig(figures / "eda_feature_target_corr.png", dpi=180); plt.close(fig)
    heat_cols = [c for c in MODEL_FEATURES if c in b1 and b1[c].notna().any()]
    fig, ax = plt.subplots(figsize=(13, 11)); sns.heatmap(b1[heat_cols].corr(), cmap="RdBu_r", center=0, ax=ax)
    ax.set_title("Batch 1 Feature Correlation"); fig.tight_layout(); fig.savefig(figures / "eda_feature_corr_heatmap.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6)); top_policy = b1.charging_policy.value_counts().head(15).index
    sns.boxplot(data=b1[b1.charging_policy.isin(top_policy)], x="charging_policy", y="cycle_life", ax=ax)
    ax.tick_params(axis="x", rotation=65); ax.set(title="Batch 1 Charging Policy vs Cycle Life", xlabel="Charging policy", ylabel="Cycle life (cycles)"); fig.tight_layout(); fig.savefig(figures / "eda_charging_policy.png", dpi=180); plt.close(fig)
    b1.groupby("charging_policy").cycle_life.agg(["count", "mean", "median", "std"]).to_csv(tables / "charging_policy_summary.csv")

    representatives = []
    for group_name, condition in (("Short", b1.cycle_life < 500), ("Middle", b1.cycle_life.between(500, 1000)), ("Long", b1.cycle_life > 1000)):
        group = b1[condition]
        if not group.empty:
            median = group.cycle_life.median(); representatives.extend(group.iloc[(group.cycle_life - median).abs().argsort()[:2]].cell_id.tolist())
    fig, ax = plt.subplots(figsize=(9, 6))
    for cid in representatives:
        qd = degradation["Batch1"][cid]
        ax.plot(np.arange(1, len(qd) + 1), qd, label=f"{cid} ({int(b1.set_index('cell_id').loc[cid, 'cycle_life'])})", alpha=.8)
    ax.set(title="Representative Capacity Degradation Curves", xlabel="Cycle number", ylabel="Discharge capacity QD (Ah)")
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(figures / "eda_degradation_curve.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 6))
    for cid in representatives:
        grid, dq = curves["Batch1"][cid]
        ax.plot(grid, dq, label=f"{cid} ({int(b1.set_index('cell_id').loc[cid, 'cycle_life'])})")
    ax.set(title="Representative Batch 1 ΔQ(V): Cycle 100 − Cycle 10", xlabel="Voltage (V)", ylabel="ΔQ (Ah)"); ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(figures / "eda_delta_q_curve.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 5)); sns.regplot(data=b1, x="log_dq_var", y="cycle_life", ax=ax)
    p = pearsonr(b1.log_dq_var, b1.cycle_life).statistic; s = spearmanr(b1.log_dq_var, b1.cycle_life).statistic
    ax.set(title=f"Batch 1 ΔQ Variance vs Cycle Life (Pearson={p:.3f}, Spearman={s:.3f})", xlabel="log10(var(ΔQ100−10))", ylabel="Cycle life (cycles)"); fig.tight_layout(); fig.savefig(figures / "eda_delta_q_vs_cycle_life.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6));
    for name, group in all_data.groupby("batch"): sns.kdeplot(data=group, x="log_dq_var", label=name, ax=ax)
    ax.set(title="Distribution Shift in Key ΔQ Feature", xlabel="log10(var(ΔQ100−10))", ylabel="Density"); ax.legend(); fig.tight_layout(); fig.savefig(figures / "batch_feature_distribution_shift.png", dpi=180); plt.close(fig)
    return {"dq_pearson": float(p), "dq_spearman": float(s)}


def modeling(frames, qualities, output: Path):
    datasets = {key: _valid(frames[key], qualities[key]) for key in frames}
    b1 = datasets["Batch1"]
    features = [c for c in MODEL_FEATURES if c in b1 and b1[c].notna().any()]
    groups = b1.charging_policy.astype(str)
    if groups.nunique() >= 5:
        split = GroupShuffleSplit(n_splits=1, test_size=.2, random_state=RANDOM_STATE)
        train_idx, valid_idx = next(split.split(b1, groups=groups)); split_method = "GroupShuffleSplit by charging_policy"
    else:
        train_idx, valid_idx = train_test_split(np.arange(len(b1)), test_size=.2, random_state=RANDOM_STATE); split_method = "random hold-out"
    train, holdout = b1.iloc[train_idx], b1.iloc[valid_idx]
    cv = GroupKFold(n_splits=min(5, train.charging_policy.nunique())) if train.charging_policy.nunique() >= 3 else KFold(4, shuffle=True, random_state=RANDOM_STATE)
    cv_groups = train.charging_policy if isinstance(cv, GroupKFold) else None
    linear_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", LinearRegression())])
    elastic_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", ElasticNet(max_iter=100000, random_state=RANDOM_STATE))])
    boosting_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", GradientBoostingRegressor(random_state=RANDOM_STATE))])
    candidates = {
        "LinearRegression": (linear_pipe, {}),
        "ElasticNet": (elastic_pipe, {"model__alpha": [1e-4, 1e-3, 1e-2, .1, 1.0], "model__l1_ratio": [.1, .3, .5, .7, .9]}),
        "GradientBoosting": (boosting_pipe, {"model__n_estimators": [50, 100], "model__max_depth": [1, 2], "model__learning_rate": [.03, .05, .1]}),
    }
    comparisons, fitted = [], {}
    x_train, y_train = train[features], np.log(train.cycle_life.to_numpy())
    for name, (pipeline, grid) in candidates.items():
        search = GridSearchCV(pipeline, grid or [{}], scoring=_log_mape_scorer, cv=cv, n_jobs=-1, return_train_score=True)
        search.fit(x_train, y_train, groups=cv_groups)
        pred = np.exp(search.best_estimator_.predict(holdout[features]))
        comparisons.append({"model": name, "cv_mape": -search.best_score_, "cv_std": search.cv_results_["std_test_score"][search.best_index_], "valid_mape": mape_percent(holdout.cycle_life.to_numpy(), pred), "best_params": json.dumps(search.best_params_)})
        fitted[name] = search.best_estimator_
    comparison = pd.DataFrame(comparisons).sort_values(["valid_mape", "cv_mape"])
    comparison.to_csv(output / "tables" / "model_comparison.csv", index=False)
    # Prefer the stable, interpretable regularized model when its hold-out score is
    # close to the best candidate; do not select a tree from one favorable split alone.
    best_valid = float(comparison.valid_mape.min())
    elastic_row = comparison[comparison.model == "ElasticNet"].iloc[0]
    selected_name = "ElasticNet" if float(elastic_row.valid_mape) <= best_valid + 3.0 else str(comparison.iloc[0].model)
    selected = clone(fitted[selected_name]).fit(b1[features], np.log(b1.cycle_life.to_numpy()))
    rows = [{"set": "Train (Batch 1 CV)", "mape_percent": float(comparison.set_index("model").loc[selected_name, "cv_mape"]), "note": selected_name}, {"set": "Valid (Batch 1 Hold-out)", "mape_percent": float(comparison.set_index("model").loc[selected_name, "valid_mape"]), "note": split_method}]
    predictions = {}
    for name in ("Batch2", "Batch3"):
        data = datasets[name]; pred = np.exp(selected.predict(data[features])); predictions[name] = pred
        score = mape_percent(data.cycle_life.to_numpy(), pred); rows.append({"set": f"Test ({name})", "mape_percent": score, "note": "external batch; no tuning"})
        save_prediction_plots(data.cycle_life.to_numpy(), pred, name, output / "figures")
        error_table(data, pred).to_csv(output / "tables" / f"error_analysis_{name.lower()}.csv", index=False)
    perf = pd.DataFrame(rows)
    cv_score, val_score = perf.iloc[0].mape_percent, perf.iloc[1].mape_percent
    b2_score, b3_score = perf.iloc[2].mape_percent, perf.iloc[3].mape_percent
    gaps = pd.DataFrame([{"set": "Gap Train-Valid", "mape_percent": val_score-cv_score, "note": "%p"}, {"set": "Gap Valid-Test", "mape_percent": b2_score-val_score, "note": "%p"}, {"set": "Gap Target-Test", "mape_percent": b2_score-9.1, "note": "%p vs paper target"}, {"set": "Gap Batch2-Batch3", "mape_percent": b3_score-b2_score, "note": "%p"}])
    pd.concat([perf, gaps], ignore_index=True).to_csv(output / "model_performance.csv", index=False)
    metadata = {"selected_model": selected_name, "features": features, "split_method": split_method, "model_comparison": comparisons}
    (output / "tables" / "model_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch1", type=Path, required=True); parser.add_argument("--batch2", type=Path, required=True); parser.add_argument("--batch3", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args(); output = args.output_dir
    for directory in (output, output / "figures", output / "tables"): directory.mkdir(parents=True, exist_ok=True)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    frames, qualities, curves, degradation = extract_all({"Batch1": args.batch1, "Batch2": args.batch2, "Batch3": args.batch3}, output)
    insights = eda(frames, qualities, curves, degradation, output / "figures", output / "tables")
    metadata = modeling(frames, qualities, output)
    (output / "run_summary.json").write_text(json.dumps({**insights, **metadata}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
