import json
import os
import pickle
from typing import Any, Dict, List

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")

CANONICAL_ARTIFACTS = {
    "baseline_classifier": {
        "model": "canonical_baseline_model.pkl",
        "scaler": "canonical_baseline_scaler.pkl",
        "features": "canonical_baseline_feature_columns.json",
        "metrics": "canonical_baseline_metrics.json",
        "legacy_model": "model.pkl",
        "legacy_scaler": "scaler.pkl",
        "legacy_features": "feature_columns.json",
    },
    "fair_champion": {
        "bundle": "canonical_fair_champion.pkl",
        "metrics": "canonical_fair_champion_metrics.json",
        "legacy_bundle": "fairlearn_lightgbm_eps_0.010.pkl",
    },
    "ranker": {
        "model": "canonical_ranker.pkl",
        "scaler": "canonical_ranker_scaler.pkl",
        "features": "canonical_ranker_feature_columns.json",
        "metrics": "canonical_ranker_metrics.json",
        "legacy_model": "ranker.pkl",
        "legacy_scaler": "ranker_scaler.pkl",
        "legacy_features": "ranker_feature_columns.json",
    },
}


def _path(name: str) -> str:
    return os.path.join(MODEL_DIR, name)


def _first_existing(*names: str) -> str:
    for name in names:
        if name and os.path.exists(_path(name)):
            return _path(name)
    raise FileNotFoundError(f"None of the artifact paths exist: {', '.join(names)}")


def _load_pickle(path: str) -> Any:
    with open(path, "rb") as handle:
        return pickle.load(handle)


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_classifier_artifact() -> Dict[str, Any]:
    config = CANONICAL_ARTIFACTS["baseline_classifier"]
    model_path = _first_existing(config["model"], config["legacy_model"])
    scaler_path = _first_existing(config["scaler"], config["legacy_scaler"])
    feature_path = _first_existing(config["features"], config["legacy_features"])
    return {
        "model": _load_pickle(model_path),
        "scaler": _load_pickle(scaler_path),
        "feature_cols": _load_json(feature_path),
        "artifact_path": os.path.basename(model_path),
    }


def load_ranker_artifact() -> Dict[str, Any]:
    config = CANONICAL_ARTIFACTS["ranker"]
    model_path = _first_existing(config["model"], config["legacy_model"])
    scaler_path = _first_existing(config["scaler"], config["legacy_scaler"])
    feature_path = _first_existing(config["features"], config["legacy_features"])
    return {
        "model": _load_pickle(model_path),
        "scaler": _load_pickle(scaler_path),
        "feature_cols": _load_json(feature_path),
        "artifact_path": os.path.basename(model_path),
    }


def load_fair_champion_artifact() -> Dict[str, Any]:
    config = CANONICAL_ARTIFACTS["fair_champion"]
    bundle_path = _first_existing(config["bundle"], config["legacy_bundle"])
    bundle = _load_pickle(bundle_path)
    if isinstance(bundle, dict):
      artifact = dict(bundle)
    else:
      classifier = load_classifier_artifact()
      artifact = {
          "model": bundle,
          "scaler": classifier["scaler"],
          "feature_cols": classifier["feature_cols"],
      }
    artifact["artifact_path"] = os.path.basename(bundle_path)
    return artifact


def save_json(name: str, payload: Any) -> str:
    path = _path(name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def save_pickle(name: str, payload: Any) -> str:
    path = _path(name)
    with open(path, "wb") as handle:
        pickle.dump(payload, handle)
    return path


def artifact_names() -> Dict[str, Dict[str, str]]:
    return CANONICAL_ARTIFACTS
