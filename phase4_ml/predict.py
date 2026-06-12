"""Phase 4 inference: classify a recall reason into Lethal / Moderate / Minor.

Loads the canonical Guild-trained model. Runs in the MAIN venv (scikit-learn +
joblib only - no Guild/protobuf). The orchestrator imports `classify` from here.
Falls back to the raw openFDA classification mapping if the model is missing.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from settings import CLASSIFICATION_TO_SEVERITY  # noqa: E402

MODEL_PATH = ROOT / "phase4_ml" / "models" / "severity_model.joblib"


@lru_cache(maxsize=1)
def _load_model():
    try:
        import joblib
        bundle = joblib.load(MODEL_PATH)
        return bundle["pipeline"], bundle["classes"]
    except Exception as exc:  # noqa: BLE001
        print(f"[predict] model unavailable ({exc}); using classification fallback")
        return None, None


def classify(reason_text: str, fallback_classification: str | None = None) -> dict:
    """Return {severity, confidence, source}.

    Uses the ML model when available; otherwise maps the openFDA classification.
    """
    pipeline, classes = _load_model()
    if pipeline is None:
        sev = CLASSIFICATION_TO_SEVERITY.get(fallback_classification or "", "Minor")
        return {"severity": sev, "confidence": 0.5, "source": "classification_fallback", "proba": {sev: 1.0}}

    text = (reason_text or "").strip()
    if not text:
        sev = CLASSIFICATION_TO_SEVERITY.get(fallback_classification or "", "Minor")
        return {"severity": sev, "confidence": 0.5, "source": "empty_text_fallback", "proba": {sev: 1.0}}

    proba = pipeline.predict_proba([text])[0]
    idx = int(proba.argmax())
    label = pipeline.classes_[idx]
    dist = {str(c): round(float(p), 3) for c, p in zip(pipeline.classes_, proba)}
    return {"severity": str(label), "confidence": round(float(proba[idx]), 3),
            "source": "ml_model", "proba": dist}


if __name__ == "__main__":
    samples = [
        "Products may contain a life-threatening bacterial contaminant; risk of death.",
        "Label mix-up: bottle declares wrong tablet count, no health hazard.",
        "Out of specification dissolution results found during stability testing.",
    ]
    for s in samples:
        print(f"{classify(s)}  <- {s[:60]}")
