"""Shared Pandas loading helpers for analytical workflows."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.cleaning import DATA_CONTRACTS, clean_datasets


def load_clean_datasets(data_dir: Path | str) -> dict[str, pd.DataFrame]:
    """Read and clean all required CSV datasets from a directory."""
    root = Path(data_dir)
    frames: dict[str, pd.DataFrame] = {}
    for name in DATA_CONTRACTS:
        path = root / f"{name}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Required input file not found: {path}")
        frames[name] = pd.read_csv(path, dtype="string", keep_default_na=True)
    cleaned, _ = clean_datasets(frames)
    return cleaned
