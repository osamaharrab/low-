import Head from "next/head";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import AppShell from "../components/AppShell";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LegalNotice from "../components/LegalNotice";
import LoadingState from "../components/LoadingState";
import PageHero from "../components/PageHero";
import QueryComposer from "../components/QueryComposer";
import StatusBadge from "../components/StatusBadge";
import TranslationToggle from "../components/TranslationToggle";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "ما المواد المرتبطة بإنهاء عقد العمل؟",
  "ما الموضوعات المرتبطة بالإجازة السنوية؟",
  "أي قانون يحتوي على مواد الفصل التعسفي؟",
];

const RELATIONSHIP_LABELS = {
  HAS_TOPIC: "مرتبطة بموضوع",
  HAS_ARTICLE: "يتضمن مادة",
  REFERS_TO: "يشير إلى",
  RELATED_TO: "مرتبط بـ",
  CONTAINS: "يتضمن",
  PART_OF: "جزء من",
  APPLIES_TO: "ينطبق على",
  REGULATES: "ينظم",
  DEFINES: "يعرّف",
  MENTIONS: "يذكر",
};

const PROPERTY_LABELS = {
  name: "الاسم",
  number: "الرقم",
  title: "العنوان",
  topic: "الموضوع",
  summary: "الملخص",
  text: "النص",
  reference: "المرجع",
  description: "الوصف",
  jurisdiction: "الاختصاص",
  law_name: "القانون",
  law_title: "القانون",
  article_number: "رقم المادة",
  source_name: "المصدر",
  source_type: "نوع المصدر",
  year: "السنة",
};

const TECHNICAL_ANSWER_RE = /^أرجعت قاعدة المعرفة التجريبية\s+\d+\s+صف/;
const SUMMARY_LIMIT = 320;
const GENERIC_ERROR_MESSAGE = "تعذر تنفيذ الاستعلام حالياً. يرجى المحاولة مرة أخرى.";
const MALFORMED_RESPONSE_MESSAGE = "عاد الرسم المعرفي باستجابة غير متوقعة. يرجى المحاولة مرة أخرى.";
const SAFE_ERROR_MESSAGES = new Set([
  GENERIC_ERROR_MESSAGE,
  MALFORMED_RESPONSE_MESSAGE,
  "تعذر تحويل السؤال إلى استعلام آمن. جرّب صياغة السؤال بطريقة مختلفة.",
  "خدمة الرسم المعرفي غير متاحة حالياً. يرجى المحاولة لاحقاً.",
]);

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

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

function uniqueValues(values) {
  return [...new Set(values.map(toText).filter(Boolean))];
}

function formatReadableList(values) {
  const items = uniqueValues(values);
  if (items.length <= 1) {
    return items[0] || "";
  }
  if (items.length === 2) {
    return `${items[0]} و${items[1]}`;
  }
  return `${items.slice(0, -1).join("، ")}، و${items[items.length - 1]}`;
}

function getLabels(node) {
  return safeArray(node?.labels).map(toText).filter(Boolean);
}

function getProperties(node) {
  return safeObject(node?.properties);
}

function hasLabel(node, label) {
  return getLabels(node).includes(label);
}

function isSerializedNode(value) {
  return (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    typeof value.id === "string" &&
    Array.isArray(value.labels) &&
    (value.properties === undefined ||
      (value.properties && typeof value.properties === "object" && !Array.isArray(value.properties)))
  );
}

function isSerializedRelationship(value) {
  return (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    typeof value.id === "string" &&
    typeof value.type === "string" &&
    typeof value.source === "string" &&
    typeof value.target === "string" &&
    (value.properties === undefined ||
      (value.properties && typeof value.properties === "object" && !Array.isArray(value.properties)))
  );
}

function addNode(nodeMap, node) {
  if (isSerializedNode(node) && !nodeMap.has(node.id)) {
    nodeMap.set(node.id, {
      ...node,
      labels: getLabels(node),
      properties: getProperties(node),
    });
  }
}

function addRelationship(relationshipMap, relationship) {
  if (isSerializedRelationship(relationship) && !relationshipMap.has(relationship.id)) {
    relationshipMap.set(relationship.id, {
      ...relationship,
      properties: safeObject(relationship.properties),
    });
  }
}

function collectGraphValues(value, nodeMap, relationshipMap) {
  if (isSerializedRelationship(value)) {
    addRelationship(relationshipMap, value);
  } else if (isSerializedNode(value)) {
    addNode(nodeMap, value);
  }

  if (Array.isArray(value)) {
    value.forEach((item) => collectGraphValues(item, nodeMap, relationshipMap));
    return;
  }

  if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectGraphValues(item, nodeMap, relationshipMap));
  }
}

function articleSortValue(node) {
  const rawNumber = toText(getProperties(node).number);
  const numeric = Number.parseInt(rawNumber.replace(/[^\d]/g, ""), 10);
  return Number.isFinite(numeric) ? numeric : Number.MAX_SAFE_INTEGER;
}

function sortArticles(nodes) {
  return [...nodes].sort((left, right) => {
    const leftNumber = articleSortValue(left);
    const rightNumber = articleSortValue(right);
    if (leftNumber !== rightNumber) {
      return leftNumber - rightNumber;
    }
    return toText(getProperties(left).number).localeCompare(toText(getProperties(right).number), "ar", {
      numeric: true,
    });
  });
}

function propertyValueText(value) {
  if (Array.isArray(value)) {
    return value.map(propertyValueText).filter(Boolean).join(", ");
  }
  if (value && typeof value === "object") {
    return "";
  }
  return toText(value);
}

function nodeReadableName(node) {
  const properties = getProperties(node);
  if (hasLabel(node, "Article")) {
    const number = toText(properties.number);
    return number ? `المادة ${number}` : toText(properties.title) || "مادة قانونية";
  }
  if (hasLabel(node, "Topic")) {
    return toText(properties.name) || "موضوع قانوني";
  }
  if (hasLabel(node, "Law")) {
    return toText(properties.name) || toText(properties.title) || toText(properties.number) || "قانون أو نظام";
  }
  return (
    toText(properties.name) ||
    toText(properties.title) ||
    toText(properties.number) ||
    getLabels(node).join(", ") ||
    "كيان قانوني"
  );
}

function relationshipLabel(type) {
  const rawType = toText(type);
  if (!rawType) {
    return "علاقة";
  }
  return RELATIONSHIP_LABELS[rawType] || rawType.replace(/_/g, " ").toLowerCase();
}

function endpointName(nodeMap, id) {
  const node = nodeMap.get(toText(id));
  return node ? nodeReadableName(node) : "كيان غير معروف";
}

function relationshipSortValue(relationship, nodeMap) {
  const source = nodeMap.get(toText(relationship.source));
  const target = nodeMap.get(toText(relationship.target));
  const articleNode = [source, target].find((node) => hasLabel(node, "Article"));
  return articleNode ? articleSortValue(articleNode) : Number.MAX_SAFE_INTEGER;
}

function sortRelationships(relationships, nodeMap) {
  return [...relationships].sort((left, right) => {
    const leftArticle = relationshipSortValue(left, nodeMap);
    const rightArticle = relationshipSortValue(right, nodeMap);
    if (leftArticle !== rightArticle) {
      return leftArticle - rightArticle;
    }
    const leftLabel = `${endpointName(nodeMap, left.source)} ${relationshipLabel(left.type)} ${endpointName(nodeMap, left.target)}`;
    const rightLabel = `${endpointName(nodeMap, right.source)} ${relationshipLabel(right.type)} ${endpointName(nodeMap, right.target)}`;
    return leftLabel.localeCompare(rightLabel, "ar", { numeric: true });
  });
}

function isTechnicalAnswer(answer) {
  return TECHNICAL_ANSWER_RE.test(toText(answer));
}

function buildResultSummary({ articles, topics, laws, relationships, rowCount }) {
  const pieces = [];

  if (articles.length) {
    const numbers = uniqueValues(articles.map((node) => getProperties(node).number));
    if (numbers.length) {
      pieces.push(
        `وجد الرسم المعرفي ${articles.length} مادة قانونية مرتبطة: ${formatReadableList(numbers.map((number) => `المادة ${number}`))}.`
      );
    } else {
      pieces.push(`وجد الرسم المعرفي ${articles.length} مادة قانونية مرتبطة.`);
    }
  }

  if (topics.length) {
    const topicNames = uniqueValues(topics.map((node) => getProperties(node).name || getProperties(node).title));
    if (topicNames.length) {
      pieces.push(`الموضوعات المرتبطة: ${formatReadableList(topicNames)}.`);
    } else {
      pieces.push(`تتضمن النتيجة ${topics.length} موضوعاً قانونياً مرتبطاً.`);
    }
  }

  if (!articles.length && laws.length) {
    const lawNames = uniqueValues(laws.map((node) => getProperties(node).name || getProperties(node).title || getProperties(node).number));
    if (lawNames.length) {
      pieces.push(`القوانين أو الأنظمة المرتبطة: ${formatReadableList(lawNames)}.`);
    } else {
      pieces.push(`تتضمن النتيجة ${laws.length} قانوناً أو نظاماً مرتبطاً.`);
    }
  }

  if (relationships.length) {
    pieces.push(`وتتضمن ${relationships.length} علاقة قانونية بين الكيانات.`);
  }

  if (pieces.length) {
    return pieces.join(" ");
  }

  return rowCount > 0 ? `أرجع الرسم المعرفي ${rowCount} نتيجة مرتبطة بالسؤال.` : "";
}

function normalizeKgResult(result) {
  const nodeMap = new Map();
  const relationshipMap = new Map();
  const records = safeArray(result?.records);

  safeArray(result?.nodes).forEach((node) => addNode(nodeMap, node));
  safeArray(result?.relationships).forEach((relationship) => addRelationship(relationshipMap, relationship));
  collectGraphValues(records, nodeMap, relationshipMap);

  const nodes = [...nodeMap.values()];
  const relationships = sortRelationships([...relationshipMap.values()], nodeMap);
  const articles = sortArticles(nodes.filter((node) => hasLabel(node, "Article")));
  const topics = nodes
    .filter((node) => hasLabel(node, "Topic"))
    .sort((left, right) => nodeReadableName(left).localeCompare(nodeReadableName(right), "ar"));
  const laws = nodes
    .filter((node) => hasLabel(node, "Law"))
    .sort((left, right) => nodeReadableName(left).localeCompare(nodeReadableName(right), "ar"));
  const knownIds = new Set([...articles, ...topics, ...laws].map((node) => node.id));
  const otherNodes = nodes.filter((node) => !knownIds.has(node.id));
  const rowCount = Number.isInteger(result?.row_count) ? result.row_count : records.length;

  return {
    answerText: typeof result?.answer === "string" ? result.answer : "",
    generatedCypher: typeof result?.generated_cypher === "string" ? result.generated_cypher : "",
    parameters: safeObject(result?.parameters),
    records,
    nodes,
    relationships,
    articles,
    topics,
    laws,
    otherNodes,
    nodeMap,
    rowCount,
    disclaimer: typeof result?.disclaimer === "string" ? result.disclaimer : "",
  };
}

function apiErrorMessage(response) {
  if (response.status === 400) {
    return "تعذر تحويل السؤال إلى استعلام آمن. جرّب صياغة السؤال بطريقة مختلفة.";
  }
  if (response.status === 503) {
    return "خدمة الرسم المعرفي غير متاحة حالياً. يرجى المحاولة لاحقاً.";
  }
  return GENERIC_ERROR_MESSAGE;
}

function JsonBlock({ value }) {
  return (
    <pre className="code-block" dir="ltr">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function CodeBlock({ value }) {
  return (
    <pre className="code-block" dir="ltr">
      {value || "Unavailable"}
    </pre>
  );
}

function RowCountBadge({ count }) {
  return <StatusBadge>{Number.isInteger(count) ? `${count} نتيجة` : "0 نتيجة"}</StatusBadge>;
}

function PropertyList({ properties, omit = [] }) {
  const omitted = new Set(["id", "law_id", ...omit]);
  const entries = Object.entries(safeObject(properties))
    .filter(([key, value]) => !omitted.has(key) && propertyValueText(value))
    .slice(0, 12);

  if (!entries.length) {
    return null;
  }

  return (
    <dl className="property-list">
      {entries.map(([key, value]) => {
        const text = propertyValueText(value);
        return (
          <div key={key}>
            <dt>{PROPERTY_LABELS[key] || key}</dt>
            <dd dir={contentDirection(text)} lang={hasArabic(text) ? "ar" : "en"}>
              {text}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function ArticleCard({ node, expanded, onToggle }) {
  const properties = getProperties(node);
  const number = toText(properties.number);
  const title = toText(properties.title);
  const lawName = toText(properties.law_name || properties.law_title);
  const summary = toText(properties.summary || properties.description || properties.text);
  const reference = toText(properties.reference);
  const sourceName = toText(properties.source_name);
  const isLongSummary = summary.length > SUMMARY_LIMIT;
  const visibleSummary = !isLongSummary || expanded ? summary : `${summary.slice(0, SUMMARY_LIMIT).trim()}...`;

  return (
    <article className="article-card">
      <div className="article-card__header">
        <span className="article-kicker">{number ? `المادة ${number}` : "مادة قانونية"}</span>
      </div>
      {title && (
        <h3 dir={contentDirection(title)} lang={hasArabic(title) ? "ar" : "en"}>
          {title}
        </h3>
      )}
      {lawName && (
        <span className="source-name" dir={contentDirection(lawName)} lang={hasArabic(lawName) ? "ar" : "en"}>
          {lawName}
        </span>
      )}
      {summary && (
        <p className="article-summary" dir={contentDirection(visibleSummary)} lang={hasArabic(visibleSummary) ? "ar" : "en"}>
          {visibleSummary}
        </p>
      )}
      {isLongSummary && (
        <button className="text-button" type="button" onClick={onToggle} aria-expanded={expanded}>
          {expanded ? "عرض أقل" : "عرض المزيد"}
        </button>
      )}
      {reference && (
        <div className="reference-block">
          <strong>المرجع</strong>
          <p dir={contentDirection(reference)} lang={hasArabic(reference) ? "ar" : "en"}>
            {reference}
          </p>
        </div>
      )}
      {sourceName && (
        <span className="source-name">
          المصدر:{" "}
          <span dir={contentDirection(sourceName)} lang={hasArabic(sourceName) ? "ar" : "en"}>
            {sourceName}
          </span>
        </span>
      )}
    </article>
  );
}

function TopicCard({ node }) {
  const properties = getProperties(node);
  const name = toText(properties.name || properties.title) || "موضوع قانوني";
  const description = toText(properties.description || properties.summary);

  return (
    <article className="entity-card">
      <div className="entity-card__header">
        <span className="entity-kicker">موضوع قانوني</span>
      </div>
      <h3 dir={contentDirection(name)} lang={hasArabic(name) ? "ar" : "en"}>
        {name}
      </h3>
      {description && (
        <p className="card-text" dir={contentDirection(description)} lang={hasArabic(description) ? "ar" : "en"}>
          {description}
        </p>
      )}
    </article>
  );
}

function LawCard({ node }) {
  const properties = getProperties(node);
  const name = toText(properties.name) || toText(properties.title) || "قانون أو نظام";
  const number = toText(properties.number);
  const jurisdiction = toText(properties.jurisdiction);
  const sourceType = toText(properties.source_type);

  return (
    <article className="entity-card">
      <div className="entity-card__header">
        <span className="entity-kicker">قانون أو نظام</span>
      </div>
      <h3 dir={contentDirection(name)} lang={hasArabic(name) ? "ar" : "en"}>
        {name}
      </h3>
      <div className="meta-list">
        {number && <span className="meta-pill">الرقم: {number}</span>}
        {jurisdiction && (
          <span className="meta-pill" dir={contentDirection(jurisdiction)}>
            الاختصاص: {jurisdiction}
          </span>
        )}
        {sourceType && (
          <span className="meta-pill" dir={contentDirection(sourceType)}>
            نوع المصدر: {sourceType}
          </span>
        )}
      </div>
    </article>
  );
}

function GenericNodeCard({ node }) {
  const labels = getLabels(node);
  const properties = getProperties(node);
  const name = nodeReadableName(node);

  return (
    <article className="entity-card">
      <div className="entity-card__header">
        <span className="entity-kicker">كيان مرتبط</span>
      </div>
      <h3 dir={contentDirection(name)} lang={hasArabic(name) ? "ar" : "en"}>
        {name}
      </h3>
      {labels.length > 0 && <p className="node-type">النوع: {labels.join(", ")}</p>}
      <PropertyList properties={properties} />
    </article>
  );
}

function RelationshipCard({ relationship, nodeMap }) {
  const properties = safeObject(relationship.properties);
  const source = endpointName(nodeMap, relationship.source);
  const target = endpointName(nodeMap, relationship.target);

  return (
    <article className="relationship-card">
      <p className="relationship-line" dir="rtl">
        <strong className="entity-name" dir={contentDirection(source)} lang={hasArabic(source) ? "ar" : "en"}>
          {source}
        </strong>
        <span className="relationship-label">{relationshipLabel(relationship.type)}</span>
        <strong className="entity-name" dir={contentDirection(target)} lang={hasArabic(target) ? "ar" : "en"}>
          {target}
        </strong>
      </p>
      <div className="relationship-properties">
        <PropertyList properties={properties} />
      </div>
    </article>
  );
}

function KgResultHeader({ rowCount }) {
  return (
    <div className="result-card__header legal-result__header" dir="rtl">
      <div>
        <h2>نتيجة الاستعلام القانوني</h2>
        <p>إجابة مولدة من الرسم المعرفي القانوني.</p>
      </div>
      <div className="result-status-row">
        <StatusBadge tone="accent">الرسم المعرفي القانوني</StatusBadge>
        {Number.isInteger(rowCount) && <RowCountBadge count={rowCount} />}
      </div>
    </div>
  );
}

function ResultMetric({ label, value }) {
  if (!value) {
    return null;
  }

  return (
    <div className="result-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function KgResultMetrics({ kg }) {
  const metricCount = [kg.articles.length, kg.topics.length, kg.laws.length, kg.relationships.length].filter(Boolean).length;

  if (!metricCount) {
    return null;
  }

  return (
    <div className="result-metrics" dir="rtl" aria-label="ملخص النتيجة">
      <ResultMetric label="مواد قانونية" value={kg.articles.length} />
      <ResultMetric label="موضوعات" value={kg.topics.length} />
      <ResultMetric label="قوانين وأنظمة" value={kg.laws.length} />
      <ResultMetric label="علاقات" value={kg.relationships.length} />
    </div>
  );
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

function KgAnswerBlock({ answerText, summaryText }) {
  if (!answerText) {
    return null;
  }

  return (
    <section className="answer-section answer-section--lead">
      <h3>الإجابة</h3>
      <p className="answer-copy legal-content" dir={contentDirection(answerText)} lang={hasArabic(answerText) ? "ar" : "en"}>
        {answerText}
      </p>
      {summaryText && summaryText !== answerText && (
        <p className="result-summary-note" dir={contentDirection(summaryText)} lang={hasArabic(summaryText) ? "ar" : "en"}>
          {summaryText}
        </p>
      )}
    </section>
  );
}

function EntitySection({ title, count, children }) {
  if (!count) {
    return null;
  }

  return (
    <section className="result-card entity-section" dir="rtl">
      <div className="result-card__header">
        <h2>{title}</h2>
        <StatusBadge>{count}</StatusBadge>
      </div>
      {children}
    </section>
  );
}

export default function KGPage() {
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedArticles, setExpandedArticles] = useState(() => new Set());
  const technicalDetailsRef = useRef(null);

  const kg = useMemo(() => normalizeKgResult(result), [result]);
  const usefulNodeCount = kg.articles.length + kg.topics.length + kg.laws.length + kg.otherNodes.length;
  const hasGraphData = usefulNodeCount > 0 || kg.relationships.length > 0 || kg.records.length > 0 || kg.rowCount > 0;
  const summaryText = hasGraphData ? buildResultSummary(kg) : "";
  const backendAnswer = kg.answerText && !isTechnicalAnswer(kg.answerText) ? kg.answerText : "";
  const recordOnlySummary =
    hasGraphData && !summaryText ? "تم العثور على سجلات مرتبطة بالسؤال. يمكن مراجعة تفاصيل الاستعلام في القسم التقني." : "";
  const primaryAnswerText = backendAnswer || summaryText || recordOnlySummary;
  const hasUsefulResults = Boolean(result) && Boolean(primaryAnswerText || hasGraphData);
  const canRetry = question.trim().length >= 2 && !loading;

  function toggleArticle(articleKey) {
    setExpandedArticles((current) => {
      const next = new Set(current);
      if (next.has(articleKey)) {
        next.delete(articleKey);
      } else {
        next.add(articleKey);
      }
      return next;
    });
  }

  async function submitQuestion() {
    const trimmedQuestion = question.trim();
    if (loading || trimmedQuestion.length < 2) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setExpandedArticles(new Set());

    try {
      const response = await fetch(`${API_URL}/kg/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmedQuestion }),
      });
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (!response.ok) {
        throw new Error(apiErrorMessage(response));
      }
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error(MALFORMED_RESPONSE_MESSAGE);
      }
      setResult(data);
    } catch (err) {
      if (SAFE_ERROR_MESSAGES.has(err.message)) {
        setError(err.message);
      } else {
        setError(GENERIC_ERROR_MESSAGE);
      }
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
        <title>Knowledge Graph | Lawz AI JO</title>
        <meta name="description" content="Explore Jordanian labour-law relationships through the Lawz AI JO legal knowledge graph." />
      </Head>

      <div className="page-container">
        <PageHero
          eyebrow="Knowledge Graph Explorer"
          title="Explore Legal Relationships"
          description="Explore connections between laws, articles, and legal topics through the knowledge graph."
          badge="Neo4j · Text2Cypher"
        >
          <Link href="/rag" className="button button--secondary">
            Open Legal Assistant
          </Link>
        </PageHero>

        <QueryComposer
          id="kg-question"
          value={question}
          onChange={setQuestion}
          onSubmit={askQuestion}
          label="Knowledge Graph question"
          placeholder="Enter a legal relationship question in Arabic..."
          helperText="For best results, ask the graph-oriented legal question in Arabic."
          submitLabel="Explore the Knowledge Graph"
          loadingLabel="Querying..."
          loading={loading}
          suggestions={sampleQuestions}
          onSuggestionSelect={setQuestion}
        />

        {error && (
          <ErrorState title="تعذر عرض النتيجة" message={error} onRetry={canRetry ? submitQuestion : undefined} retryLabel="إعادة المحاولة" />
        )}
        {loading && <LoadingState message="جار الاستعلام من الرسم المعرفي القانوني..." />}

        {result && (
          <section className="results-stack" aria-live="polite">
            {hasUsefulResults ? (
              <>
                <article className="result-card result-card--soft legal-result-card">
                  <KgResultHeader rowCount={kg.rowCount} />
                  <KgAnswerBlock answerText={primaryAnswerText} summaryText={backendAnswer ? summaryText : ""} />
                  <KgResultMetrics kg={kg} />
                  {primaryAnswerText && (
                    <div className="result-action-row">
                      <CopyAnswerButton text={primaryAnswerText} />
                      <TranslationToggle text={primaryAnswerText} apiUrl={API_URL} />
                      <button
                        type="button"
                        className="result-action-button"
                        onClick={() => toggleDetails(technicalDetailsRef)}
                        aria-controls="kg-technical-details"
                      >
                        Technical details
                      </button>
                    </div>
                  )}
                </article>

                <EntitySection title="المواد القانونية" count={kg.articles.length}>
                  <div className="article-grid">
                    {kg.articles.map((node, index) => {
                      const articleKey = node.id || `${nodeReadableName(node)}-${index}`;
                      return (
                        <ArticleCard
                          key={articleKey}
                          node={node}
                          expanded={expandedArticles.has(articleKey)}
                          onToggle={() => toggleArticle(articleKey)}
                        />
                      );
                    })}
                  </div>
                </EntitySection>

                <EntitySection title="الموضوعات القانونية" count={kg.topics.length}>
                  <div className="entity-grid">
                    {kg.topics.map((node, index) => (
                      <TopicCard key={node.id || `${nodeReadableName(node)}-${index}`} node={node} />
                    ))}
                  </div>
                </EntitySection>

                <EntitySection title="القوانين والأنظمة" count={kg.laws.length}>
                  <div className="entity-grid">
                    {kg.laws.map((node, index) => (
                      <LawCard key={node.id || `${nodeReadableName(node)}-${index}`} node={node} />
                    ))}
                  </div>
                </EntitySection>

                <EntitySection title="كيانات قانونية مرتبطة" count={kg.otherNodes.length}>
                  <div className="entity-grid">
                    {kg.otherNodes.map((node, index) => (
                      <GenericNodeCard key={node.id || `${nodeReadableName(node)}-${index}`} node={node} />
                    ))}
                  </div>
                </EntitySection>

                <EntitySection title="العلاقات القانونية" count={kg.relationships.length}>
                  <div className="relationship-grid">
                    {kg.relationships.map((relationship, index) => (
                      <RelationshipCard key={relationship.id || `${relationship.type}-${index}`} relationship={relationship} nodeMap={kg.nodeMap} />
                    ))}
                  </div>
                </EntitySection>
              </>
            ) : (
              <EmptyState
                title="لا توجد علاقات قانونية مطابقة"
                message="لم يعثر الرسم المعرفي على علاقة قانونية مطابقة لهذا السؤال. جرّب تحديد المادة أو الموضوع القانوني بصياغة مختلفة."
              />
            )}

            <details className="details-panel" ref={technicalDetailsRef} id="kg-technical-details">
              <summary>عرض الاستعلام والتفاصيل التقنية</summary>
              <div className="details-panel__content">
                <section className="details-panel__section">
                  <h3>استعلام Cypher الناتج</h3>
                  <CodeBlock value={kg.generatedCypher} />
                </section>
                <section className="details-panel__section">
                  <h3>معاملات الاستعلام</h3>
                  <JsonBlock value={kg.parameters} />
                </section>
                <section className="details-panel__section">
                  <h3>السجلات الخام</h3>
                  <JsonBlock value={kg.records} />
                </section>
                <section className="details-panel__section">
                  <h3>العقد الخام</h3>
                  <JsonBlock value={kg.nodes} />
                </section>
                <section className="details-panel__section">
                  <h3>العلاقات الخام</h3>
                  <JsonBlock value={kg.relationships} />
                </section>
              </div>
            </details>

            {kg.disclaimer && <LegalNotice disclaimer={kg.disclaimer} />}
          </section>
        )}

        {(!result || !kg.disclaimer) && <LegalNotice />}
      </div>
    </AppShell>
  );
}
