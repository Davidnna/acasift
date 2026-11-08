import re
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TOKEN_PATTERN = re.compile(r"\b[\w]+(?:['’][\w]+)?\b", re.UNICODE)


def token_spans(text):
    """Return case-folded tokens with their original character offsets."""
    return [
        (match.group(0).casefold(), match.start(), match.end())
        for match in TOKEN_PATTERN.finditer(text or "")
    ]


def find_ngram_matches(submitted_text, reference_text, n=5, max_passages=100):
    """Find exact word-sequence overlap and return coverage plus passage offsets."""
    query_tokens = token_spans(submitted_text)
    reference_tokens = token_spans(reference_text)

    if not query_tokens or not reference_tokens:
        return {"matched_count": 0, "total_count": 0, "coverage": 0.0, "passages": []}

    n = max(1, min(int(n), len(query_tokens), len(reference_tokens)))

    reference_index = defaultdict(list)
    for start in range(0, len(reference_tokens) - n + 1):
        gram = tuple(token[0] for token in reference_tokens[start:start + n])
        if len(reference_index[gram]) < 10:
            reference_index[gram].append(start)

    query_grams = set()
    matches = []
    for start in range(0, len(query_tokens) - n + 1):
        gram = tuple(token[0] for token in query_tokens[start:start + n])
        query_grams.add(gram)
        reference_positions = reference_index.get(gram)
        if reference_positions:
            reference_start = reference_positions[0]
            q_first, q_last = query_tokens[start], query_tokens[start + n - 1]
            r_first, r_last = reference_tokens[reference_start], reference_tokens[reference_start + n - 1]
            matches.append({
                "q_start_token": start,
                "q_end_token": start + n - 1,
                "q_start": q_first[1],
                "q_end": q_last[2],
                "r_start": r_first[1],
                "r_end": r_last[2],
            })

    matched_grams = {
        tuple(token[0] for token in query_tokens[item["q_start_token"]:item["q_end_token"] + 1])
        for item in matches
    }
    total_count = len(query_grams)
    matched_count = len(matched_grams)
    coverage = (matched_count / total_count * 100.0) if total_count else 0.0

    matches.sort(key=lambda item: (item["q_start"], item["r_start"]))
    merged = []
    for item in matches:
        if merged:
            last = merged[-1]
            same_alignment = (item["q_start"] - item["r_start"]) == (
                last["submitted_start"] - last["reference_start"]
            )
            overlaps_query = item["q_start"] <= last["submitted_end"]
            overlaps_reference = item["r_start"] <= last["reference_end"]
            if same_alignment and overlaps_query and overlaps_reference:
                last["submitted_end"] = max(last["submitted_end"], item["q_end"])
                last["reference_end"] = max(last["reference_end"], item["r_end"])
                last["matched_text"] = submitted_text[last["submitted_start"]:last["submitted_end"]]
                continue

        merged.append({
            "submitted_start": item["q_start"],
            "submitted_end": item["q_end"],
            "reference_start": item["r_start"],
            "reference_end": item["r_end"],
            "matched_text": submitted_text[item["q_start"]:item["q_end"]],
        })

    return {
        "matched_count": matched_count,
        "total_count": total_count,
        "coverage": round(coverage, 4),
        "passages": merged[:max_passages],
    }


def compare_against_repository(submitted_text, reference_documents, ngram_size=5):
    """Compare a submission against document objects in the internal repository."""
    if not reference_documents:
        return []

    texts = [submitted_text] + [doc.extracted_text or "" for doc in reference_documents]
    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=100000,
        )
        matrix = vectorizer.fit_transform(texts)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except ValueError:
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
            "passages": ngram_result["passages"],
        })

    results.sort(
        key=lambda item: (item["cosine_similarity"], item["matched_ngram_coverage"]),
        reverse=True,
    )
    return results
