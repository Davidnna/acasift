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




# Optional near-duplicate and semantic analysis.
# RapidFuzz is a lightweight runtime dependency. Sentence-transformers is optional
# because loading a local embedding model has a material memory/startup cost.
from functools import lru_cache
from difflib import SequenceMatcher
import os


def _sentence_spans(text):
    """Return sentence-like spans with offsets into the original text."""
    output = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text or ""):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        leading = len(match.group(0)) - len(match.group(0).lstrip())
        start = match.start() + leading
        end = start + len(sentence)
        tokens = token_spans(sentence)
        if len(tokens) >= 8:
            output.append({
                "text": sentence,
                "start": start,
                "end": end,
                "tokens": tokens,
                "normalised": " ".join(token[0] for token in tokens),
                "word_count": len(tokens),
            })
    return output[:400]


def find_fuzzy_matches(
    submitted_text,
    reference_text,
    *,
    minimum_score=88.0,
    minimum_words=8,
    max_passages=20,
):
    """Find near-identical sentence passages using RapidFuzz.

    Exact matches are handled separately by N-gram matching. Fuzzy matching is
    intended to identify small edits, punctuation/wording changes and reordered
    terms; it is not a paraphrase detector.
    """
    query_sentences = _sentence_spans(submitted_text)
    reference_sentences = _sentence_spans(reference_text)
    if not query_sentences or not reference_sentences:
        return {
            "coverage": 0.0,
            "similarity": 0.0,
            "matched_words": 0,
            "passages": [],
        }

    try:
        from rapidfuzz import fuzz, process
        reference_values = [item["normalised"] for item in reference_sentences]
        scorer = fuzz.ratio
        use_rapidfuzz = True
    except ImportError:
        reference_values = [item["normalised"] for item in reference_sentences]
        use_rapidfuzz = False

    used_reference = set()
    passages = []
    matched_words = 0
    weighted_scores = []

    for query in query_sentences:
        if query["word_count"] < minimum_words:
            continue

        candidates = []
        if use_rapidfuzz:
            candidates = process.extract(
                query["normalised"],
                reference_values,
                scorer=scorer,
                limit=8,
                score_cutoff=minimum_score,
            )
            candidates = [
                (value, score, index)
                for value, score, index in candidates
                if index not in used_reference
            ]
        else:
            for index, value in enumerate(reference_values):
                if index in used_reference:
                    continue
                score = SequenceMatcher(None, query["normalised"], value).ratio() * 100
                if score >= minimum_score:
                    candidates.append((value, score, index))
            candidates.sort(key=lambda item: item[1], reverse=True)
            candidates = candidates[:8]

        if not candidates:
            continue

        _value, score, index = candidates[0]
        # Identical passages are already represented by exact N-gram evidence.
        if score >= 99.5:
            continue

        reference = reference_sentences[index]
        used_reference.add(index)
        matched_words += query["word_count"]
        weighted_scores.append((float(score), query["word_count"]))
        passages.append({
            "submitted_start": query["start"],
            "submitted_end": query["end"],
            "reference_start": reference["start"],
            "reference_end": reference["end"],
            "matched_text": query["text"],
            "reference_text": reference["text"],
            "match_method": "fuzzy_sentence",
            "match_score": round(float(score), 2),
        })
        if len(passages) >= max_passages:
            break

    total_words = max(1, len(token_spans(submitted_text)))
    coverage = min(100.0, matched_words / total_words * 100.0)
    denominator = sum(words for _score, words in weighted_scores)
    similarity = (
        sum(score * words for score, words in weighted_scores) / denominator
        if denominator else 0.0
    )
    return {
        "coverage": round(coverage, 4),
        "similarity": round(similarity, 4),
        "matched_words": matched_words,
        "passages": passages,
    }


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name, device='cpu')


def find_semantic_matches(
    submitted_text,
    reference_text,
    *,
    minimum_similarity=None,
    max_passages=20,
):
    """Find semantically similar sentence pairs using an optional local model.

    Set ENABLE_LOCAL_SEMANTIC=true and install requirements-semantic.txt to enable.
    If the model is unavailable, the method is explicitly marked unavailable;
    lexical TF-IDF is never mislabelled as semantic similarity.
    """
    enabled = os.getenv("ENABLE_LOCAL_SEMANTIC", "false").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return {
            "available": False,
            "status": "not_configured",
            "similarity": None,
            "coverage": None,
            "passages": [],
        }

    model_name = os.getenv("SEMANTIC_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    if minimum_similarity is None:
        try:
            minimum_similarity = float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.82"))
        except ValueError:
            minimum_similarity = 0.82
    try:
        model = _load_sentence_transformer(model_name)
        from sklearn.metrics.pairwise import cosine_similarity as pairwise_cosine

        query_sentences = _sentence_spans(submitted_text)
        reference_sentences = _sentence_spans(reference_text)
        if not query_sentences or not reference_sentences:
            return {
                "available": True, "status": "completed", "similarity": 0.0,
                "coverage": 0.0, "passages": [],
            }

        query_sentences = query_sentences[:200]
        reference_sentences = reference_sentences[:300]
        query_vectors = model.encode(
            [item["text"] for item in query_sentences],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        reference_vectors = model.encode(
            [item["text"] for item in reference_sentences],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        matrix = pairwise_cosine(query_vectors, reference_vectors)
        used_reference = set()
        passages = []
        matched_words = 0
        weighted_scores = []

        for query_index, query in enumerate(query_sentences):
            ranking = matrix[query_index].argsort()[::-1]
            best_index = None
            best_score = 0.0
            for candidate_index in ranking:
                candidate_index = int(candidate_index)
                if candidate_index in used_reference:
                    continue
                score = float(matrix[query_index, candidate_index])
                if score >= minimum_similarity:
                    best_index = candidate_index
                    best_score = score
                break
            if best_index is None:
                continue

            reference = reference_sentences[best_index]
            used_reference.add(best_index)
            matched_words += query["word_count"]
            weighted_scores.append((best_score * 100.0, query["word_count"]))
            passages.append({
                "submitted_start": query["start"],
                "submitted_end": query["end"],
                "reference_start": reference["start"],
                "reference_end": reference["end"],
                "matched_text": query["text"],
                "reference_text": reference["text"],
                "match_method": "semantic_sentence",
                "match_score": round(best_score * 100.0, 2),
            })
            if len(passages) >= max_passages:
                break

        total_words = max(1, len(token_spans(submitted_text)))
        coverage = min(100.0, matched_words / total_words * 100.0)
        denominator = sum(words for _score, words in weighted_scores)
        similarity = (
            sum(score * words for score, words in weighted_scores) / denominator
            if denominator else 0.0
        )
        return {
            "available": True,
            "status": "completed",
            "similarity": round(similarity, 4),
            "coverage": round(coverage, 4),
            "passages": passages,
        }
    except Exception as exc:
        return {
            "available": False,
            "status": "unavailable",
            "similarity": None,
            "coverage": None,
            "passages": [],
            "error": type(exc).__name__,
        }


def _tfidf_pair_similarity(submitted_text, reference_text):
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
        matrix = vectorizer.fit_transform([submitted_text or "", reference_text or ""])
        return round(float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0]) * 100.0, 4)
    except ValueError:
        return 0.0


def compare_text_pair(submitted_text, reference_text, ngram_size=5, cosine_override=None):
    """Run exact N-gram, fuzzy sentence, TF-IDF and optional semantic comparison."""
    exact = find_ngram_matches(submitted_text, reference_text, n=ngram_size)
    fuzzy = find_fuzzy_matches(submitted_text, reference_text)
    semantic = find_semantic_matches(submitted_text, reference_text)
    cosine = (
        round(float(cosine_override), 4)
        if cosine_override is not None
        else _tfidf_pair_similarity(submitted_text, reference_text)
    )

    exact_passages = []
    for passage in exact["passages"]:
        exact_passages.append({
            **passage,
            "reference_text": (reference_text or "")[
                passage["reference_start"]:passage["reference_end"]
            ],
            "match_method": "exact_ngram",
            "match_score": 100.0,
        })

    # Merge methods without repeating the same target passage. Exact evidence takes
    # precedence over fuzzy/semantic evidence when offsets substantially overlap.
    passages = list(exact_passages)
    exact_spans = [(p["submitted_start"], p["submitted_end"]) for p in exact_passages]
    for candidate in fuzzy["passages"] + semantic["passages"]:
        start, end = candidate["submitted_start"], candidate["submitted_end"]
        candidate_length = max(1, end - start)
        overlaps = [
            max(0, min(end, right) - max(start, left)) / candidate_length
            for left, right in exact_spans
        ]
        if overlaps and max(overlaps) >= 0.70:
            continue
        passages.append(candidate)

    passages.sort(key=lambda item: (
        item["submitted_start"],
        -(item["submitted_end"] - item["submitted_start"]),
        item["match_method"],
    ))

    if semantic["available"] and semantic["coverage"] is not None:
        composite = (
            0.40 * exact["coverage"]
            + 0.35 * fuzzy["coverage"]
            + 0.25 * semantic["coverage"]
        )
    else:
        composite = (
            0.40 * exact["coverage"] + 0.35 * fuzzy["coverage"]
        ) / 0.75

    return {
        "cosine_similarity": cosine,
        "matched_ngram_coverage": exact["coverage"],
        "matched_ngram_count": exact["matched_count"],
        "total_query_ngrams": exact["total_count"],
        "effective_ngram_size": exact["effective_ngram_size"],
        "fuzzy_similarity": fuzzy["similarity"],
        "fuzzy_coverage": fuzzy["coverage"],
        "semantic_similarity": semantic["similarity"],
        "semantic_coverage": semantic["coverage"],
        "semantic_status": semantic["status"],
        "composite_similarity": round(composite, 4),
        "passages": passages[:100],
    }


def compare_against_repository(submitted_text, reference_documents, ngram_size=5):
    """Compare a submission against every eligible peer document in the request."""
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
        scores = [0.0] * len(reference_documents)

    results = []
    for index, document in enumerate(reference_documents):
        analysis = compare_text_pair(
            submitted_text,
            document.extracted_text or "",
            ngram_size=ngram_size,
            cosine_override=float(scores[index]) * 100.0,
        )
        results.append({
            "reference_document": document,
            **analysis,
        })

    results.sort(
        key=lambda item: (
            item["composite_similarity"],
            item["cosine_similarity"],
            item["matched_ngram_coverage"],
        ),
        reverse=True,
    )
    return results
