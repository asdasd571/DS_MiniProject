"""Memory-conscious reader for the MATLAB v7.3 battery dataset."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import h5py
import numpy as np
import pandas as pd


SUMMARY_ALIASES = {
    "qd": ("QDischarge", "QD"),
    "qc": ("QCharge", "QC"),
    "ir": ("IR",),
    "tmax": ("Tmax",),
    "tavg": ("Tavg",),
    "tmin": ("Tmin",),
    "charge_time": ("chargetime", "charge_time"),
    "discharge_time": ("discharge_time", "dischargetime"),
}


def _flat_numeric(obj: h5py.Dataset) -> np.ndarray:
    return np.asarray(obj[()]).astype(float, copy=False).reshape(-1)


def _deref(file: h5py.File, value: Any) -> h5py.Group | h5py.Dataset:
    """Resolve MATLAB references, including singleton ndarray wrappers."""
    while isinstance(value, np.ndarray):
        value = value.reshape(-1)[0]
    return file[value] if isinstance(value, h5py.Reference) else value


def _decode_text(obj: h5py.Dataset) -> str:
    raw = np.asarray(obj[()]).reshape(-1)
    if raw.dtype.kind in "ui":
        return "".join(chr(int(x)) for x in raw if int(x) != 0)
    if raw.dtype.kind in "SU":
        return "".join(x.decode() if isinstance(x, bytes) else str(x) for x in raw)
    return str(raw[0]) if raw.size else ""


def _field(group: h5py.Group, aliases: tuple[str, ...]) -> h5py.Dataset | None:
    lookup = {key.lower(): key for key in group.keys()}
    for alias in aliases:
        if alias.lower() in lookup:
            return group[lookup[alias.lower()]]
    return None


def _read_vector(file: h5py.File, dataset: h5py.Dataset) -> np.ndarray:
    """Read either a numeric MATLAB vector or a vector behind one reference."""
    if h5py.check_dtype(ref=dataset.dtype) is None:
        return _flat_numeric(dataset)
    refs = np.asarray(dataset[()]).reshape(-1)
    if refs.size == 1:
        return _flat_numeric(_deref(file, refs[0]))
    values: list[float] = []
    for ref in refs:
        arr = _flat_numeric(_deref(file, ref))
        values.extend(arr.tolist())
    return np.asarray(values, dtype=float)


@dataclass
class BatteryCell:
    cell_id: str
    batch: str
    cycle_life: float
    charging_policy: str
    vdlin: np.ndarray
    summary: dict[str, np.ndarray]
    qdlin_10: np.ndarray | None
    qdlin_100: np.ndarray | None
    num_cycle_records: int
    cycle_fields: tuple[str, ...]


class BatteryBatchReader:
    """Stream cell records without deserializing every cycle time series."""

    def __init__(self, path: str | Path, batch_name: str):
        self.path = Path(path)
        self.batch_name = batch_name

    def inspect(self) -> dict[str, Any]:
        with h5py.File(self.path, "r") as file:
            batch = file["batch"]
            return {
                "path": str(self.path),
                "cell_count": int(batch[next(iter(batch.keys()))].shape[0]),
                "batch_fields": sorted(batch.keys()),
            }

    def iter_cells(self) -> Iterator[BatteryCell]:
        with h5py.File(self.path, "r") as file:
            batch = file["batch"]
            count = batch["summary"].shape[0]
            for index in range(count):
                yield self._read_cell(file, batch, index)

    def _object(self, file: h5py.File, batch: h5py.Group, field: str, index: int):
        return _deref(file, batch[field][index, 0])

    def _read_cell(self, file: h5py.File, batch: h5py.Group, index: int) -> BatteryCell:
        life = float(_flat_numeric(self._object(file, batch, "cycle_life", index))[0])
        policy = _decode_text(self._object(file, batch, "policy_readable", index))
        summary_group = self._object(file, batch, "summary", index)
        cycles_group = self._object(file, batch, "cycles", index)
        vdlin = _read_vector(file, self._object(file, batch, "Vdlin", index))

        summary: dict[str, np.ndarray] = {}
        for canonical, aliases in SUMMARY_ALIASES.items():
            dataset = _field(summary_group, aliases)
            if dataset is not None:
                summary[canonical] = _read_vector(file, dataset)

        qdlin_dataset = _field(cycles_group, ("Qdlin",))
        num_cycle_records = int(np.asarray(qdlin_dataset[()]).size) if qdlin_dataset is not None else 0
        qd10 = self._read_cycle_vector(file, qdlin_dataset, 9) if qdlin_dataset is not None else None
        qd100 = self._read_cycle_vector(file, qdlin_dataset, 99) if qdlin_dataset is not None else None
        return BatteryCell(
            cell_id=f"{self.batch_name}_cell_{index:03d}", batch=self.batch_name,
            cycle_life=life, charging_policy=policy, vdlin=vdlin, summary=summary,
            qdlin_10=qd10, qdlin_100=qd100, num_cycle_records=num_cycle_records,
            cycle_fields=tuple(sorted(cycles_group.keys())),
        )

    @staticmethod
    def _read_cycle_vector(file: h5py.File, dataset: h5py.Dataset, index: int) -> np.ndarray | None:
        refs = np.asarray(dataset[()]).reshape(-1) if h5py.check_dtype(ref=dataset.dtype) else None
        if refs is not None:
            if index >= refs.size:
                return None
            return _flat_numeric(_deref(file, refs[index]))
        data = np.asarray(dataset[()])
        if data.ndim < 2 or index >= max(data.shape):
            return None
        axis = 0 if data.shape[0] > data.shape[1] else 1
        return np.asarray(data[index, :] if axis == 0 else data[:, index], dtype=float).reshape(-1)


def finite_count(arrays: list[np.ndarray]) -> tuple[int, int]:
    """Return total missing and infinite values."""
    missing = sum(int(np.isnan(a).sum()) for a in arrays if a.size)
    infinite = sum(int(np.isinf(a).sum()) for a in arrays if a.size)
    return missing, infinite
