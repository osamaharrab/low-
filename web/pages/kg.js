import Head from "next/head";
import Link from "next/link";
import { useMemo, useState } from "react";

import AppShell from "../components/AppShell";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LegalNotice from "../components/LegalNotice";
import LoadingState from "../components/LoadingState";
import PageHero from "../components/PageHero";
import QueryComposer from "../components/QueryComposer";
import StatusBadge from "../components/StatusBadge";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "ما المواد المرتبطة بإنهاء عقد العمل؟",
  "ما الموضوعات المرتبطة بالإجازة السنوية؟",
  "أي قانون يحتوي على مواد الفصل التعسفي؟",
];

const RELATIONSHIP_LABELS = {
  HAS_TOPIC: "Related to topic",
  HAS_ARTICLE: "Contains article",
  REFERS_TO: "Refers to",
  RELATED_TO: "Related to",
};

const PROPERTY_LABELS = {
  name: "Name",
  number: "Number",
  title: "Title",
  summary: "Summary",
  reference: "Reference",
  description: "Description",
  jurisdiction: "Jurisdiction",
  source_name: "Source",
  source_type: "Source type",
  year: "Year",
};

const TECHNICAL_ANSWER_RE = /^أرجعت قاعدة المعرفة التجريبية\s+\d+\s+صف/;
const SUMMARY_LIMIT = 320;
const GENERIC_ERROR_MESSAGE = "Something went wrong while processing your request. Please try again.";
const MALFORMED_RESPONSE_MESSAGE = "The knowledge graph returned an unexpected response. Please try again.";
const SAFE_ERROR_MESSAGES = new Set([
  GENERIC_ERROR_MESSAGE,
  MALFORMED_RESPONSE_MESSAGE,
  "The graph question could not be converted into a safe query. Try phrasing it differently.",
  "The knowledge graph service is not available right now. Please try again later.",
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
    return `${items[0]} and ${items[1]}`;
  }
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
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
    return number ? `Article ${number}` : toText(properties.title) || toText(properties.id) || "Legal article";
  }
  if (hasLabel(node, "Topic")) {
    return toText(properties.name) || toText(properties.id) || "Topic";
  }
  if (hasLabel(node, "Law")) {
    return toText(properties.name) || toText(properties.title) || toText(properties.number) || toText(properties.id) || "Law";
  }
  return (
    toText(properties.name) ||
    toText(properties.title) ||
    toText(properties.number) ||
    toText(properties.id) ||
    getLabels(node).join(", ") ||
    "Graph node"
  );
}

function relationshipLabel(type) {
  return RELATIONSHIP_LABELS[type] || type || "Relationship";
}

function endpointName(nodeMap, id) {
  const node = nodeMap.get(toText(id));
  return node ? nodeReadableName(node) : "Unknown node";
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

function plural(count, singular, pluralValue) {
  return count === 1 ? singular : pluralValue;
}

function buildResultSummary({ articles, topics, laws, relationships, rowCount }) {
  const pieces = [];

  if (articles.length) {
    const numbers = uniqueValues(articles.map((node) => getProperties(node).number));
    if (numbers.length) {
      pieces.push(
        `The graph returned ${articles.length} related ${plural(articles.length, "article", "articles")}: ${formatReadableList(
          numbers.map((number) => `Article ${number}`)
        )}.`
      );
    } else {
      pieces.push(`The graph returned ${articles.length} related ${plural(articles.length, "article", "articles")}.`);
    }
  }

  if (topics.length) {
    const topicNames = uniqueValues(topics.map((node) => getProperties(node).name || getProperties(node).id));
    if (topicNames.length) {
      pieces.push(`Related topics: ${formatReadableList(topicNames)}.`);
    } else {
      pieces.push(`The result includes ${topics.length} related ${plural(topics.length, "topic", "topics")}.`);
    }
  }

  if (!articles.length && laws.length) {
    const lawNames = uniqueValues(laws.map((node) => getProperties(node).name || getProperties(node).number || getProperties(node).id));
    if (lawNames.length) {
      pieces.push(`Related laws: ${formatReadableList(lawNames)}.`);
    } else {
      pieces.push(`The result includes ${laws.length} related ${plural(laws.length, "law", "laws")}.`);
    }
  }

  if (relationships.length) {
    pieces.push(`It also returned ${relationships.length} ${plural(relationships.length, "relationship", "relationships")}.`);
  }

  if (pieces.length) {
    return pieces.join(" ");
  }

  return `The knowledge graph returned ${rowCount} related ${plural(rowCount, "result", "results")}.`;
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
    return "The graph question could not be converted into a safe query. Try phrasing it differently.";
  }
  if (response.status === 503) {
    return "The knowledge graph service is not available right now. Please try again later.";
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
  return <StatusBadge>{Number.isInteger(count) ? `${count} rows` : "0 rows"}</StatusBadge>;
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
  const summary = toText(properties.summary);
  const reference = toText(properties.reference);
  const sourceName = toText(properties.source_name);
  const isLongSummary = summary.length > SUMMARY_LIMIT;
  const visibleSummary = !isLongSummary || expanded ? summary : `${summary.slice(0, SUMMARY_LIMIT).trim()}...`;

  return (
    <article className="article-card">
      <div className="article-card__header">
        <span className="article-kicker">{number ? `Article ${number}` : "Article"}</span>
      </div>
      {title && (
        <h3 dir={contentDirection(title)} lang={hasArabic(title) ? "ar" : "en"}>
          {title}
        </h3>
      )}
      {summary && (
        <p className="article-summary" dir={contentDirection(visibleSummary)} lang={hasArabic(visibleSummary) ? "ar" : "en"}>
          {visibleSummary}
        </p>
      )}
      {isLongSummary && (
        <button className="text-button" type="button" onClick={onToggle} aria-expanded={expanded}>
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
      {reference && (
        <div className="reference-block">
          <strong>Reference</strong>
          <p dir={contentDirection(reference)} lang={hasArabic(reference) ? "ar" : "en"}>
            {reference}
          </p>
        </div>
      )}
      {sourceName && (
        <span className="source-name">
          Source:{" "}
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
  const name = toText(properties.name) || "Topic";
  const description = toText(properties.description);

  return (
    <article className="entity-card">
      <div className="entity-card__header">
        <span className="entity-kicker">Topic</span>
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
  const name = toText(properties.name) || toText(properties.title) || "Law";
  const number = toText(properties.number);
  const jurisdiction = toText(properties.jurisdiction);
  const sourceType = toText(properties.source_type);

  return (
    <article className="entity-card">
      <div className="entity-card__header">
        <span className="entity-kicker">Law</span>
      </div>
      <h3 dir={contentDirection(name)} lang={hasArabic(name) ? "ar" : "en"}>
        {name}
      </h3>
      <div className="meta-list">
        {number && <span className="meta-pill">Number: {number}</span>}
        {jurisdiction && (
          <span className="meta-pill" dir={contentDirection(jurisdiction)}>
            Jurisdiction: {jurisdiction}
          </span>
        )}
        {sourceType && (
          <span className="meta-pill" dir={contentDirection(sourceType)}>
            Source: {sourceType}
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
        <span className="entity-kicker">Related entity</span>
      </div>
      <h3 dir={contentDirection(name)} lang={hasArabic(name) ? "ar" : "en"}>
        {name}
      </h3>
      {labels.length > 0 && <p className="node-type">{labels.join(", ")}</p>}
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
      <p className="relationship-line" dir="ltr">
        <strong className="entity-name" dir={contentDirection(source)} lang={hasArabic(source) ? "ar" : "en"}>
          {source}
        </strong>
        <span className="relationship-arrow" aria-hidden="true">
          →
        </span>
        <span className="relationship-label">{relationshipLabel(relationship.type)}</span>
        <span className="relationship-arrow" aria-hidden="true">
          →
        </span>
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

export default function KGPage() {
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedArticles, setExpandedArticles] = useState(() => new Set());

  const kg = useMemo(() => normalizeKgResult(result), [result]);
  const usefulNodeCount = kg.articles.length + kg.topics.length + kg.laws.length + kg.otherNodes.length;
  const hasUsefulResults = Boolean(result) && kg.rowCount > 0 && usefulNodeCount > 0;
  const summaryText = hasUsefulResults ? buildResultSummary(kg) : "";
  const shouldShowBackendAnswer = Boolean(kg.answerText && !isTechnicalAnswer(kg.answerText) && kg.answerText !== summaryText);
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

        {error && <ErrorState message={error} onRetry={canRetry ? submitQuestion : undefined} />}
        {loading && <LoadingState message="Querying the knowledge graph..." />}

        {result && (
          <section className="results-stack" aria-live="polite">
            {hasUsefulResults ? (
              <>
                <article className="result-card result-card--soft">
                  <div className="result-card__header">
                    <h2>Result Summary</h2>
                    <RowCountBadge count={kg.rowCount} />
                  </div>
                  <p className="answer-copy">{summaryText}</p>
                  {shouldShowBackendAnswer && (
                    <p className="backend-answer legal-content" dir={contentDirection(kg.answerText)} lang={hasArabic(kg.answerText) ? "ar" : "en"}>
                      {kg.answerText}
                    </p>
                  )}
                </article>

                {kg.articles.length > 0 && (
                  <section className="result-card">
                    <div className="result-card__header">
                      <h2>Legal Articles</h2>
                      <StatusBadge>{kg.articles.length}</StatusBadge>
                    </div>
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
                  </section>
                )}

                {(kg.topics.length > 0 || kg.laws.length > 0 || kg.otherNodes.length > 0) && (
                  <section className="result-card">
                    <div className="result-card__header">
                      <h2>Related Entities</h2>
                      <StatusBadge>{kg.topics.length + kg.laws.length + kg.otherNodes.length}</StatusBadge>
                    </div>
                    <div className="entity-grid">
                      {kg.topics.map((node) => (
                        <TopicCard key={node.id} node={node} />
                      ))}
                      {kg.laws.map((node) => (
                        <LawCard key={node.id} node={node} />
                      ))}
                      {kg.otherNodes.map((node) => (
                        <GenericNodeCard key={node.id} node={node} />
                      ))}
                    </div>
                  </section>
                )}

                {kg.relationships.length > 0 && (
                  <section className="result-card">
                    <div className="result-card__header">
                      <h2>Relationships</h2>
                      <StatusBadge>{kg.relationships.length}</StatusBadge>
                    </div>
                    <div className="relationship-grid">
                      {kg.relationships.map((relationship) => (
                        <RelationshipCard key={relationship.id} relationship={relationship} nodeMap={kg.nodeMap} />
                      ))}
                    </div>
                  </section>
                )}
              </>
            ) : (
              <EmptyState
                title="No related results"
                message="No related results were found in the knowledge graph. Try phrasing the question differently."
              >
                <RowCountBadge count={kg.rowCount} />
              </EmptyState>
            )}

            <details className="details-panel">
              <summary>Query and Record Details</summary>
              <div className="details-panel__content">
                <section className="details-panel__section">
                  <h3>Generated Cypher</h3>
                  <CodeBlock value={kg.generatedCypher} />
                </section>
                <section className="details-panel__section">
                  <h3>Query Parameters</h3>
                  <JsonBlock value={kg.parameters} />
                </section>
                <section className="details-panel__section">
                  <h3>Raw Records</h3>
                  <JsonBlock value={kg.records} />
                </section>
                <section className="details-panel__section">
                  <h3>Raw Nodes</h3>
                  <JsonBlock value={kg.nodes} />
                </section>
                <section className="details-panel__section">
                  <h3>Raw Relationships</h3>
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
