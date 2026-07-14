import Head from "next/head";

import AppShell from "../components/AppShell";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LegalNotice from "../components/LegalNotice";
import LoadingState from "../components/LoadingState";
import PageHero from "../components/PageHero";
import QueryComposer from "../components/QueryComposer";
import StatusBadge from "../components/StatusBadge";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "ما المقصود بالفصل التعسفي؟",
  "ما حقوق العامل في الإجازة السنوية؟",
  "هل يجوز الخصم من أجر العامل؟",
];

const GENERIC_ERROR_MESSAGE = "Something went wrong while processing your request. Please try again.";
const MALFORMED_RESPONSE_MESSAGE = "The assistant returned an unexpected response. Please try again.";

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function toText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function hasArabic(value) {
  return /[\u0600-\u06FF]/.test(toText(value));
}

function contentDirection(value) {
  return hasArabic(value) ? "rtl" : "auto";
}

function normalizeRagResult(result) {
  return {
    answerText: typeof result?.answer === "string" ? result.answer : "",
    citations: safeArray(result?.citations),
    retrievedChunks: safeArray(result?.retrieved_chunks),
    disclaimer: typeof result?.disclaimer === "string" ? result.disclaimer : "",
    confidence: typeof result?.confidence === "number" && Number.isFinite(result.confidence) ? result.confidence : null,
  };
}

function confidenceInfo(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }

  const ratio = value > 1 && value <= 100 ? value / 100 : value;
  if (ratio < 0 || ratio > 1) {
    return {
      label: "Confidence returned",
      tone: "neutral",
      value: String(value),
    };
  }

  if (ratio >= 0.75) {
    return {
      label: "High confidence",
      tone: "success",
      value: `${Math.round(ratio * 100)}%`,
    };
  }

  if (ratio >= 0.45) {
    return {
      label: "Medium confidence",
      tone: "accent",
      value: `${Math.round(ratio * 100)}%`,
    };
  }

  return {
    label: "Limited confidence",
    tone: "warning",
    value: `${Math.round(ratio * 100)}%`,
  };
}

function formatScore(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "";
  }
  return value > 1 ? value.toFixed(2) : value.toFixed(3);
}

function citationMeta(citation) {
  const fields = [
    ["Article", citation.article_number || citation.article],
    ["Page", citation.page || citation.page_number],
    ["Source", citation.source_name || citation.source],
  ];

  return fields
    .map(([label, value]) => [label, toText(value)])
    .filter(([, value]) => value);
}

function CitationCard({ citation, index }) {
  const topic = toText(citation.topic || citation.topic_name);
  const reference = toText(citation.reference || citation.ref);
  const title = reference || topic || `Reference ${index + 1}`;
  const meta = citationMeta(citation);

  return (
    <article className="source-card">
      <span className="source-card__label">Legal reference</span>
      <strong className="source-card__title source-card__value" dir={contentDirection(title)} lang={hasArabic(title) ? "ar" : "en"}>
        {title}
      </strong>
      {topic && topic !== title && (
        <span className="source-card__value" dir={contentDirection(topic)} lang={hasArabic(topic) ? "ar" : "en"}>
          {topic}
        </span>
      )}
      {meta.length > 0 && (
        <div className="source-card__meta">
          {meta.map(([label, value]) => (
            <span className="meta-pill" key={`${label}-${value}`} dir={contentDirection(value)}>
              {label}: {value}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function chunkPreview(chunk) {
  return toText(chunk.text_preview || chunk.preview || chunk.text || chunk.content || chunk.source_text);
}

function RetrievedChunkCard({ chunk, index }) {
  const topic = toText(chunk.topic || chunk.topic_name);
  const reference = toText(chunk.reference || chunk.ref);
  const preview = chunkPreview(chunk);
  const score = formatScore(chunk.score ?? chunk.retrieval_score ?? chunk.distance);

  return (
    <article className="evidence-card">
      <div className="evidence-card__header">
        <span className="evidence-card__topic" dir={contentDirection(topic || reference)} lang={hasArabic(topic || reference) ? "ar" : "en"}>
          {topic || reference || `Evidence ${index + 1}`}
        </span>
        {score && <span className="meta-pill">Score: {score}</span>}
      </div>
      {reference && topic !== reference && (
        <span className="evidence-card__reference" dir={contentDirection(reference)} lang={hasArabic(reference) ? "ar" : "en"}>
          {reference}
        </span>
      )}
      {preview && (
        <p className="source-excerpt" dir={contentDirection(preview)} lang={hasArabic(preview) ? "ar" : "en"}>
          {preview}
        </p>
      )}
    </article>
  );
}

function TechnicalDetails({ citations, retrievedChunks, confidence }) {
  const citationIds = citations.map((citation) => toText(citation.chunk_id || citation.id)).filter(Boolean);
  const chunkIds = retrievedChunks.map((chunk) => toText(chunk.chunk_id || chunk.id)).filter(Boolean);
  const hasDetails = citationIds.length > 0 || chunkIds.length > 0 || confidence !== null;

  if (!hasDetails) {
    return null;
  }

  return (
    <details className="details-panel">
      <summary>Technical Details</summary>
      <div className="details-panel__content">
        <dl className="technical-list">
          {confidence !== null && (
            <div>
              <dt>Raw confidence</dt>
              <dd>{confidence}</dd>
            </div>
          )}
          {citationIds.length > 0 && (
            <div>
              <dt>Citation chunk IDs</dt>
              <dd>{citationIds.join(", ")}</dd>
            </div>
          )}
          {chunkIds.length > 0 && (
            <div>
              <dt>Retrieved chunk IDs</dt>
              <dd>{chunkIds.join(", ")}</dd>
            </div>
          )}
        </dl>
      </div>
    </details>
  );
}

export default function RagPage() {
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const rag = normalizeRagResult(result);
  const confidence = confidenceInfo(rag.confidence);
  const hasAnswer = Boolean(rag.answerText);
  const canRetry = question.trim().length >= 2 && !loading;

  async function submitQuestion() {
    const trimmedQuestion = question.trim();
    if (loading || trimmedQuestion.length < 2) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/rag/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmedQuestion, k: 5 }),
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) {
        throw new Error(GENERIC_ERROR_MESSAGE);
      }

      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error(MALFORMED_RESPONSE_MESSAGE);
      }

      setResult(data);
    } catch (err) {
      setError(err.message === MALFORMED_RESPONSE_MESSAGE ? MALFORMED_RESPONSE_MESSAGE : GENERIC_ERROR_MESSAGE);
    } finally {
      setLoading(false);
    }
  }

  function askQuestion(event) {
    event.preventDefault();
    submitQuestion();
  }

  return (
    <AppShell>
      <Head>
        <title>Legal Assistant | Lawz AI JO</title>
        <meta name="description" content="Ask source-grounded questions about Jordanian labour law." />
      </Head>

      <div className="page-container">
        <PageHero
          eyebrow="Legal Assistant"
          title="Ask about Jordanian Labour Law"
          description="Receive an initial explanation supported by references from the legal knowledge base."
          badge="Semantic retrieval with references"
        />

        <QueryComposer
          id="rag-question"
          value={question}
          onChange={setQuestion}
          onSubmit={askQuestion}
          label="Legal question"
          placeholder="Enter your question in Arabic about Jordanian labour law..."
          helperText="For best results, enter the legal question in Arabic."
          submitLabel="Ask the Assistant"
          loadingLabel="Searching..."
          loading={loading}
          suggestions={sampleQuestions}
          onSuggestionSelect={setQuestion}
        />

        {error && <ErrorState message={error} onRetry={canRetry ? submitQuestion : undefined} />}
        {loading && <LoadingState message="Searching legal sources and preparing the answer..." />}

        {result && (
          <section className="results-stack" aria-live="polite">
            {hasAnswer ? (
              <article className="result-card result-card--soft">
                <div className="result-card__header">
                  <h2>Answer</h2>
                </div>
                <p className="answer-copy legal-content" dir={contentDirection(rag.answerText)} lang={hasArabic(rag.answerText) ? "ar" : "en"}>
                  {rag.answerText}
                </p>
              </article>
            ) : (
              <EmptyState
                title="Insufficient evidence"
                message="The current sources do not contain enough evidence to answer this question."
              />
            )}

            {confidence && (
              <article className="result-card">
                <div className="result-card__header">
                  <h2>Confidence</h2>
                </div>
                <div className="confidence-row">
                  <StatusBadge tone={confidence.tone}>{confidence.label}</StatusBadge>
                  <strong>{confidence.value}</strong>
                </div>
              </article>
            )}

            {rag.citations.length > 0 && (
              <section className="result-card">
                <div className="result-card__header">
                  <h2>Legal References</h2>
                  <StatusBadge>{rag.citations.length}</StatusBadge>
                </div>
                <div className="citation-grid">
                  {rag.citations.map((citation, index) => (
                    <CitationCard key={toText(citation.chunk_id || citation.id) || index} citation={citation} index={index} />
                  ))}
                </div>
              </section>
            )}

            {rag.retrievedChunks.length > 0 && (
              <details className="details-panel">
                <summary>Retrieved Evidence</summary>
                <div className="details-panel__content">
                  <div className="evidence-grid">
                    {rag.retrievedChunks.map((chunk, index) => (
                      <RetrievedChunkCard key={toText(chunk.chunk_id || chunk.id) || index} chunk={chunk} index={index} />
                    ))}
                  </div>
                </div>
              </details>
            )}

            <TechnicalDetails citations={rag.citations} retrievedChunks={rag.retrievedChunks} confidence={rag.confidence} />

            {rag.disclaimer && <LegalNotice disclaimer={rag.disclaimer} />}
          </section>
        )}

        {(!result || !rag.disclaimer) && <LegalNotice />}
      </div>
    </AppShell>
  );
}
