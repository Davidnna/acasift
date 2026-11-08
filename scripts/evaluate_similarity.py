"""Run a small labelled evaluation corpus against AcaSift's exact N-gram matcher."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.similarity_service import find_ngram_matches  # noqa: E402


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def evaluate(dataset_path, ngram_size):
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    cases = dataset.get("cases", [])
    if not cases:
        raise ValueError("The evaluation dataset contains no cases.")

    tp = fp = tn = fn = 0
    localized = 0
    positive_cases = 0
    details = []

    for case in cases:
        result = find_ngram_matches(
            case["submitted_text"],
            case["reference_text"],
            n=ngram_size,
        )
        expected = bool(case["expected_overlap"])
        # This is an evaluation rule for exact overlap only, not a plagiarism verdict.
        predicted = result["matched_count"] > 0

        if expected and predicted:
            tp += 1
        elif expected and not predicted:
            fn += 1
        elif not expected and predicted:
            fp += 1
        else:
            tn += 1

        passage_expected = case.get("expected_passage", "")
        passage_found = False
        if expected:
            positive_cases += 1
            passage_found = any(
                passage_expected.casefold() in passage["matched_text"].casefold()
                for passage in result["passages"]
            ) if passage_expected else bool(result["passages"])
            localized += int(passage_found)

        details.append({
            "id": case["id"],
            "expected_overlap": expected,
            "detected_overlap": predicted,
            "matched_ngram_windows": result["matched_count"],
            "total_ngram_windows": result["total_count"],
            "coverage_percent": result["coverage"],
            "passage_localized": passage_found if expected else None,
        })

    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    f1 = safe_ratio(2 * precision * recall, precision + recall)
    accuracy = safe_ratio(tp + tn, tp + tn + fp + fn)
    localization_rate = safe_ratio(localized, positive_cases)

    return {
        "dataset": dataset.get("dataset_name", Path(dataset_path).name),
        "ngram_size": ngram_size,
        "case_count": len(cases),
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "positive_passage_localization_rate": round(localization_rate, 4),
        },
        "cases": details,
        "interpretation": (
            "These metrics describe performance on this small synthetic exact-overlap corpus only. "
            "They are not estimates of real-world plagiarism detection accuracy."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=str(PROJECT_ROOT / "evaluation" / "cases.json"),
        help="Path to a labelled JSON evaluation dataset.",
    )
    parser.add_argument("--ngram-size", type=int, default=5)
    parser.add_argument("--output", help="Optional path to write the JSON results.")
    args = parser.parse_args()

    results = evaluate(args.dataset, args.ngram_size)
    rendered = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
