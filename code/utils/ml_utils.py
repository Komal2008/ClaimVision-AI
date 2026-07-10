import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier


def get_default_models() -> dict[str, Any]:
    return {
        "Logistic Regression": LogisticRegression(
            max_iter=500, solver="lbfgs", multi_class="auto"
        ),
        "Decision Tree": DecisionTreeClassifier(random_state=42),
        "Random Forest": RandomForestClassifier(random_state=42, n_estimators=100),
        "Gradient Boosting": GradientBoostingClassifier(random_state=42),
        "KNN": KNeighborsClassifier(n_neighbors=5),
    }


def encode_categorical_columns(
    df: pd.DataFrame, categorical_columns: list[str]
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    df_copy = df.copy()
    encoders: dict[str, LabelEncoder] = {}
    for column in categorical_columns:
        encoder = LabelEncoder()
        df_copy[column] = encoder.fit_transform(
            df_copy[column].astype(str).fillna("Missing")
        )
        encoders[column] = encoder
    return df_copy, encoders


def build_feature_matrix(
    df: pd.DataFrame, target: str, feature_columns: list[str] | None = None
) -> tuple[pd.DataFrame, pd.Series]:
    if feature_columns is None:
        feature_columns = [
            col
            for col in df.columns
            if col != target and col != "user_claim" and col != "image_paths"
        ]
    X = df[feature_columns].copy()
    y = df[target].copy()
    return X, y


def standardize_numeric(X: pd.DataFrame) -> tuple[pd.DataFrame, StandardScaler | None]:
    numeric_columns = X.select_dtypes(include=["number"]).columns.tolist()
    scaler = None
    if numeric_columns:
        scaler = StandardScaler()
        X[numeric_columns] = scaler.fit_transform(X[numeric_columns])
    return X, scaler


def evaluate_classification(y_true, y_pred) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "f1_score": float(
            f1_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
    }


def train_models(
    X_train, X_test, y_train, y_test, model_map: dict[str, Any]
) -> list[dict[str, Any]]:
    results = []
    for name, model in model_map.items():
        try:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            metrics = evaluate_classification(y_test, y_pred)
            results.append({"model": name, **metrics, "model_object": model})
        except Exception:
            continue
    return results


def grid_search_model(model, param_grid: dict[str, list[Any]], X_train, y_train):
    try:
        grid = GridSearchCV(model, param_grid, cv=3, scoring="f1_weighted", n_jobs=-1)
        grid.fit(X_train, y_train)
        return grid
    except Exception:
        return None


def save_model(
    model,
    model_name: str,
    target: str,
    metrics: dict[str, float],
    models_dir: Path = Path("models"),
) -> Path:
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / f"{model_name.lower().replace(' ', '_')}_{target}.joblib"
    dump(model, model_path)
    metadata_path = models_dir / "leaderboard.json"
    leaderboard = []
    if metadata_path.exists():
        try:
            leaderboard = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            leaderboard = []
    leaderboard = [
        entry for entry in leaderboard if entry.get("model_path") != str(model_path)
    ]
    leaderboard.append(
        {
            "model_name": model_name,
            "target": target,
            "model_path": str(model_path),
            "metrics": metrics,
        }
    )
    metadata_path.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    return model_path


def load_leaderboard(models_dir: Path = Path("models")) -> list[dict[str, Any]]:
    metadata_path = models_dir / "leaderboard.json"
    if not metadata_path.exists():
        return []
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return []


def prepare_claim_features(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    if "image_paths" in df_copy.columns:
        df_copy["image_count"] = (
            df_copy["image_paths"]
            .fillna("")
            .apply(
                lambda value: len(str(value).split(";")) if str(value).strip() else 0
            )
        )
    if "user_claim" in df_copy.columns:
        df_copy["claim_length"] = df_copy["user_claim"].astype(str).apply(len)
        df_copy["word_count"] = (
            df_copy["user_claim"].astype(str).apply(lambda text: len(str(text).split()))
        )
        df_copy["has_question"] = (
            df_copy["user_claim"]
            .astype(str)
            .str.contains(r"\?", regex=False)
            .astype(int)
        )
    if "claim_object" in df_copy.columns:
        encoder = LabelEncoder()
        df_copy["claim_object_encoded"] = encoder.fit_transform(
            df_copy["claim_object"].astype(str).fillna("Missing")
        )
    return df_copy
