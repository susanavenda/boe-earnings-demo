"""Gated batch recalibration — NOT continuous online learning.

Why not retrain every quarter?
- Silver labels amplify FinBERT's own biases → alerts drift for no real reason
- PRA needs reproducible verdicts: a model that moves weekly is hard to defend
- Small N (≈100 turns): noise dominates; human labels are the scarce resource

Good pattern:
1. Score new quarters with the *promoted* frozen model (or zero-shot FinBERT)
2. Humans review a sample → grow hand_validation_sample.csv
3. Only when enough new human labels land, run light domain FT offline
4. Promote if hold-out macro-F1 does not regress vs the active model
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .paths import (
    HAND_LABELS,
    PIPELINE_MODELS,
    PIPELINE_PROCESSED,
    PIPELINE_PYTHON,
    PIPELINE_ROOT,
    PIPELINE_SCRIPTS,
)
from .registry import load_registry, record_run, register_model, save_registry

# Heuristic gates for "is a retrain worth it?"
MIN_HUMAN_ROWS = 40
MIN_NEW_SINCE_PROMOTE = 15
MIN_MACRO_F1 = 0.50


def _python() -> Path:
    if PIPELINE_PYTHON.exists():
        return PIPELINE_PYTHON
    return Path(sys.executable)


def count_human_labels() -> int:
    if not HAND_LABELS.exists():
        return 0
    try:
        import pandas as pd

        df = pd.read_csv(HAND_LABELS)
        if "human_reviewed" in df.columns:
            return int((df["human_reviewed"].astype(int) == 1).sum())
        if "gold_label" in df.columns:
            return int(df["gold_label"].notna().sum())
        return len(df)
    except Exception:
        return max(0, sum(1 for _ in HAND_LABELS.open()) - 1)


def active_human_baseline(reg: dict) -> int:
    mid = reg.get("active_model_id")
    for m in reg.get("models") or []:
        if m.get("model_id") == mid:
            return int(m.get("n_human_labels") or 0)
    return 0


def check_recalibration() -> dict:
    reg = load_registry()
    n_human = count_human_labels()
    baseline = active_human_baseline(reg)
    new_labels = max(0, n_human - baseline)
    metrics_path = PIPELINE_PROCESSED / "finetune_metrics.json"
    last_metrics = (
        json.loads(metrics_path.read_text()) if metrics_path.exists() else None
    )

    ready = n_human >= MIN_HUMAN_ROWS and new_labels >= MIN_NEW_SINCE_PROMOTE
    reasons = []
    if n_human < MIN_HUMAN_ROWS:
        reasons.append(
            f"Need ≥{MIN_HUMAN_ROWS} human-labelled rows (have {n_human}). "
            f"Grow {HAND_LABELS.name}."
        )
    if new_labels < MIN_NEW_SINCE_PROMOTE:
        reasons.append(
            f"Need ≥{MIN_NEW_SINCE_PROMOTE} new human labels since last promote "
            f"(have {new_labels}; active baseline={baseline})."
        )
    if ready:
        reasons.append(
            "Gates passed — you may run: python -m pipeline.recalibrate --train"
        )

    out = {
        "retrain_recommended": ready,
        "n_human_labels": n_human,
        "n_new_since_promote": new_labels,
        "active_model_id": reg.get("active_model_id"),
        "policy": reg.get("policy"),
        "gates": {
            "min_human_rows": MIN_HUMAN_ROWS,
            "min_new_since_promote": MIN_NEW_SINCE_PROMOTE,
            "min_macro_f1_to_promote": MIN_MACRO_F1,
        },
        "last_finetune_metrics": last_metrics,
        "advice": reasons,
        "do_not": [
            "Do not retrain on every IR PDF drop-in",
            "Do not use silver labels alone as promotion evidence",
            "Do not overwrite the active model without --promote",
        ],
    }
    record_run(
        "recalibrate_check",
        {
            "retrain_recommended": ready,
            "n_human_labels": n_human,
            "n_new_since_promote": new_labels,
        },
    )
    return out


def train() -> dict:
    """Run Pipeline light domain FT offline. Does not auto-promote."""
    status = check_recalibration()
    if not status["retrain_recommended"]:
        raise SystemExit(
            "Recalibration gates not met.\n" + json.dumps(status, indent=2)
        )

    script = PIPELINE_SCRIPTS / "finetune_sentiment.py"
    if not script.exists():
        raise FileNotFoundError(script)

    print(f"→ training via {script} (heavy; uses Pipeline .venv)")
    proc = subprocess.run(
        [str(_python()), str(script)],
        cwd=str(PIPELINE_ROOT),
        env={**os.environ, "PYTHONPATH": str(PIPELINE_ROOT)},
    )
    if proc.returncode != 0:
        raise SystemExit(f"finetune_sentiment.py failed ({proc.returncode})")

    metrics_path = PIPELINE_PROCESSED / "finetune_metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    model_id = "finbert-ft-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    entry = register_model(
        model_id=model_id,
        source=str(PIPELINE_MODELS),
        metrics=metrics.get("finetuned") or metrics,
        n_human_labels=count_human_labels(),
        promote=False,
        notes="Candidate only — run with --promote after reviewing metrics",
    )
    record_run("recalibrate_train", {"model_id": model_id})
    return {
        "candidate": entry,
        "metrics": metrics,
        "next": f"python -m pipeline.recalibrate --promote {model_id}",
    }


def promote(model_id: str) -> dict:
    reg = load_registry()
    match = next(
        (m for m in reg.get("models") or [] if m.get("model_id") == model_id),
        None,
    )
    if not match:
        raise SystemExit(f"Unknown model_id: {model_id}")

    ft = match.get("metrics") or {}
    macro = ft.get("macro_f1")
    if macro is None and isinstance(ft.get("finetuned"), dict):
        macro = ft["finetuned"].get("macro_f1")
    if macro is not None and float(macro) < MIN_MACRO_F1:
        raise SystemExit(
            f"Refuse promote: macro_f1={macro} < {MIN_MACRO_F1}. "
            "Keep previous active model."
        )

    for m in reg["models"]:
        m["promoted"] = m.get("model_id") == model_id
    reg["active_model_id"] = model_id
    save_registry(reg)
    record_run("recalibrate_promote", {"model_id": model_id, "macro_f1": macro})
    return {"active_model_id": model_id, "macro_f1": macro}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true", help="Show whether retrain is warranted"
    )
    ap.add_argument(
        "--train", action="store_true", help="Run gated light FT (candidate)"
    )
    ap.add_argument("--promote", metavar="MODEL_ID", help="Promote a candidate model")
    args = ap.parse_args()

    if args.promote:
        print(json.dumps(promote(args.promote), indent=2))
    elif args.train:
        print(json.dumps(train(), indent=2))
    else:
        print(json.dumps(check_recalibration(), indent=2))


if __name__ == "__main__":
    main()
