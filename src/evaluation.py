"""Evaluation helpers and publication-ready plots."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import mean_absolute_percentage_error


def mape_percent(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(mean_absolute_percentage_error(actual, predicted) * 100.0)


def save_prediction_plots(actual: np.ndarray, predicted: np.ndarray, batch: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(actual, predicted, alpha=.8)
    bounds = [min(actual.min(), predicted.min()), max(actual.max(), predicted.max())]
    ax.plot(bounds, bounds, "--", color="black", label="Perfect prediction (y=x)")
    ax.set(title=f"{batch}: Actual vs Predicted Cycle Life", xlabel="Actual cycle life (cycles)", ylabel="Predicted cycle life (cycles)")
    ax.legend(); fig.tight_layout(); fig.savefig(output / f"test_{batch.lower()}_actual_vs_pred.png", dpi=180); plt.close(fig)
    pct = (actual - predicted) / actual * 100
    fig, ax = plt.subplots(figsize=(7, 5)); sns.histplot(pct, bins=12, kde=True, ax=ax)
    ax.axvline(0, color="black", linestyle="--")
    ax.set(title=f"{batch}: Percentage Residuals", xlabel="(Actual - prediction) / actual (%)", ylabel="Cell count")
    fig.tight_layout(); fig.savefig(output / f"test_{batch.lower()}_residual.png", dpi=180); plt.close(fig)


def error_table(frame: pd.DataFrame, predicted: np.ndarray) -> pd.DataFrame:
    result = frame.copy()
    result["prediction"] = predicted
    result["absolute_error"] = np.abs(result["cycle_life"] - result["prediction"])
    result["absolute_percentage_error"] = result["absolute_error"] / result["cycle_life"] * 100
    return result.sort_values("absolute_percentage_error", ascending=False)
