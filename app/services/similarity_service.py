"""Document-level similarity and exact word N-gram overlap analysis."""

import re
import unicodedata
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TOKEN_PATTERN = re.compile(r"\b[\w]+(?:['’][\w]+)?\b", re.UNICODE)
MAX_REFERENCE_OCCURRENCES_PER_NGRAM = 50


def token_spans(text):
    """Return normalized tokens with offsets into the original, unmodified text.

    Unicode compatibility normalization and case-folding make matching tolerant
    of differences such as uppercase text and typographic ligatures. Character
    offsets always refer to the original input so the report can display exact
    source excerpts.
    """
    tokens = []
    for match in TOKEN_PATTERN.finditer(text or ""):
        normalized = unicodedata.normalize("NFKC", match.group(0)).casefold()
        if normalized:
            tokens.append((normalized, match.start(), match.end()))
    return tokens


def _empty_ngram_result(effective_ngram_size=0):
    return {
        "matched_count": 0,
        "total_count": 0,
        "coverage": 0.0,
        "effective_ngram_size": effective_ngram_size,
        "passages": [],
    }


def find_ngram_matches(
    submitted_text,
    reference_text,
    n=5,
    max_passages=100,
    max_reference_occurrences=MAX_REFERENCE_OCCURRENCES_PER_NGRAM,
):
    """Find exact normalized word-sequence overlap and locate matching passages.

    Coverage is occurrence-based:
        matched query N-gram windows / all query N-gram windows * 100.

    A minimum effective size of two tokens avoids treating a single common word
    as a meaningful phrase match. Shorter documents automatically use a smaller
    N-gram size, down to bigrams.
    """
    query_tokens = token_spans(submitted_text)
    reference_tokens = token_spans(reference_text)

    if len(query_tokens) < 2 or len(reference_tokens) < 2:
        return _empty_ngram_result()

    try:
        requested_n = int(n)
    except (TypeError, ValueError):
        requested_n = 5
    requested_n = max(2, requested_n)
    effective_n = min(requested_n, len(query_tokens), len(reference_tokens))
    if effective_n < 2:
        return _empty_ngram_result()

    try:
        occurrence_limit = max(1, int(max_reference_occurrences))
    except (TypeError, ValueError):
        occurrence_limit = MAX_REFERENCE_OCCURRENCES_PER_NGRAM

    reference_index = defaultdict(list)
    for start in range(len(reference_tokens) - effective_n + 1):
        gram = tuple(token[0] for token in reference_tokens[start:start + effective_n])
        positions = reference_index[gram]
        if len(positions) < occurrence_limit:
            positions.append(start)

    total_count = len(query_tokens) - effective_n + 1
    matched_count = 0
    # Token-index alignment is stable even when punctuation or whitespace differs.
    alignment_positions = defaultdict(set)

    for query_start in range(total_count):
        gram = tuple(token[0] for token in query_tokens[query_start:query_start + effective_n])
        reference_positions = reference_index.get(gram)
        if not reference_positions:
            continue

        matched_count += 1
        for reference_start in reference_positions:
            alignment = reference_start - query_start
            alignment_positions[alignment].add(query_start)

    coverage = (matched_count / total_count * 100.0) if total_count else 0.0

    passages = []
    for alignment, starts in alignment_positions.items():
        ordered_starts = sorted(starts)
        if not ordered_starts:
            continue

        run_start = ordered_starts[0]
        previous = ordered_starts[0]
        runs = []
        for current in ordered_starts[1:]:
            if current == previous + 1:
                previous = current
                continue
            runs.append((run_start, previous))
            run_start = current
            previous = current
        runs.append((run_start, previous))

        for first_query_start, last_query_start in runs:
            first_reference_start = first_query_start + alignment
            last_reference_start = last_query_start + alignment
            query_last_token = last_query_start + effective_n - 1
            reference_last_token = last_reference_start + effective_n - 1

            query_first = query_tokens[first_query_start]
            query_last = query_tokens[query_last_token]
            reference_first = reference_tokens[first_reference_start]
            reference_last = reference_tokens[reference_last_token]

            query_char_start, query_char_end = query_first[1], query_last[2]
            reference_char_start, reference_char_end = reference_first[1], reference_last[2]
            passages.append({
                "submitted_start": query_char_start,
                "submitted_end": query_char_end,
                "reference_start": reference_char_start,
                "reference_end": reference_char_end,
                "matched_text": (submitted_text or "")[query_char_start:query_char_end],
            })

    # Stable ordering makes reports deterministic. Exact duplicate alignments
    # can arise from repeated N-grams; remove them without hiding distinct sources.
    unique_passages = {}
    for passage in passages:
        key = (
            passage["submitted_start"],
            passage["submitted_end"],
            passage["reference_start"],
            passage["reference_end"],
        )
        unique_passages[key] = passage

    ordered_passages = sorted(
        unique_passages.values(),
        key=lambda item: (
            item["submitted_start"],
            -(item["submitted_end"] - item["submitted_start"]),
            item["reference_start"],
        ),
    )

    return {
        "matched_count": matched_count,
        "total_count": total_count,
        "coverage": round(coverage, 4),
        "effective_ngram_size": effective_n,
        "passages": ordered_passages[:max(0, int(max_passages))],
    }


def compare_against_repository(submitted_text, reference_documents, ngram_size=5):
    """Compare a submission against document objects in the internal repository."""
    if not reference_documents:
        return []

    texts = [submitted_text or ""] + [doc.extracted_text or "" for doc in reference_documents]
    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            stop_words="english",
            token_pattern=r"(?u)\b\w+\b",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=100000,
        )
        matrix = vectorizer.fit_transform(texts)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except ValueError:
        # Empty vocabulary (for example, stop-word-only text) is a valid zero-score case.
        scores = [0.0] * len(reference_documents)

    results = []
    for index, document in enumerate(reference_documents):
        ngram_result = find_ngram_matches(
            submitted_text,
            document.extracted_text or "",
            n=ngram_size,
        )
        results.append({
            "reference_document": document,
            "cosine_similarity": round(float(scores[index]) * 100.0, 4),
            "matched_ngram_coverage": ngram_result["coverage"],
            "matched_ngram_count": ngram_result["matched_count"],
            "total_query_ngrams": ngram_result["total_count"],
            "effective_ngram_size": ngram_result["effective_ngram_size"],
            "passages": ngram_result["passages"],
        })

    results.sort(
        key=lambda item: (item["cosine_similarity"], item["matched_ngram_coverage"]),
        reverse=True,
    )
    return results
