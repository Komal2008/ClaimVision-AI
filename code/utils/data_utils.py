import os
from pathlib import Path
import pandas as pd

DATASET_DIR = Path(__file__).resolve().parents[2] / "dataset"


def list_dataset_csv(dataset_dir: Path = DATASET_DIR) -> list[str]:
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.exists():
        return []
    return sorted([path.name for path in dataset_dir.glob("*.csv")])


def load_dataset(filename: str, dataset_dir: Path = DATASET_DIR) -> pd.DataFrame | None:
    try:
        filepath = Path(dataset_dir) / filename
        if not filepath.exists():
            return None
        return pd.read_csv(filepath)
    except Exception:
        return None


def memory_usage_bytes(df: pd.DataFrame) -> int:
    return int(df.memory_usage(deep=True).sum())


def memory_usage_human(bytes_value: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} TB"


def column_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = []
    for column in df.columns:
        series = df[column]
        dtype = str(series.dtype)
        non_null = int(series.count())
        missing = int(series.isna().sum())
        unique = int(series.nunique(dropna=True))
        top = series.mode().iloc[0] if not series.mode().empty else "N/A"
        freq = (
            int(series.value_counts(dropna=True).iloc[0])
            if not series.value_counts(dropna=True).empty
            else 0
        )
        summary.append(
            {
                "column": column,
                "dtype": dtype,
                "non_null": non_null,
                "missing": missing,
                "unique": unique,
                "top_value": top,
                "top_freq": freq,
            }
        )
    return pd.DataFrame(summary)


def clean_dataset(
    df: pd.DataFrame, drop_duplicates: bool = True, fill_method: str | None = None
) -> pd.DataFrame:
    clean_df = df.copy()
    if drop_duplicates:
        clean_df = clean_df.drop_duplicates()
    if fill_method == "ffill":
        clean_df = clean_df.fillna(method="ffill")
    elif fill_method == "bfill":
        clean_df = clean_df.fillna(method="bfill")
    elif fill_method == "zero":
        clean_df = clean_df.fillna(0)
    return clean_df


def split_metadata_columns(df: pd.DataFrame) -> tuple[dict[str, int], dict[str, str]]:
    numeric = {col: int(df[col].dtype != "object") for col in df.columns}
    dtypes = {col: str(df[col].dtype) for col in df.columns}
    return numeric, dtypes
