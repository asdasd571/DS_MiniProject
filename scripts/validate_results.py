"""Fail fast when generated result files and documented metrics diverge."""
from pathlib import Path

import numpy as np
import pandas as pd

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
}


def main() -> None:
    for batch, expected in EXPECTED_VALID.items():
        features = pd.read_csv(RESULTS / f"feature_dataset_batch{batch}.csv")
        quality = pd.read_csv(RESULTS / "tables" / f"quality_report_batch{batch}.csv")
        assert features.cell_id.is_unique, f"Batch {batch}: duplicate cell rows"
        assert int(quality.valid_for_model.sum()) == expected, f"Batch {batch}: valid count changed"
        assert quality.num_cycles.notna().all(), f"Batch {batch}: missing cycle count"

    performance = pd.read_csv(RESULTS / "model_performance.csv")
    assert np.isfinite(performance.mape_percent).all(), "Non-finite performance value"
    errors = pd.read_csv(RESULTS / "tables" / "error_analysis_batch2.csv")
    recomputed = np.mean(np.abs(errors.cycle_life - errors.prediction) / errors.cycle_life) * 100
    recorded = performance.loc[performance.set.eq("Test (Batch2)"), "mape_percent"].iloc[0]
    assert np.isclose(recomputed, recorded), "Batch 2 MAPE does not match error table"

    available = {path.name for path in (RESULTS / "figures").glob("*.png")}
    assert REQUIRED_FIGURES <= available, f"Missing figures: {sorted(REQUIRED_FIGURES - available)}"
    readme = (ROOT / "README.md").read_text()
    for value in ("10.45%", "8.48%", "37.01%", "16.93%", "-0.886", "-0.880"):
        assert value in readme, f"README missing current metric {value}"
    print("PASS: result tables, figures, quality counts, MAPE, and README metrics are consistent")


if __name__ == "__main__":
    main()
