"""Unit tests for Phase 10 empirical evaluation runner."""

from pathlib import Path

from scripts.run_evaluation import evaluate_single_seed, run_benchmark


def test_evaluate_single_seed():
    """Verify that a single seed evaluation produces valid metrics across all 7 detectors."""
    res = evaluate_single_seed(
        seed=42,
        n_cases=50,
        anomaly_rate=0.20,
        split_name="test",
        target_fpr=0.05,
        ml_policy="any",
    )

    assert res["seed"] == 42
    assert res["n_cases"] > 0
    assert 0.0 <= res["base_rate"] <= 1.0

    models = res["models"]
    expected_detectors = [
        "FSM-only",
        "ML-only",
        "Hybrid",
        "IF alone",
        "Markov alone",
        "K-Means alone",
        "RF reference",
    ]
    for det in expected_detectors:
        assert det in models
        m = models[det]
        assert "tp" in m and "fp" in m and "tn" in m and "fn" in m
        assert 0.0 <= m["precision"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0
        assert 0.0 <= m["f1"] <= 1.0
        assert m["latency_median_ms"] >= 0.0

    # Formal FSM must have 0 false positives on valid variations
    assert models["FSM-only"]["fpr_valid_variation"] == 0.0


def test_run_benchmark_artifacts(tmp_path: Path):
    """Verify that run_benchmark generates all required CSV and JSON report artifacts."""
    out_dir = tmp_path / "eval_out"
    run_benchmark(
        seeds=[0],
        n_cases=40,
        anomaly_rate=0.20,
        split_name="test",
        target_fpr=0.05,
        ml_policy="any",
        out_dir_path=str(out_dir),
        save_db=False,
    )

    assert (out_dir / "table_r1_main_comparison.csv").exists()
    assert (out_dir / "table_r2_confusion_matrices.csv").exists()
    assert (out_dir / "table_r3_type_breakdown.csv").exists()
    assert (out_dir / "evaluation_report.json").exists()

    # Check non-empty files
    assert (out_dir / "table_r1_main_comparison.csv").stat().st_size > 0
    assert (out_dir / "table_r2_confusion_matrices.csv").stat().st_size > 0
    assert (out_dir / "table_r3_type_breakdown.csv").stat().st_size > 0
    assert (out_dir / "evaluation_report.json").stat().st_size > 0
