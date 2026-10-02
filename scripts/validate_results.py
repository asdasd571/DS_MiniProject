"""Fail fast when generated result files and documented metrics diverge."""
from pathlib import Path

import numpy as np
import pandas as pd
import json

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

EXPECTED_VALID = {1: 41, 2: 34, 3: 40}
REQUIRED_FIGURES = {
    "eda_cycle_life_hist.png", "eda_cycle_life_boxplot.png",
    "eda_degradation_curve.png", "eda_delta_q_curve.png",
    "eda_delta_q_vs_cycle_life.png", "eda_charging_policy.png",
    "eda_feature_target_corr.png", "eda_feature_corr_heatmap.png",
    "test_batch2_actual_vs_pred.png", "test_batch2_residual.png",
    "batch_feature_distribution_shift.png",
    "day1_eda01_cycle_life_by_batch.png", "day1_eda02_qd_degradation_by_batch.png",
    "day1_eda03_delta_q_by_batch.png", "day1_eda04_charging_by_batch.png",
    "day1_eda05_correlation_strategy.png",
}

EXPECTED_PERFORMANCE_ROWS = [
    "Train (Batch 1 CV)", "Valid (Batch 1 Hold-out)", "Test (Batch 2)",
    "Gap (Train-Valid)", "Gap (Valid-Test)", "Gap (Target-Test)",
    "Test (Batch 3)", "Gap (Batch2-Batch3)", "Gap (Target-Batch3)",
]


def main() -> None:
    for batch, expected in EXPECTED_VALID.items():
        features = pd.read_csv(RESULTS / f"feature_dataset_batch{batch}.csv")
        quality = pd.read_csv(RESULTS / "tables" / f"quality_report_batch{batch}.csv")
        assert features.cell_id.is_unique, f"Batch {batch}: duplicate cell rows"
        assert int(quality.valid_for_model.sum()) == expected, f"Batch {batch}: valid count changed"
        assert quality.num_cycles.notna().all(), f"Batch {batch}: missing cycle count"

    performance = pd.read_csv(RESULTS / "model_performance.csv")
    assert np.isfinite(performance.mape_percent).all(), "Non-finite performance value"
    assert performance.set.tolist() == EXPECTED_PERFORMANCE_ROWS, "DAY 2 performance rows/order changed"
    scores = performance.set_index("set").mape_percent
    for batch in (2, 3):
        errors = pd.read_csv(RESULTS / "tables" / f"error_analysis_batch{batch}.csv")
        recomputed = np.mean(np.abs(errors.cycle_life - errors.prediction) / errors.cycle_life) * 100
        assert np.isclose(recomputed, scores[f"Test (Batch {batch})"]), f"Batch {batch} MAPE mismatch"
    assert np.isclose(scores["Gap (Train-Valid)"], scores["Valid (Batch 1 Hold-out)"] - scores["Train (Batch 1 CV)"])
    assert np.isclose(scores["Gap (Valid-Test)"], scores["Test (Batch 2)"] - scores["Valid (Batch 1 Hold-out)"])
    assert np.isclose(scores["Gap (Target-Test)"], scores["Test (Batch 2)"] - 9.1)
    assert np.isclose(scores["Gap (Batch2-Batch3)"], scores["Test (Batch 3)"] - scores["Test (Batch 2)"])
    assert np.isclose(scores["Gap (Target-Batch3)"], scores["Test (Batch 3)"] - 9.1)

    audit = pd.read_csv(RESULTS / "tables" / "day2_split_audit.csv")
    train_policies = set(audit.loc[audit.split.eq("Train (Batch 1)"), "charging_policy"])
    valid_policies = set(audit.loc[audit.split.eq("Valid (Batch 1 Hold-out)"), "charging_policy"])
    assert train_policies.isdisjoint(valid_policies), "charging policy leaked into hold-out"
    metadata = json.loads((RESULTS / "tables" / "model_metadata.json").read_text())
    assert metadata["external_results_used_for_selection"] is False
    assert metadata["target_feature_forbidden"] not in metadata["features"]

    available = {path.name for path in (RESULTS / "figures").glob("*.png")}
    assert REQUIRED_FIGURES <= available, f"Missing figures: {sorted(REQUIRED_FIGURES - available)}"
    readme = (ROOT / "README.md").read_text()
    for value in ("10.45%", "8.48%", "37.01%", "16.93%", "-0.886", "-0.880"):
        assert value in readme, f"README missing current metric {value}"
    print("PASS: DAY 1/2 artifacts, split isolation, MAPE/gaps, figures, and README are consistent")


if __name__ == "__main__":
    main()
