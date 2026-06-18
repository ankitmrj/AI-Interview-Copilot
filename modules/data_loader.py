
from __future__ import annotations

from pathlib import Path
from typing import Union, IO, Any

import pandas as pd


REQUIRED_COLUMNS = ["question"]


def normalize_role(role: str) -> str:
    return (role or "").strip().lower()


def _read_csv(source: Union[str, Path, IO[bytes], IO[str]]) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        return pd.read_csv(source)
    return pd.read_csv(source)


def load_question_bank(source: Union[str, Path, IO[bytes], IO[str]]) -> pd.DataFrame:
    """
    Load a Kaggle CSV or local CSV.

    Expected optional columns:
    role, category, difficulty, ideal_points
    """
    df = _read_csv(source).copy()

    if "question" not in df.columns:
        raise ValueError("Dataset must contain a 'question' column.")

    for col in ["role", "category", "difficulty", "ideal_points"]:
        if col not in df.columns:
            df[col] = ""

    df["role"] = df["role"].fillna("").astype(str).map(normalize_role)
    df["category"] = df["category"].fillna("").astype(str)
    df["difficulty"] = df["difficulty"].fillna("mixed").astype(str).str.lower()
    df["ideal_points"] = df["ideal_points"].fillna("").astype(str)
    df["question"] = df["question"].fillna("").astype(str)

    df = df[df["question"].str.strip() != ""].reset_index(drop=True)

    if df.empty:
        raise ValueError("No valid questions found in dataset.")

    return df


def filter_bank(df: pd.DataFrame, role: str, difficulty: str = "mixed") -> pd.DataFrame:
    role = normalize_role(role)
    out = df.copy()

    if role:
        role_mask = out["role"].str.contains(role, na=False) | out["role"].eq("")
        out = out[role_mask]

    if difficulty and difficulty != "mixed":
        out = out[out["difficulty"].str.contains(difficulty, na=False) | out["difficulty"].eq("mixed")]

    return out.reset_index(drop=True)
