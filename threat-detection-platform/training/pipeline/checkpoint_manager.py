"""
Model Checkpoint Manager

Manages trained model checkpoints:
- List available experiments and their metrics
- Compare models across experiments
- Export best model for deployment
- Clean up old/failed runs

Usage:
    python -m pipeline.checkpoint_manager list
    python -m pipeline.checkpoint_manager best --metric mAP50
    python -m pipeline.checkpoint_manager export --run runs/experiment_name --output ../detection/models/
    python -m pipeline.checkpoint_manager clean --keep-best 3
"""

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class ExperimentInfo:
    """Information about a training experiment."""

    name: str
    path: Path
    config_path: Optional[Path]
    best_weights: Optional[Path]
    last_weights: Optional[Path]
    results_csv: Optional[Path]
    metrics: Dict

    @property
    def has_weights(self) -> bool:
        return self.best_weights is not None and self.best_weights.exists()


def list_experiments(runs_dir: str = "runs") -> List[ExperimentInfo]:
    """
    Scan runs directory and list all training experiments.

    Args:
        runs_dir: Path to the runs directory.

    Returns:
        List of ExperimentInfo for each found experiment.
    """
    runs_path = Path(runs_dir)
    if not runs_path.exists():
        return []

    experiments = []

    for exp_dir in sorted(runs_path.iterdir()):
        if not exp_dir.is_dir():
            continue

        # Look for training artifacts
        weights_dir = exp_dir / "weights"
        best_pt = weights_dir / "best.pt" if weights_dir.exists() else None
        last_pt = weights_dir / "last.pt" if weights_dir.exists() else None

        if best_pt and not best_pt.exists():
            best_pt = None
        if last_pt and not last_pt.exists():
            last_pt = None

        # Look for config
        config_path = exp_dir / "train_config.yaml"
        if not config_path.exists():
            config_path = None

        # Look for results
        results_csv = exp_dir / "results.csv"
        if not results_csv.exists():
            results_csv = None

        # Try to read metrics from results
        metrics = _read_best_metrics(exp_dir)

        experiments.append(ExperimentInfo(
            name=exp_dir.name,
            path=exp_dir,
            config_path=config_path,
            best_weights=best_pt,
            last_weights=last_pt,
            results_csv=results_csv,
            metrics=metrics,
        ))

    return experiments


def _read_best_metrics(exp_dir: Path) -> Dict:
    """Attempt to read the best metrics from an experiment directory."""
    metrics = {}

    # Try to read from results.csv (Ultralytics format)
    results_csv = exp_dir / "results.csv"
    if results_csv.exists():
        try:
            import pandas as pd
            df = pd.read_csv(results_csv, skipinitialspace=True)
            # Get last row (best epoch metrics are in the best.pt, but last row is latest)
            if len(df) > 0:
                last = df.iloc[-1]
                # Column names vary by ultralytics version, try common ones
                for col in df.columns:
                    col_clean = col.strip()
                    if "map50" in col_clean.lower() and "95" not in col_clean.lower():
                        metrics["mAP50"] = float(last[col])
                    elif "map50-95" in col_clean.lower() or "map" == col_clean.lower().strip("metrics/"):
                        metrics["mAP50_95"] = float(last[col])
                    elif "precision" in col_clean.lower():
                        metrics["precision"] = float(last[col])
                    elif "recall" in col_clean.lower():
                        metrics["recall"] = float(last[col])
        except Exception:
            pass

    # Try to read from eval JSON
    eval_dir = exp_dir / "evaluation"
    if eval_dir.exists():
        for json_file in sorted(eval_dir.glob("eval_results_*.json")):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                if "summary" in data:
                    metrics.update(data["summary"])
                break  # Use most recent
            except Exception:
                pass

    return metrics


def get_best_experiment(
    runs_dir: str = "runs",
    metric: str = "mAP50",
) -> Optional[ExperimentInfo]:
    """
    Find the experiment with the best value for a given metric.

    Args:
        runs_dir: Path to runs directory.
        metric: Metric name to compare (mAP50, mAP50_95, precision, recall, f1).

    Returns:
        ExperimentInfo for the best experiment, or None.
    """
    experiments = list_experiments(runs_dir)
    experiments_with_metric = [
        exp for exp in experiments
        if metric in exp.metrics and exp.has_weights
    ]

    if not experiments_with_metric:
        return None

    return max(experiments_with_metric, key=lambda e: e.metrics[metric])


def export_model(
    experiment_path: Path,
    output_dir: Path,
    model_name: str = "weapon_detector.pt",
) -> Path:
    """
    Export the best weights from an experiment to a deployment location.

    Args:
        experiment_path: Path to the experiment directory.
        output_dir: Destination directory.
        model_name: Filename for the exported model.

    Returns:
        Path to the exported model file.
    """
    best_weights = experiment_path / "weights" / "best.pt"
    if not best_weights.exists():
        raise FileNotFoundError(f"best.pt not found in {experiment_path / 'weights'}")

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / model_name
    shutil.copy2(best_weights, dest)

    # Also copy the config for reference
    config_src = experiment_path / "train_config.yaml"
    if config_src.exists():
        shutil.copy2(config_src, output_dir / f"{model_name.replace('.pt', '_config.yaml')}")

    return dest


def clean_runs(
    runs_dir: str = "runs",
    keep_best: int = 3,
    metric: str = "mAP50",
    dry_run: bool = True,
) -> List[str]:
    """
    Remove old experiments, keeping only the top N by metric.

    Args:
        runs_dir: Path to runs directory.
        keep_best: Number of best experiments to keep.
        metric: Metric to rank by.
        dry_run: If True, only report what would be deleted.

    Returns:
        List of removed (or would-be-removed) directory names.
    """
    experiments = list_experiments(runs_dir)

    # Sort by metric (best first), put those without metrics at the end
    def sort_key(exp):
        return exp.metrics.get(metric, -1)

    sorted_exps = sorted(experiments, key=sort_key, reverse=True)

    to_keep = sorted_exps[:keep_best]
    to_remove = sorted_exps[keep_best:]

    removed = []
    for exp in to_remove:
        if dry_run:
            print(f"  [DRY RUN] Would remove: {exp.name}")
        else:
            shutil.rmtree(exp.path)
            print(f"  Removed: {exp.name}")
        removed.append(exp.name)

    return removed


def print_experiments_table(experiments: List[ExperimentInfo]) -> None:
    """Print a formatted table of experiments."""
    try:
        from tabulate import tabulate
    except ImportError:
        for exp in experiments:
            print(f"  {exp.name}: {exp.metrics}")
        return

    table = []
    for exp in experiments:
        has_model = "✅" if exp.has_weights else "❌"
        map50 = f"{exp.metrics['mAP50']:.4f}" if "mAP50" in exp.metrics else "—"
        prec = f"{exp.metrics['precision']:.4f}" if "precision" in exp.metrics else "—"
        recall = f"{exp.metrics['recall']:.4f}" if "recall" in exp.metrics else "—"

        table.append([exp.name, has_model, map50, prec, recall])

    print("\n" + tabulate(
        table,
        headers=["Experiment", "Model", "mAP@0.5", "Precision", "Recall"],
        tablefmt="grid",
    ))


def main():
    parser = argparse.ArgumentParser(description="Model checkpoint manager")
    subparsers = parser.add_subparsers(dest="command")

    # List
    list_parser = subparsers.add_parser("list", help="List all experiments")
    list_parser.add_argument("--runs-dir", default="runs")

    # Best
    best_parser = subparsers.add_parser("best", help="Find best experiment")
    best_parser.add_argument("--metric", default="mAP50")
    best_parser.add_argument("--runs-dir", default="runs")

    # Export
    export_parser = subparsers.add_parser("export", help="Export model for deployment")
    export_parser.add_argument("--run", required=True, help="Experiment directory")
    export_parser.add_argument("--output", required=True, help="Output directory")
    export_parser.add_argument("--name", default="weapon_detector.pt")

    # Clean
    clean_parser = subparsers.add_parser("clean", help="Remove old experiments")
    clean_parser.add_argument("--keep-best", type=int, default=3)
    clean_parser.add_argument("--metric", default="mAP50")
    clean_parser.add_argument("--runs-dir", default="runs")
    clean_parser.add_argument("--confirm", action="store_true", help="Actually delete")

    args = parser.parse_args()

    if args.command == "list":
        experiments = list_experiments(args.runs_dir)
        if experiments:
            print_experiments_table(experiments)
        else:
            print(f"No experiments found in '{args.runs_dir}/'")

    elif args.command == "best":
        best = get_best_experiment(args.runs_dir, args.metric)
        if best:
            print(f"\nBest experiment by {args.metric}:")
            print(f"  Name:   {best.name}")
            print(f"  Value:  {best.metrics.get(args.metric, 'N/A')}")
            print(f"  Weights: {best.best_weights}")
        else:
            print(f"No experiments with metric '{args.metric}' found")

    elif args.command == "export":
        exp_path = Path(args.run)
        output_path = Path(args.output)
        dest = export_model(exp_path, output_path, args.name)
        print(f"\nModel exported to: {dest}")

    elif args.command == "clean":
        removed = clean_runs(
            args.runs_dir, args.keep_best, args.metric,
            dry_run=not args.confirm
        )
        if not args.confirm and removed:
            print(f"\n  Run with --confirm to actually delete {len(removed)} experiments")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
