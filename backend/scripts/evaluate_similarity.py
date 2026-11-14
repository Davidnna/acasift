"""Run a small labelled evaluation corpus against AcaSift's exact N-gram matcher."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.similarity_service import find_ngram_matches, find_fuzzy_matches  # noqa: E402


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def evaluate(dataset_path, ngram_size):
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    cases = dataset.get("cases", [])
    if not cases:
        raise ValueError("The evaluation dataset contains no cases.")

    tp = fp = tn = fn = 0
    fuzzy_tp = fuzzy_fp = fuzzy_tn = fuzzy_fn = 0
    localized = 0
    positive_cases = 0
    fuzzy_positive_cases = 0
    fuzzy_localized = 0
    details = []

    for case in cases:
        result = find_ngram_matches(
            case["submitted_text"],
            case["reference_text"],
            n=ngram_size,
        )
        expected = bool(case["expected_overlap"])
        # Exact overlap and near-identical sentence matching are evaluated separately.
        predicted = result["matched_count"] > 0
        fuzzy_result = find_fuzzy_matches(case["submitted_text"], case["reference_text"])
        fuzzy_labelled = "expected_fuzzy" in case
        expected_fuzzy = bool(case.get("expected_fuzzy", False))
        predicted_fuzzy = bool(fuzzy_result["passages"])

        if fuzzy_labelled:
            if expected_fuzzy and predicted_fuzzy:
                fuzzy_tp += 1
            elif expected_fuzzy and not predicted_fuzzy:
                fuzzy_fn += 1
            elif not expected_fuzzy and predicted_fuzzy:
                fuzzy_fp += 1
            else:
                fuzzy_tn += 1

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

        if fuzzy_labelled and expected_fuzzy:
            fuzzy_positive_cases += 1
            expected_fuzzy_passage = case.get("expected_fuzzy_passage", "")
            fuzzy_found = any(
                expected_fuzzy_passage.casefold() in passage["matched_text"].casefold()
                for passage in fuzzy_result["passages"]
            ) if expected_fuzzy_passage else bool(fuzzy_result["passages"])
            fuzzy_localized += int(fuzzy_found)
        elif fuzzy_labelled:
            fuzzy_found = False
        else:
            fuzzy_found = None

        details.append({
            "id": case["id"],
            "expected_overlap": expected,
            "detected_overlap": predicted,
            "expected_fuzzy": expected_fuzzy if fuzzy_labelled else None,
            "detected_fuzzy": predicted_fuzzy if fuzzy_labelled else None,
            "fuzzy_coverage_percent": fuzzy_result["coverage"],
            "fuzzy_passage_localized": fuzzy_found,
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
        "fuzzy_metrics": {
            "labelled_case_count": fuzzy_tp + fuzzy_fp + fuzzy_tn + fuzzy_fn,
            "confusion_matrix": {
                "true_positive": fuzzy_tp,
                "false_positive": fuzzy_fp,
                "true_negative": fuzzy_tn,
                "false_negative": fuzzy_fn,
            },
            "precision": round(safe_ratio(fuzzy_tp, fuzzy_tp + fuzzy_fp), 4),
            "recall": round(safe_ratio(fuzzy_tp, fuzzy_tp + fuzzy_fn), 4),
            "f1_score": round(
                safe_ratio(
                    2 * safe_ratio(fuzzy_tp, fuzzy_tp + fuzzy_fp) * safe_ratio(fuzzy_tp, fuzzy_tp + fuzzy_fn),
                    safe_ratio(fuzzy_tp, fuzzy_tp + fuzzy_fp) + safe_ratio(fuzzy_tp, fuzzy_tp + fuzzy_fn),
                ), 4
            ),
            "positive_passage_localization_rate": round(safe_ratio(fuzzy_localized, fuzzy_positive_cases), 4),
        },
        "cases": details,
        "interpretation": (
            "These metrics describe performance on a small synthetic software-check corpus only. "
            "Exact overlap and fuzzy near-copy matching are separate tasks. They are not estimates "
            "of real-world plagiarism-detection accuracy."
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
