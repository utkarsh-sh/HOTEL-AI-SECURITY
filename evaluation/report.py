import json
from pathlib import Path

from evaluation.metrics import calculate_evaluation_metrics


def generate_evaluation_report(
    artifact_path,
    report_path,
):
    """
    Load an evaluation artifact, calculate reproducible metrics,
    and save a JSON evaluation report.

    Classification metrics remain unavailable unless independent
    ground truth is supplied.
    """

    artifact_path = Path(artifact_path)
    report_path = Path(report_path)

    if not artifact_path.exists():
        raise ValueError(
            f"Evaluation artifact not found: {artifact_path}"
        )

    try:
        with artifact_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            artifact = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Unable to load evaluation artifact: {artifact_path}"
        ) from exc

    metrics = calculate_evaluation_metrics(artifact)

    report = {
        "report_type": "evaluation",
        "evaluation_version": "1.0",
        "ground_truth_available": False,
        "ground_truth_note": (
            "Independent ground truth is required for "
            "precision, recall, F1, false-positive, "
            "and false-negative classification metrics."
        ),
        **metrics,
    }

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    return report
