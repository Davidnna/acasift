# AcaSift detection evaluation guide (0.4.0)

## Purpose

This release adds a controlled evaluation harness for the exact word N-gram matcher. It is
intended to verify expected software behaviour and provide a reproducible starting point for
the final-year project's evaluation chapter.

## Included corpus

`evaluation/cases.json` contains 12 original synthetic submitted/reference document pairs:

- Six positive exact-overlap cases: full and partial overlap, case/punctuation differences,
  separated matching passages, repeated source phrases and Unicode compatibility characters.
- Six negative cases: unrelated topics, paraphrase-only wording, reordered terms, shared academic
  vocabulary, short generic phrases and distinct content.

The corpus is deliberately small and synthetic. It is not representative of actual student
submissions, and its results must not be presented as real-world accuracy estimates.

## Run the evaluation

From the project root, with the project dependencies installed:

```powershell
python scripts/evaluate_similarity.py --ngram-size 5
```

To save a machine-readable result:

```powershell
python scripts/evaluate_similarity.py --ngram-size 5 --output evaluation/results.json
```

## Metrics

- **Precision:** TP / (TP + FP). Of the pairs flagged as containing exact overlap, the proportion
  labelled positive in the test corpus.
- **Recall:** TP / (TP + FN). Of the positive pairs in the corpus, the proportion detected.
- **F1-score:** harmonic mean of precision and recall.
- **Accuracy:** (TP + TN) / all evaluated pairs.
- **Positive-passage localisation rate:** positive cases for which the expected copied excerpt
  appears inside at least one identified passage, divided by all positive cases.

The script's binary evaluation rule is `matched_ngram_count > 0`. This is a test harness rule for
exact phrase overlap, not a production decision threshold and not a plagiarism verdict.

## Recommended empirical evaluation for the final-year project

For a defensible evaluation, develop a larger corpus with permission and manual labels. Include
multiple document lengths, disciplines, citation styles, quoted passages, common technical
phrases, partial copying, rearranged paragraphs, paraphrases, and unrelated documents. Have at
least two reviewers independently label copied/overlapping passages and resolve disagreements.
Keep training/configuration selection separate from the final test set. Report precision, recall,
F1-score, false-positive rate, passage-localisation performance and processing time. Describe
corpus size, sampling method, document formats, language and limitations.

Do not describe cosine similarity as a percentage of plagiarism. It is a document-vector
similarity measure. Exact N-gram matching identifies shared word sequences and does not by itself
prove academic misconduct.

## Historical report compatibility

AcaSift 0.4.0 stores `coverage_method` on each new source-level comparison result. The startup
`init-db` command adds this column if it is missing and assigns the `unique_ngrams` label to existing
rows. The frontend therefore labels older stored coverage as unique-N-gram coverage and new results
as occurrence-based coverage. This additive migration does not delete or recalculate historical results.
