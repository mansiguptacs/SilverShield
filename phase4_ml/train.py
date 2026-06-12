"""Phase 4: Train + track a recall-severity classifier with Guild AI.

Pipeline: TfidfVectorizer -> TruncatedSVD -> LogisticRegression.
Labels: openFDA classification (Class I/II/III) -> Lethal/Moderate/Minor.

The TruncatedSVD step decorrelates the high-dimensional, highly-correlated
TF-IDF features (the requested multicollinearity mitigation). We log the mean
pairwise feature correlation before vs. after SVD as evidence.

Run directly:
    python phase4_ml/train.py --max_features 5000 --svd_components 120 --C 1.0
Run + track with Guild (from phase4_ml/):
    guild run train max_features=5000 svd_components=120 C=1.0
Compare runs:
    guild compare
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(os.environ.get("SAFETYNET_ROOT", Path(__file__).resolve().parents[1]))
TRAIN_CSV = ROOT / "data" / "training_recalls.csv"
CANONICAL_MODEL = ROOT / "phase4_ml" / "models" / "severity_model.joblib"


def mean_abs_offdiag_corr(matrix: np.ndarray) -> float:
    """Mean absolute off-diagonal correlation across columns (collinearity proxy)."""
    if matrix.shape[1] < 2:
        return 0.0
    corr = np.corrcoef(matrix, rowvar=False)
    corr = np.nan_to_num(corr)
    n = corr.shape[0]
    off = corr[~np.eye(n, dtype=bool)]
    return float(np.mean(np.abs(off)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max_features", type=int, default=5000)
    ap.add_argument("--ngram_max", type=int, default=2)
    ap.add_argument("--svd_components", type=int, default=120)
    ap.add_argument("--C", type=float, default=1.0)
    ap.add_argument("--test_size", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save_canonical", action="store_true",
                    help="also write the model to phase4_ml/models/ for predict.py")
    args = ap.parse_args()

    df = pd.read_csv(TRAIN_CSV)
    X = df["reason_for_recall"].astype(str)
    y = df["severity"].astype(str)
    print(f"Loaded {len(df)} labeled recalls. Class balance:\n{y.value_counts().to_string()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=args.max_features,
            ngram_range=(1, args.ngram_max),
            stop_words="english",
            sublinear_tf=True,
        )),
        ("svd", TruncatedSVD(n_components=args.svd_components, random_state=args.seed)),
        ("clf", LogisticRegression(
            C=args.C, max_iter=1000, class_weight="balanced",
        )),
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="macro")

    # Multicollinearity evidence: correlation among the most informative TF-IDF
    # columns (pre-SVD) vs. the decorrelated SVD components (post-SVD).
    tfidf = pipeline.named_steps["tfidf"]
    svd = pipeline.named_steps["svd"]
    tfidf_mat = tfidf.transform(X_train)
    top_idx = np.asarray(tfidf_mat.sum(axis=0)).ravel().argsort()[-60:]
    pre = mean_abs_offdiag_corr(tfidf_mat[:, top_idx].toarray())
    post = mean_abs_offdiag_corr(svd.transform(tfidf_mat))

    print("\nclassification report:")
    print(classification_report(y_test, y_pred))
    print(f"accuracy: {acc:.4f}")
    print(f"f1_macro: {f1:.4f}")
    print(f"pre_svd_corr: {pre:.4f}")
    print(f"post_svd_corr: {post:.4f}")
    print(f"collinearity_reduction: {(pre - post):.4f}")

    # Save model: always to cwd (Guild tracks it as a run artifact); optionally
    # to the canonical path used by predict.py / the orchestrator.
    joblib.dump({"pipeline": pipeline, "classes": sorted(y.unique())}, "severity_model.joblib")
    if args.save_canonical:
        CANONICAL_MODEL.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": pipeline, "classes": sorted(y.unique())}, CANONICAL_MODEL)
        print(f"saved canonical model -> {CANONICAL_MODEL}")


if __name__ == "__main__":
    main()
