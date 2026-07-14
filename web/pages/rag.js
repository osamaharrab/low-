import Head from "next/head";

import AppShell from "../components/AppShell";
import ErrorState from "../components/ErrorState";
import LegalNotice from "../components/LegalNotice";
import LoadingState from "../components/LoadingState";
import PageHero from "../components/PageHero";
import QueryComposer from "../components/QueryComposer";
import StatusBadge from "../components/StatusBadge";
import TranslationToggle from "../components/TranslationToggle";
import { useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "ما المقصود بالفصل التعسفي؟",
  "ما حقوق العامل في الإجازة السنوية؟",
  "هل يجوز الخصم من أجر العامل؟",
];

const GENERIC_ERROR_MESSAGE = "تعذر معالجة الطلب حالياً. يرجى المحاولة مرة أخرى.";
const MALFORMED_RESPONSE_MESSAGE = "عاد المساعد باستجابة غير متوقعة. يرجى المحاولة مرة أخرى.";
const INSUFFICIENT_FALLBACK = "لم تتضمن المصادر القانونية المتاحة أدلة كافية لإنتاج إجابة موثوقة لهذا السؤال.";
const INSUFFICIENT_GUIDANCE = "يمكنك إعادة صياغة السؤال أو تحديد القانون، المادة، أو الواقعة القانونية المقصودة.";
const INSUFFICIENT_ANSWER_PATTERNS = [
  /لا\s+تكفي\s+قاعدة\s+المعرفة\s+الحالية\s+للإجابة\s+بثقة/i,
  /المعلومات\s+غير\s+كافية/i,
  /لا\s+توجد\s+معلومات\s+كافية/i,
  /لا\s+أستطيع\s+الإجابة/i,
  /لا\s+تتوفر\s+مصادر\s+كافية/i,
];

const ANSWER_SECTION_DEFS = [
  {
    key: "shortAnswer",
    title: "الإجابة المختصرة",
    labels: ["الإجابة المختصرة", "الجواب المختصر", "الخلاصة"],
  },
  {
    key: "explanation",
    title: "التفسير",
    labels: ["التفسير", "الشرح", "التوضيح", "التفصيل"],
  },
  {
    key: "references",
    title: "المراجع",
    labels: ["المراجع", "المصادر", "الاستناد"],
  },
  {
    key: "disclaimer",
    title: "تنبيه",
    labels: ["تنبيه", "إخلاء مسؤولية", "ملاحظة"],
  },
];

const ANSWER_SECTION_TITLES = ANSWER_SECTION_DEFS.reduce((acc, section) => {
  acc[section.key] = section.title;
  return acc;
}, {});

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

function sectionKeyFromLabel(label) {
  const normalizedLabel = toText(label).replace(/\s+/g, " ");
  const match = ANSWER_SECTION_DEFS.find((section) => section.labels.some((knownLabel) => normalizedLabel === knownLabel));
  return match?.key || "";
}

function splitAnswerSections(answerText) {
  const sections = {
    preface: [],
    shortAnswer: [],
    explanation: [],
    references: [],
    disclaimer: [],
  };
  let currentKey = "preface";

  toText(answerText)
    .split(/\r?\n/)
    .forEach((line) => {
      const headingMatch = line.match(/^\s*(?:[-*•\d.)،\s]+)?([^:：]{2,48})\s*[:：]\s*(.*)$/);
      const headingKey = headingMatch ? sectionKeyFromLabel(headingMatch[1]) : "";

      if (headingKey) {
        currentKey = headingKey;
        if (headingMatch[2]) {
          sections[currentKey].push(headingMatch[2]);
        }
        return;
      }

      sections[currentKey].push(line);
    });

  Object.keys(sections).forEach((key) => {
    sections[key] = sections[key].join("\n").trim();
  });

  if (!sections.shortAnswer && sections.preface) {
    sections.shortAnswer = sections.preface;
    sections.preface = "";
  } else if (sections.preface) {
    sections.explanation = [sections.preface, sections.explanation].filter(Boolean).join("\n\n");
    sections.preface = "";
  }

  if (!sections.shortAnswer && !sections.explanation && answerText) {
    sections.shortAnswer = toText(answerText);
  }

  return sections;
}

function isInsufficientAnswer(rag) {
  const answerText = toText(rag.answerText);
  const confidenceIsZero = rag.confidence === 0 && rag.citations.length === 0;
  return confidenceIsZero || INSUFFICIENT_ANSWER_PATTERNS.some((pattern) => pattern.test(answerText));
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
      label: "مؤشر الثقة",
      tone: "neutral",
      value: String(value),
    };
  }

  if (ratio >= 0.75) {
    return {
      label: "مؤشر ثقة مرتفع",
      tone: "success",
      value: `${Math.round(ratio * 100)}%`,
    };
  }

  if (ratio >= 0.45) {
    return {
      label: "مؤشر ثقة متوسط",
      tone: "accent",
      value: `${Math.round(ratio * 100)}%`,
    };
  }

  return {
    label: "مؤشر ثقة محدود",
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

function citationSourceKind(citation) {
  if (citation.is_official === true) {
    return { label: "مصدر قانوني رسمي", tone: "success" };
  }

  const sourceType = toText(citation.source_type || citation.type || citation.source_kind).toLowerCase();
  if (!sourceType) {
    return null;
  }

  if (/official|primary|statute|legislation|gazette|قانون|تشريع|الجريدة الرسمية/.test(sourceType)) {
    return { label: "مصدر قانوني رسمي", tone: "success" };
  }

  if (/secondary|guide|summary|دليل|إرشاد|شرح/.test(sourceType)) {
    return { label: "مصدر إرشادي", tone: "accent" };
  }

  return null;
}

function citationMeta(citation, title) {
  const topic = toText(citation.topic || citation.topic_name);
  const reference = toText(citation.reference || citation.ref);
  const sourceName = toText(citation.source_name || citation.source);
  const sourcePage = toText(citation.source_page || citation.page || citation.page_number);
  const articleNumber = toText(citation.article_number || citation.article);
  const fields = [
    ["الموضوع", topic && topic !== title ? topic : ""],
    ["المرجع", reference && reference !== title ? reference : ""],
    ["المصدر", sourceName],
    ["الصفحة", sourcePage],
    ["المادة", articleNumber],
  ];

  return fields.filter(([, value]) => value);
}

function CitationCard({ citation, index }) {
  const topic = toText(citation.topic || citation.topic_name);
  const reference = toText(citation.reference || citation.ref);
  const sourceName = toText(citation.source_name || citation.source);
  const articleNumber = toText(citation.article_number || citation.article);
  const title = reference || sourceName || topic || (articleNumber ? `المادة ${articleNumber}` : `مرجع ${index + 1}`);
  const meta = citationMeta(citation, title);
  const sourceKind = citationSourceKind(citation);

  return (
    <article className="citation-card">
      <span className="citation-card__number" aria-label={`مرجع ${index + 1}`}>
        {index + 1}
      </span>
      <div className="citation-card__body">
        <div className="citation-card__title-row">
          <strong className="citation-card__title source-card__value" dir={contentDirection(title)} lang={hasArabic(title) ? "ar" : "en"}>
            {title}
          </strong>
          {sourceKind && <StatusBadge tone={sourceKind.tone}>{sourceKind.label}</StatusBadge>}
        </div>
        {meta.length > 0 && (
          <dl className="compact-meta-list">
            {meta.map(([label, value]) => (
              <div key={`${label}-${value}`}>
                <dt>{label}</dt>
                <dd dir={contentDirection(value)} lang={hasArabic(value) ? "ar" : "en"}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </article>
  );
}

function chunkPreview(chunk) {
  return toText(chunk.text_preview || chunk.preview || chunk.text || chunk.content || chunk.source_text);
}

function RetrievedChunkCard({ chunk, index }) {
  const topic = toText(chunk.topic || chunk.topic_name);
  const reference = toText(chunk.reference || chunk.ref);
  const source = toText(chunk.source_name || chunk.source);
  const chunkId = toText(chunk.chunk_id || chunk.id);
  const preview = chunkPreview(chunk);
  const score = formatScore(chunk.score ?? chunk.retrieval_score ?? chunk.distance);

  return (
    <article className="evidence-card">
      <div className="evidence-card__header">
        <span className="evidence-card__topic" dir={contentDirection(topic || reference)} lang={hasArabic(topic || reference) ? "ar" : "en"}>
          {topic || reference || `دليل ${index + 1}`}
        </span>
        {score && <span className="meta-pill">الدرجة: {score}</span>}
      </div>
      {reference && topic !== reference && (
        <span className="evidence-card__reference" dir={contentDirection(reference)} lang={hasArabic(reference) ? "ar" : "en"}>
          {reference}
        </span>
      )}
      {source && (
        <span className="evidence-card__reference" dir={contentDirection(source)} lang={hasArabic(source) ? "ar" : "en"}>
          {source}
        </span>
      )}
      {preview && (
        <p className="source-excerpt" dir={contentDirection(preview)} lang={hasArabic(preview) ? "ar" : "en"}>
          {preview}
        </p>
      )}
      {chunkId && (
        <code className="technical-id" dir="ltr">
          {chunkId}
        </code>
      )}
    </article>
  );
}

function AnswerTextSection({ title, text, variant = "plain" }) {
  if (!text) {
    return null;
  }

  return (
    <section className={`answer-section answer-section--${variant}`}>
      <h3>{title}</h3>
      <p className="answer-copy legal-content" dir={contentDirection(text)} lang={hasArabic(text) ? "ar" : "en"}>
        {text}
      </p>
    </section>
  );
}

function AnswerDisclaimer({ text }) {
  if (!text) {
    return null;
  }

  return (
    <aside className="answer-disclaimer" aria-label="تنبيه قانوني">
      <strong>تنبيه</strong>
      <p dir={contentDirection(text)} lang={hasArabic(text) ? "ar" : "en"}>
        {text}
      </p>
    </aside>
  );
}

function RagResultHeader({ confidence, isAbstention }) {
  return (
    <div className="result-card__header legal-result__header" dir="rtl">
      <div>
        <h2>النتيجة القانونية</h2>
        <p>عرض أولي منظم بناءً على المصادر القانونية المتاحة.</p>
      </div>
      <div className="result-status-row">
        <StatusBadge tone={isAbstention ? "warning" : "success"}>
          {isAbstention ? "المعلومات غير كافية" : "إجابة مستندة إلى المصادر"}
        </StatusBadge>
        {confidence && (
          <span className="confidence-chip" title="مؤشر تقني للاستناد إلى المصادر، وليس ضماناً لصحة قانونية نهائية.">
            <span>{confidence.label}</span>
            <strong>{confidence.value}</strong>
          </span>
        )}
      </div>
    </div>
  );
}

function InsufficientRagResult({ answerText }) {
  const message = toText(answerText) || INSUFFICIENT_FALLBACK;

  return (
    <section className="insufficient-panel" dir="rtl" lang="ar">
      <h3>المعلومات القانونية المتاحة غير كافية</h3>
      <p>{message}</p>
      <p>{INSUFFICIENT_GUIDANCE}</p>
    </section>
  );
}

function insufficientResultText(answerText) {
  return `${toText(answerText) || INSUFFICIENT_FALLBACK}\n\n${INSUFFICIENT_GUIDANCE}`;
}

function buildRagHumanAnswerText({ isAbstention, answerText, answerSections, showTextualReferences }) {
  if (isAbstention) {
    return insufficientResultText(answerText);
  }

  return [
    answerSections.shortAnswer,
    answerSections.explanation,
    showTextualReferences ? answerSections.references : "",
  ]
    .map(toText)
    .filter(Boolean)
    .join("\n\n");
}

function CopyAnswerButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function copyAnswer() {
    const answerText = toText(text);
    if (!answerText || !navigator?.clipboard?.writeText) {
      return;
    }

    await navigator.clipboard.writeText(answerText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <button type="button" className="result-action-button" onClick={copyAnswer} disabled={!toText(text)}>
      {copied ? "Copied" : "Copy answer"}
    </button>
  );
}

function toggleDetails(detailsRef) {
  if (detailsRef.current) {
    detailsRef.current.open = !detailsRef.current.open;
  }
}

function RagTechnicalDetails({ citations, retrievedChunks, confidence, detailsRef, detailsId }) {
  const citationIds = citations.map((citation) => toText(citation.chunk_id || citation.id)).filter(Boolean);
  const chunkIds = retrievedChunks.map((chunk) => toText(chunk.chunk_id || chunk.id)).filter(Boolean);
  const hasDetails = retrievedChunks.length > 0 || citationIds.length > 0 || chunkIds.length > 0 || confidence !== null;

  if (!hasDetails) {
    return null;
  }

  return (
    <details className="details-panel" ref={detailsRef} id={detailsId}>
      <summary>عرض الأدلة المسترجعة والتفاصيل التقنية</summary>
      <div className="details-panel__content">
        {retrievedChunks.length > 0 && (
          <section className="details-panel__section">
            <h3>الأدلة المسترجعة</h3>
            <div className="evidence-grid">
              {retrievedChunks.map((chunk, index) => (
                <RetrievedChunkCard key={toText(chunk.chunk_id || chunk.id) || index} chunk={chunk} index={index} />
              ))}
            </div>
          </section>
        )}
        <dl className="technical-list">
          {confidence !== null && (
            <div>
              <dt>قيمة الثقة الخام</dt>
              <dd dir="ltr">{confidence}</dd>
            </div>
          )}
          {citationIds.length > 0 && (
            <div>
              <dt>معرفات المراجع</dt>
              <dd dir="ltr">{citationIds.join(", ")}</dd>
            </div>
          )}
          {chunkIds.length > 0 && (
            <div>
              <dt>معرفات الأدلة</dt>
              <dd dir="ltr">{chunkIds.join(", ")}</dd>
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
  const technicalDetailsRef = useRef(null);

  const rag = normalizeRagResult(result);
  const confidence = confidenceInfo(rag.confidence);
  const answerSections = splitAnswerSections(rag.answerText);
  const isAbstention = isInsufficientAnswer(rag);
  const visibleDisclaimer = rag.disclaimer || answerSections.disclaimer;
  const showStructuredCitations = !isAbstention && rag.citations.length > 0;
  const showTextualReferences = !showStructuredCitations && Boolean(answerSections.references);
  const hasStructuredAnswer = Boolean(answerSections.shortAnswer || answerSections.explanation || showTextualReferences);
  const humanAnswerText = buildRagHumanAnswerText({
    isAbstention,
    answerText: rag.answerText,
    answerSections,
    showTextualReferences,
  });
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

        {error && (
          <ErrorState title="تعذر عرض النتيجة" message={error} onRetry={canRetry ? submitQuestion : undefined} retryLabel="إعادة المحاولة" />
        )}
        {loading && <LoadingState message="جار البحث في المصادر القانونية وتجهيز النتيجة..." />}

        {result && (
          <section className="results-stack" aria-live="polite">
            <article className="result-card result-card--soft legal-result-card">
              <RagResultHeader confidence={confidence} isAbstention={isAbstention} />

              {isAbstention ? (
                <InsufficientRagResult answerText={rag.answerText} />
              ) : (
                <>
                  {hasStructuredAnswer ? (
                    <>
                      <AnswerTextSection title={ANSWER_SECTION_TITLES.shortAnswer} text={answerSections.shortAnswer} variant="lead" />
                      <AnswerTextSection title={ANSWER_SECTION_TITLES.explanation} text={answerSections.explanation} />
                      {showTextualReferences && (
                        <AnswerTextSection title={ANSWER_SECTION_TITLES.references} text={answerSections.references} variant="references" />
                      )}
                    </>
                  ) : (
                    <section className="insufficient-panel" dir="rtl" lang="ar">
                      <h3>لا توجد إجابة قابلة للعرض</h3>
                      <p>لم تتضمن الاستجابة نص إجابة واضحاً. يمكن مراجعة التفاصيل التقنية عند توفرها.</p>
                    </section>
                  )}

                  {showStructuredCitations && (
                    <section className="answer-section citations-section" dir="rtl">
                      <div className="section-title-row">
                        <h3>المراجع القانونية</h3>
                        <StatusBadge>{rag.citations.length}</StatusBadge>
                      </div>
                      <div className="citation-grid">
                        {rag.citations.map((citation, index) => (
                          <CitationCard key={toText(citation.chunk_id || citation.id) || index} citation={citation} index={index} />
                        ))}
                      </div>
                    </section>
                  )}
                </>
              )}

              {humanAnswerText && (
                <div className="result-action-row">
                  <CopyAnswerButton text={humanAnswerText} />
                  <TranslationToggle text={humanAnswerText} apiUrl={API_URL} />
                  <button
                    type="button"
                    className="result-action-button"
                    onClick={() => toggleDetails(technicalDetailsRef)}
                    aria-controls="rag-technical-details"
                  >
                    Technical details
                  </button>
                </div>
              )}

              <AnswerDisclaimer text={visibleDisclaimer} />
            </article>

            <RagTechnicalDetails
              citations={rag.citations}
              retrievedChunks={rag.retrievedChunks}
              confidence={rag.confidence}
              detailsRef={technicalDetailsRef}
              detailsId="rag-technical-details"
            />
          </section>
        )}

        {(!result || !visibleDisclaimer) && <LegalNotice />}
      </div>
    </AppShell>
  );
}
