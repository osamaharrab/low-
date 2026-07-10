from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import numpy as np

from api.generator import INSUFFICIENT_ANSWER, GeneratorError, clean_llm_output, generate_answer
from api.models import Citation, RAGResponse, RetrievedChunk
from api.settings import Settings


DISCLAIMER = "هذا شرح أولي مبني على المصادر المسترجعة ولا يُعد استشارة قانونية ولا يغني عن مراجعة محامٍ مختص أو النص القانوني الرسمي."

SYSTEM_PROMPT = """أنت مساعد معلوماتي لمشروع Lawz AI JO.
مهمتك شرح النصوص القانونية الأردنية المسترجعة بلغة عربية بسيطة.
لا تقدم استشارة قانونية نهائية.
لا تخترع مواد أو مراجع غير موجودة.
اعتمد فقط على النصوص القانونية المسترجعة.
إذا لم تكف النصوص، قل بوضوح: لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.
لا تعرض خطوات التفكير.
لا تكتب <think>.
أجب مباشرة وباختصار وبمسافات عربية واضحة."""

ARABIC_VARIANTS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }
)
DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")
WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", flags=re.UNICODE)
STOPWORDS = {
    "في",
    "من",
    "على",
    "عن",
    "الى",
    "إلى",
    "هل",
    "ما",
    "هو",
    "هي",
    "او",
    "أو",
    "لا",
    "اذا",
    "إذا",
    "ذلك",
    "هذا",
    "هذه",
}

INSUFFICIENT_PHRASES = (
    "لا تكفي قاعدة المعرفة",
    "لا توجد معلومات كافية",
    "السياق غير كاف",
    "لا أستطيع الإجابة بثقة",
)


def normalize_arabic_text(text: str) -> str:
    text = (text or "").strip().translate(ARABIC_VARIANTS)
    text = DIACRITICS_RE.sub("", text)
    return WHITESPACE_RE.sub(" ", text)


def tokenize_for_overlap(text: str) -> set[str]:
    normalized = normalize_arabic_text(text)
    return {token for token in TOKEN_RE.findall(normalized) if len(token) > 1 and token not in STOPWORDS}


def uses_e5_prefix(model_name: str) -> bool:
    return "e5" in (model_name or "").lower()


def format_query_for_embedding(question: str, model_name: str) -> str:
    question = question.strip()
    if uses_e5_prefix(model_name) and not question.lower().startswith("query:"):
        return f"query: {question}"
    return question


def format_passage_for_embedding(text: str, model_name: str) -> str:
    text = text.strip()
    if uses_e5_prefix(model_name) and not text.lower().startswith("passage:"):
        return f"passage: {text}"
    return text


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def encode_texts(texts: list[str], model_name: str) -> list[list[float]]:
    model = get_embedding_model(model_name)
    try:
        vectors = model.encode(texts, normalize_embeddings=True)
    except TypeError:
        vectors = model.encode(texts)
        vectors = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.maximum(norms, 1e-12)

    return np.asarray(vectors, dtype=np.float32).tolist()


def embed_question(question: str, settings: Settings) -> list[float]:
    text = format_query_for_embedding(question, settings.embedding_model)
    return encode_texts([text], settings.embedding_model)[0]


def retrieve_chunks(
    question: str,
    question_vector: list[float],
    k: int,
    settings: Settings,
) -> list[dict[str, Any]]:
    import weaviate

    client = weaviate.Client(url=settings.weaviate_url)
    properties = [
        "chunk_id",
        "source_name",
        "reference",
        "topic",
        "text",
        "source_page",
        "source_type",
        "jurisdiction",
    ]

    # Retrieve more candidates than the number ultimately returned.
    # Reranking cannot recover a relevant chunk that was never retrieved.
    candidate_limit = max(30, k * 6)

    vector_result = (
        client.query.get(settings.weaviate_class, properties)
        .with_near_vector({"vector": question_vector})
        .with_limit(candidate_limit)
        .with_additional(["distance"])
        .do()
    )

    keyword_result = (
        client.query.get(settings.weaviate_class, properties)
        .with_bm25(
            query=question,
            properties=["topic", "reference", "source_name", "text"],
        )
        .with_limit(candidate_limit)
        .do()
    )

    vector_rows = (
        vector_result.get("data", {})
        .get("Get", {})
        .get(settings.weaviate_class, [])
        or []
    )
    keyword_rows = (
        keyword_result.get("data", {})
        .get("Get", {})
        .get(settings.weaviate_class, [])
        or []
    )

    candidates: dict[str, dict[str, Any]] = {}

    def get_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
        chunk_id = str(row.get("chunk_id") or "").strip()
        if not chunk_id:
            return None

        candidate = candidates.get(chunk_id)
        if candidate is None:
            candidate = {key: row.get(key) for key in properties}
            candidate["vector_score"] = 0.0
            candidate["vector_rank"] = None
            candidate["keyword_rank"] = None
            candidates[chunk_id] = candidate

        return candidate

    for rank, row in enumerate(vector_rows, start=1):
        candidate = get_candidate(row)
        if candidate is None:
            continue

        additional = row.get("_additional") or {}
        distance = additional.get("distance")

        try:
            vector_score = (
                max(0.0, min(1.0, 1.0 - float(distance)))
                if distance is not None
                else 0.0
            )
        except (TypeError, ValueError):
            vector_score = 0.0

        candidate["vector_score"] = vector_score
        candidate["vector_rank"] = rank

    for rank, row in enumerate(keyword_rows, start=1):
        candidate = get_candidate(row)
        if candidate is None:
            continue

        candidate["keyword_rank"] = rank

    # Reciprocal Rank Fusion combines vector and keyword rankings without
    # depending on incomparable raw BM25 and vector score scales.
    rrf_constant = 60

    for candidate in candidates.values():
        rrf_score = 0.0

        vector_rank = candidate.get("vector_rank")
        if vector_rank is not None:
            rrf_score += 1.0 / (rrf_constant + int(vector_rank))

        keyword_rank = candidate.get("keyword_rank")
        if keyword_rank is not None:
            rrf_score += 1.0 / (rrf_constant + int(keyword_rank))

        candidate["rrf_score"] = rrf_score

    return list(candidates.values())


def normalize_rerank_token(token: str) -> str:
    """Apply light Arabic normalization for retrieval ranking only."""
    token = normalize_arabic_text(token)

    if token.startswith("ال") and len(token) > 4:
        token = token[2:]

    # Light stemming for common plurals and possessive suffixes.
    # Examples:
    # التعريفات -> تعريف
    # أشكاله -> اشكال
    for suffix in (
        "اته",
        "اتها",
        "هما",
        "هم",
        "هن",
        "ها",
        "ات",
        "ون",
        "ين",
        "ان",
        "ه",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[:-len(suffix)]
            break

    return token


def tokenize_for_rerank(text: str) -> set[str]:
    normalized = normalize_arabic_text(text)
    tokens: set[str] = set()

    for token in TOKEN_RE.findall(normalized):
        if len(token) <= 1 or token in STOPWORDS:
            continue

        normalized_token = normalize_rerank_token(token)
        if len(normalized_token) > 1:
            tokens.add(normalized_token)

    return tokens


def rerank_chunks(
    question: str,
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    question_normalized = normalize_arabic_text(question)
    question_tokens = tokenize_for_rerank(question)

    definition_intent = any(
        phrase in question_normalized
        for phrase in (
            "ما المقصود",
            "ما معنى",
            "ما تعريف",
            "تعريف",
            "ماذا يعني",
        )
    )

    asks_for_forms = "شكل" in question_tokens
    asks_for_types = "نوع" in question_tokens

    max_rrf_score = max(
        (float(chunk.get("rrf_score") or 0.0) for chunk in chunks),
        default=0.0,
    )

    reranked: list[dict[str, Any]] = []

    for chunk in chunks:
        topic = str(chunk.get("topic") or "")
        reference = str(chunk.get("reference") or "")
        source_name = str(chunk.get("source_name") or "")
        text = str(chunk.get("text") or "")

        searchable = " ".join(
            [
                topic,
                reference,
                source_name,
                text,
            ]
        )

        searchable_tokens = tokenize_for_rerank(searchable)
        topic_tokens = tokenize_for_rerank(topic)

        overlap_count = len(question_tokens & searchable_tokens)
        topic_overlap_count = len(question_tokens & topic_tokens)

        lexical_score = (
            overlap_count / len(question_tokens)
            if question_tokens
            else 0.0
        )
        lexical_score = min(1.0, lexical_score)

        topic_score = (
            topic_overlap_count / len(topic_tokens)
            if topic_tokens
            else 0.0
        )
        topic_score = min(1.0, topic_score)

        intent_bonus = 0.0

        # Definition questions should prioritize definition articles.
        if definition_intent and "تعريف" in topic_tokens:
            intent_bonus += 0.18

        # List/form questions should prioritize articles whose topic
        # explicitly contains the requested concept.
        if asks_for_forms and "شكل" in topic_tokens:
            intent_bonus += 0.14

        if asks_for_types and "نوع" in topic_tokens:
            intent_bonus += 0.12

        rrf_score = float(chunk.get("rrf_score") or 0.0)
        normalized_rrf = (
            rrf_score / max_rrf_score
            if max_rrf_score > 0.0
            else 0.0
        )

        vector_score = float(chunk.get("vector_score") or 0.0)

        final_score = (
            0.42 * normalized_rrf
            + 0.18 * vector_score
            + 0.20 * lexical_score
            + 0.20 * topic_score
            + intent_bonus
        )

        updated = dict(chunk)
        updated["score"] = round(
            min(1.0, max(0.0, final_score)),
            4,
        )
        updated["overlap_count"] = overlap_count
        updated["topic_overlap_count"] = topic_overlap_count
        updated["intent_bonus"] = round(intent_bonus, 4)
        reranked.append(updated)

    return sorted(
        reranked,
        key=lambda item: (
            item["score"],
            float(item.get("intent_bonus") or 0.0),
            float(item.get("rrf_score") or 0.0),
            float(item.get("vector_score") or 0.0),
        ),
        reverse=True,
    )


def truncate_text(text: str, limit: int) -> str:
    text = WHITESPACE_RE.sub(" ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def is_insufficient_answer(answer: str, confidence: float) -> bool:
    if confidence <= 0.0:
        return True
    return any(phrase in (answer or "") for phrase in INSUFFICIENT_PHRASES)


def build_user_prompt(question: str, chunks: list[dict[str, Any]], settings: Settings) -> str:
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
        topic = chunk.get("topic") or "بدون موضوع"
        reference = chunk.get("reference") or "بدون مرجع"
        text = truncate_text(str(chunk.get("text") or ""), settings.chunk_text_limit)
        context_parts.append(f"[{index}] {topic} - {reference}\n{text}")

    context = "\n\n".join(context_parts)
    return f"""السؤال:
{question}

النصوص القانونية المسترجعة:
{context}

المطلوب:
إذا كانت النصوص المسترجعة كافية، أجب بالعربية وبنفس العناوين التالية حرفياً:

الإجابة المختصرة:
اكتب خلاصة قصيرة ومباشرة.

التفسير:
اشرح السبب اعتماداً على النصوص المسترجعة فقط.

المراجع:
- اذكر المراجع الموجودة في النصوص المسترجعة فقط.

تنبيه:
هذا شرح أولي وليس استشارة قانونية.

إذا كانت النصوص المسترجعة غير كافية أو غير مرتبطة بالسؤال، اكتب فقط:
لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.

Rules:
- Do not include <think>.
- Do not show reasoning steps.
- Do not invent article numbers.
- Do not mention citations that are not in retrieved context.
- Keep Arabic spacing clean and do not glue words together.
- Do not over-explain.
- If context is not enough, say:
  لا تكفي قاعدة المعرفة الحالية للإجابة بثقة."""


def build_citations(chunks: list[dict[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        citations.append(
            Citation(
                chunk_id=chunk_id,
                source_name=str(chunk.get("source_name") or ""),
                reference=str(chunk.get("reference") or ""),
                topic=str(chunk.get("topic") or ""),
                source_page=chunk.get("source_page"),
            )
        )
    return citations


def build_retrieved_preview(chunks: list[dict[str, Any]]) -> list[RetrievedChunk]:
    previews: list[RetrievedChunk] = []
    for chunk in chunks:
        previews.append(
            RetrievedChunk(
                chunk_id=str(chunk.get("chunk_id") or ""),
                topic=str(chunk.get("topic") or ""),
                reference=str(chunk.get("reference") or ""),
                score=float(chunk.get("score") or 0.0),
                text_preview=truncate_text(str(chunk.get("text") or ""), 260),
            )
        )
    return previews


def answer_question(question: str, k: int, settings: Settings) -> RAGResponse:
    query_vector = embed_question(question, settings)
    retrieved = retrieve_chunks(question, query_vector, k, settings)
    reranked = rerank_chunks(question, retrieved)

    if not reranked:
        return RAGResponse(
            answer=INSUFFICIENT_ANSWER,
            citations=[],
            confidence=0.0,
            retrieved_chunks=[],
            disclaimer=DISCLAIMER,
        )

    prompt_chunks = reranked[: settings.rag_prompt_top_n]
    user_prompt = build_user_prompt(question, prompt_chunks, settings)
    try:
        answer = generate_answer(SYSTEM_PROMPT, user_prompt, settings)
    except GeneratorError:
        raise

    answer = clean_llm_output(answer)
    if any(
        phrase in answer for phrase in INSUFFICIENT_PHRASES
    ):
        confidence = 0.0
    else:
        top_scores = [
            float(chunk.get("score") or 0.0)
            for chunk in prompt_chunks[:2]
        ]
        confidence = (
            sum(top_scores) / len(top_scores)
            if top_scores
            else 0.0
        )
    confidence = round(min(1.0, max(0.0, confidence)), 3)
    insufficient = is_insufficient_answer(answer, confidence)
    if insufficient:
        confidence = 0.0
        if not any(phrase in answer for phrase in INSUFFICIENT_PHRASES):
            answer = INSUFFICIENT_ANSWER

    return RAGResponse(
        answer=answer,
        citations=[] if insufficient else build_citations(prompt_chunks),
        confidence=confidence,
        retrieved_chunks=build_retrieved_preview(reranked[:k]),
        disclaimer=DISCLAIMER,
    )
