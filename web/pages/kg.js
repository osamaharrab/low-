import { useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "ما المواد المرتبطة بإنهاء عقد العمل؟",
  "ما الموضوعات المرتبطة بالإجازة السنوية؟",
  "أي قانون يحتوي على مواد الفصل التعسفي؟",
];

const RELATIONSHIP_LABELS = {
  HAS_TOPIC: "مرتبطة بموضوع",
  HAS_ARTICLE: "يحتوي على المادة",
  REFERS_TO: "يشير إلى",
  RELATED_TO: "مرتبط بـ",
};

const PROPERTY_LABELS = {
  id: "المعرف",
  name: "الاسم",
  number: "الرقم",
  title: "العنوان",
  summary: "الملخص",
  reference: "المرجع",
  description: "الوصف",
  jurisdiction: "الاختصاص",
  source_name: "المصدر",
  source_type: "نوع المصدر",
  law_id: "معرف القانون",
  year: "السنة",
};

const TECHNICAL_ANSWER_RE = /^أرجعت قاعدة المعرفة التجريبية\s+\d+\s+صف/;
const SUMMARY_LIMIT = 320;

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

function uniqueValues(values) {
  return [...new Set(values.map(toText).filter(Boolean))];
}

function formatArabicList(values) {
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
    return value.map(propertyValueText).filter(Boolean).join("، ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return toText(value);
}

function nodeReadableName(node) {
  const properties = getProperties(node);
  if (hasLabel(node, "Article")) {
    const number = toText(properties.number);
    return number ? `المادة ${number}` : toText(properties.title) || toText(properties.id) || "مادة قانونية";
  }
  if (hasLabel(node, "Topic")) {
    return toText(properties.name) || toText(properties.id) || "موضوع";
  }
  if (hasLabel(node, "Law")) {
    return toText(properties.name) || toText(properties.title) || toText(properties.number) || toText(properties.id) || "قانون";
  }
  return (
    toText(properties.name) ||
    toText(properties.title) ||
    toText(properties.number) ||
    toText(properties.id) ||
    getLabels(node).join("، ") ||
    "عقدة"
  );
}

function relationshipLabel(type) {
  return RELATIONSHIP_LABELS[type] || type || "علاقة";
}

function endpointName(nodeMap, id) {
  const node = nodeMap.get(toText(id));
  return node ? nodeReadableName(node) : "عقدة غير معروفة";
}

function isTechnicalAnswer(answer) {
  return TECHNICAL_ANSWER_RE.test(toText(answer));
}

function buildResultSummary({ articles, topics, laws, rowCount }) {
  const pieces = [];

  if (articles.length) {
    const numbers = uniqueValues(articles.map((node) => getProperties(node).number));
    if (numbers.length) {
      pieces.push(`عثر الرسم المعرفي على ${articles.length} مواد مرتبطة بالسؤال: المواد ${formatArabicList(numbers)}.`);
    } else {
      pieces.push(`عثر الرسم المعرفي على ${articles.length} مواد مرتبطة بالسؤال.`);
    }
  }

  if (topics.length) {
    const topicNames = uniqueValues(topics.map((node) => getProperties(node).name || getProperties(node).id));
    if (topicNames.length) {
      pieces.push(`الموضوعات الظاهرة: ${formatArabicList(topicNames)}.`);
    } else {
      pieces.push(`ظهرت ${topics.length} موضوعات مرتبطة بالسؤال.`);
    }
  }

  if (!articles.length && laws.length) {
    const lawNames = uniqueValues(laws.map((node) => getProperties(node).name || getProperties(node).number || getProperties(node).id));
    if (lawNames.length) {
      pieces.push(`القوانين الظاهرة: ${formatArabicList(lawNames)}.`);
    } else {
      pieces.push(`ظهرت ${laws.length} قوانين مرتبطة بالسؤال.`);
    }
  }

  if (pieces.length) {
    return pieces.join(" ");
  }

  return `عثر الرسم المعرفي على ${rowCount} نتائج مرتبطة بالسؤال.`;
}

function normalizeKgResult(result) {
  const nodeMap = new Map();
  const relationshipMap = new Map();
  const records = safeArray(result?.records);

  safeArray(result?.nodes).forEach((node) => addNode(nodeMap, node));
  safeArray(result?.relationships).forEach((relationship) => addRelationship(relationshipMap, relationship));
  collectGraphValues(records, nodeMap, relationshipMap);

  const nodes = [...nodeMap.values()];
  const relationships = [...relationshipMap.values()];
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
    return "تعذر تحويل السؤال إلى استعلام مناسب للرسم المعرفي. جرّب صياغة مختلفة.";
  }
  if (response.status === 503) {
    return "خدمة الرسم المعرفي غير متاحة حالياً. حاول مرة أخرى بعد قليل.";
  }
  return "تعذر تنفيذ سؤال الرسم المعرفي.";
}

function JsonBlock({ value }) {
  return <pre dir="ltr">{JSON.stringify(value, null, 2)}</pre>;
}

function RowCountBadge({ count }) {
  return <span className="rowBadge">عدد الصفوف: {Number.isInteger(count) ? count : 0}</span>;
}

function PropertyList({ properties, omit = [] }) {
  const omitted = new Set(omit);
  const entries = Object.entries(safeObject(properties))
    .filter(([key, value]) => !omitted.has(key) && propertyValueText(value))
    .slice(0, 12);

  if (!entries.length) {
    return null;
  }

  return (
    <dl className="propertyList">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{PROPERTY_LABELS[key] || key}</dt>
          <dd>{propertyValueText(value)}</dd>
        </div>
      ))}
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
    <article className="articleCard">
      <div className="articleHeader">
        <span className="articleNumber">{number ? `المادة ${number}` : "مادة قانونية"}</span>
      </div>
      {title && <h3>{title}</h3>}
      {summary && <p className="articleSummary">{visibleSummary}</p>}
      {isLongSummary && (
        <button className="textButton" type="button" onClick={onToggle} aria-expanded={expanded}>
          {expanded ? "عرض أقل" : "عرض المزيد"}
        </button>
      )}
      {reference && (
        <div className="referenceBlock">
          <strong>المرجع:</strong>
          <p>{reference}</p>
        </div>
      )}
      {sourceName && <p className="sourceName">{sourceName}</p>}
    </article>
  );
}

function TopicCard({ node }) {
  const properties = getProperties(node);
  const name = toText(properties.name) || "موضوع";
  const description = toText(properties.description);

  return (
    <article className="card">
      <h3>{name}</h3>
      {description && <p className="cardText">{description}</p>}
    </article>
  );
}

function LawCard({ node }) {
  const properties = getProperties(node);
  const name = toText(properties.name) || toText(properties.title) || "قانون";
  const number = toText(properties.number);
  const jurisdiction = toText(properties.jurisdiction);
  const sourceType = toText(properties.source_type);

  return (
    <article className="card">
      <h3>{name}</h3>
      <div className="metaList">
        {number && <span>الرقم: {number}</span>}
        {jurisdiction && <span>الاختصاص: {jurisdiction}</span>}
        {sourceType && <span>المصدر: {sourceType}</span>}
      </div>
    </article>
  );
}

function GenericNodeCard({ node }) {
  const labels = getLabels(node);
  const properties = getProperties(node);

  return (
    <article className="card">
      <h3>{nodeReadableName(node)}</h3>
      {labels.length > 0 && <p className="nodeType">{labels.join("، ")}</p>}
      <PropertyList properties={properties} />
    </article>
  );
}

function RelationshipCard({ relationship, nodeMap }) {
  const properties = safeObject(relationship.properties);
  const hasProperties = Object.keys(properties).length > 0;
  const source = endpointName(nodeMap, relationship.source);
  const target = endpointName(nodeMap, relationship.target);

  return (
    <article className="relationshipCard">
      <p className="relationshipLine">
        <strong>{source}</strong>
        <span>→</span>
        <span>{relationshipLabel(relationship.type)}</span>
        <span>→</span>
        <strong>{target}</strong>
      </p>
      {hasProperties && <PropertyList properties={properties} />}
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

  async function askQuestion(event) {
    event.preventDefault();
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
        throw new Error("وصلت استجابة غير مفهومة من الخدمة.");
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "تعذر الاتصال بالخدمة.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main dir="rtl" lang="ar">
      <section className="shell">
        <header>
          <a className="navLink" href="/">
            العودة إلى صفحة RAG
          </a>
          <p className="eyebrow">رسم معرفي تجريبي</p>
          <h1>Lawz AI JO KG</h1>
          <p className="subtitle">
            واجهة مستقلة لسؤال الرسم المعرفي القانوني الأردني عبر Text2Cypher وNeo4j.
          </p>
        </header>

        <form onSubmit={askQuestion} className="askBox">
          <label htmlFor="question">السؤال</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={5}
            placeholder="اكتب سؤالك بالعربية..."
            aria-describedby="kg-help"
          />
          <p id="kg-help" className="srOnly">
            اكتب سؤالاً قانونياً بالعربية ثم اضغط زر السؤال أو مفتاح الإدخال مع التحكم حسب جهازك.
          </p>
          <div className="actions">
            <button type="submit" disabled={loading || question.trim().length < 2}>
              {loading ? "جارٍ الاستعلام..." : "اسأل الرسم المعرفي"}
            </button>
          </div>
        </form>

        <div className="samples" aria-label="أسئلة مقترحة">
          {sampleQuestions.map((sample) => (
            <button key={sample} type="button" onClick={() => setQuestion(sample)} disabled={loading}>
              {sample}
            </button>
          ))}
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {loading && (
          <p className="loading" aria-live="polite">
            جارٍ الاستعلام من الرسم المعرفي...
          </p>
        )}

        {result && (
          <section className="result" aria-live="polite">
            {hasUsefulResults ? (
              <>
                <div className="answer panel">
                  <div className="panelHeader">
                    <h2>ملخص النتيجة</h2>
                    <RowCountBadge count={kg.rowCount} />
                  </div>
                  <p className="answerText">{summaryText}</p>
                  {shouldShowBackendAnswer && <p className="backendAnswer">{kg.answerText}</p>}
                </div>

                {kg.articles.length > 0 && (
                  <section className="panel">
                    <div className="panelHeader">
                      <h2>المواد القانونية</h2>
                      <span className="sectionCount">{kg.articles.length}</span>
                    </div>
                    <div className="articleGrid">
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
                  <section className="panel">
                    <h2>العناصر المرتبطة</h2>
                    <div className="cards">
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
                  <section className="panel">
                    <div className="panelHeader">
                      <h2>العلاقات</h2>
                      <span className="sectionCount">{kg.relationships.length}</span>
                    </div>
                    <div className="relationships">
                      {kg.relationships.map((relationship) => (
                        <RelationshipCard key={relationship.id} relationship={relationship} nodeMap={kg.nodeMap} />
                      ))}
                    </div>
                  </section>
                )}
              </>
            ) : (
              <div className="emptyState panel">
                <div className="panelHeader">
                  <h2>لا توجد نتائج واضحة</h2>
                  <RowCountBadge count={kg.rowCount} />
                </div>
                <p>لم يعثر الرسم المعرفي على نتائج مرتبطة بالسؤال. جرّب صياغة السؤال بطريقة مختلفة.</p>
              </div>
            )}

            <details className="details">
              <summary>تفاصيل الاستعلام والسجلات</summary>
              <div className="detailGrid">
                <section>
                  <h3>Generated Cypher</h3>
                  <pre dir="ltr">{kg.generatedCypher || "غير متاح"}</pre>
                </section>
                <section>
                  <h3>Query parameters</h3>
                  <JsonBlock value={kg.parameters} />
                </section>
                <section>
                  <h3>Raw records</h3>
                  <JsonBlock value={kg.records} />
                </section>
                <section>
                  <h3>Raw nodes</h3>
                  <JsonBlock value={kg.nodes} />
                </section>
                <section>
                  <h3>Raw relationships</h3>
                  <JsonBlock value={kg.relationships} />
                </section>
              </div>
            </details>

            {kg.disclaimer && <p className="disclaimer">{kg.disclaimer}</p>}
          </section>
        )}
      </section>

      <style jsx global>{`
        * {
          box-sizing: border-box;
        }
        body {
          margin: 0;
          background: #f6f7f8;
          color: #17202a;
          font-family: Arial, "Tahoma", sans-serif;
        }
        main {
          min-height: 100vh;
          padding: 32px 16px;
        }
        .shell {
          width: min(980px, 100%);
          margin: 0 auto;
        }
        header {
          margin-bottom: 24px;
        }
        .navLink {
          display: inline-block;
          margin-bottom: 14px;
          color: #315948;
          font-weight: 700;
          text-decoration: none;
        }
        .navLink:hover {
          text-decoration: underline;
        }
        .eyebrow {
          margin: 0 0 8px;
          color: #54705f;
          font-size: 14px;
          font-weight: 700;
        }
        h1 {
          margin: 0;
          font-size: 40px;
          letter-spacing: 0;
        }
        h2 {
          margin: 0;
          font-size: 20px;
        }
        h3 {
          margin: 0;
          font-size: 17px;
          line-height: 1.7;
        }
        .subtitle {
          max-width: 760px;
          margin: 12px 0 0;
          line-height: 1.8;
          color: #45515d;
        }
        .askBox {
          background: #ffffff;
          border: 1px solid #dfe5e8;
          border-radius: 8px;
          padding: 20px;
        }
        label {
          display: block;
          margin-bottom: 8px;
          font-weight: 700;
        }
        textarea {
          width: 100%;
          resize: vertical;
          border: 1px solid #cfd8dc;
          border-radius: 6px;
          padding: 12px;
          font: inherit;
          line-height: 1.7;
          background: #fbfcfc;
        }
        textarea:focus {
          outline: 2px solid #8fb8a2;
          border-color: #54705f;
        }
        .actions {
          display: flex;
          justify-content: flex-start;
          margin-top: 12px;
        }
        button {
          border: 1px solid #8ca69a;
          border-radius: 6px;
          background: #ffffff;
          color: #17202a;
          padding: 10px 14px;
          font: inherit;
          cursor: pointer;
        }
        button:focus-visible,
        .details summary:focus-visible,
        .navLink:focus-visible {
          outline: 2px solid #8fb8a2;
          outline-offset: 2px;
        }
        .actions button {
          background: #315948;
          border-color: #315948;
          color: #ffffff;
          min-width: 150px;
        }
        button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .samples {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin: 14px 0 22px;
        }
        .error {
          border: 1px solid #e6a4a4;
          background: #fff3f3;
          color: #8a1f1f;
          border-radius: 6px;
          padding: 12px;
        }
        .loading {
          border: 1px solid #d6e3dd;
          background: #f3f8f5;
          color: #315948;
          border-radius: 6px;
          padding: 12px;
          line-height: 1.7;
        }
        .result {
          display: grid;
          gap: 16px;
        }
        .panel {
          border: 1px solid #e4e9eb;
          border-radius: 8px;
          padding: 16px;
          background: #fbfcfc;
        }
        .panelHeader {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }
        .rowBadge,
        .sectionCount {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 28px;
          border: 1px solid #d6e3dd;
          border-radius: 999px;
          background: #f3f8f5;
          color: #315948;
          padding: 4px 10px;
          font-size: 13px;
          font-weight: 700;
          white-space: nowrap;
        }
        .articleGrid,
        .cards,
        .relationships {
          display: grid;
          gap: 10px;
        }
        .articleCard,
        .card,
        .relationshipCard {
          border: 1px solid #e4e9eb;
          border-radius: 8px;
          padding: 14px;
          background: #ffffff;
          min-width: 0;
        }
        .articleHeader {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          margin-bottom: 8px;
        }
        .articleNumber {
          color: #315948;
          font-weight: 700;
        }
        .articleSummary,
        .cardText,
        .answer p,
        .emptyState p,
        .disclaimer {
          line-height: 1.8;
        }
        .articleSummary,
        .cardText {
          margin: 10px 0 0;
          color: #24313c;
          overflow-wrap: anywhere;
        }
        .answerText {
          white-space: pre-line;
          margin: 0;
          color: #24313c;
        }
        .backendAnswer {
          margin: 12px 0 0;
          color: #586772;
        }
        .textButton {
          margin-top: 8px;
          padding: 0;
          border: 0;
          background: transparent;
          color: #315948;
          font-weight: 700;
        }
        .referenceBlock {
          margin-top: 12px;
          border-top: 1px solid #eef2f3;
          padding-top: 10px;
        }
        .referenceBlock strong {
          color: #17202a;
        }
        .referenceBlock p {
          margin: 6px 0 0;
          color: #45515d;
          line-height: 1.7;
          overflow-wrap: anywhere;
        }
        .sourceName,
        .nodeType {
          margin: 10px 0 0;
          color: #586772;
          font-size: 14px;
          line-height: 1.6;
        }
        .metaList {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 10px;
          color: #586772;
          font-size: 14px;
        }
        .metaList span {
          border: 1px solid #e4e9eb;
          border-radius: 999px;
          padding: 4px 10px;
          background: #fbfcfc;
        }
        .relationshipLine {
          margin: 0;
          color: #24313c;
          line-height: 1.8;
          overflow-wrap: anywhere;
        }
        .relationshipLine span,
        .relationshipLine strong {
          margin-inline-end: 6px;
        }
        .propertyList {
          display: grid;
          gap: 8px;
          margin: 12px 0 0;
        }
        .propertyList div {
          display: grid;
          grid-template-columns: minmax(90px, 0.3fr) minmax(0, 1fr);
          gap: 10px;
        }
        .propertyList dt {
          color: #54705f;
          font-weight: 700;
        }
        .propertyList dd {
          margin: 0;
          color: #24313c;
          line-height: 1.7;
          overflow-wrap: anywhere;
        }
        .emptyState p {
          margin: 0;
          color: #586772;
        }
        .details {
          border: 1px solid #e4e9eb;
          border-radius: 8px;
          padding: 12px 14px;
          background: #ffffff;
        }
        .details summary {
          cursor: pointer;
          font-weight: 700;
          color: #315948;
        }
        .detailGrid {
          display: grid;
          gap: 14px;
          margin-top: 12px;
        }
        .detailGrid section {
          min-width: 0;
        }
        .detailGrid h3 {
          margin-bottom: 8px;
          font-size: 15px;
          color: #17202a;
        }
        pre {
          margin: 8px 0 0;
          max-width: 100%;
          overflow: auto;
          border: 1px solid #e4e9eb;
          border-radius: 6px;
          background: #f6f7f8;
          color: #24313c;
          padding: 10px;
          font-size: 13px;
          line-height: 1.5;
          text-align: left;
          white-space: pre-wrap;
          overflow-wrap: anywhere;
        }
        .disclaimer {
          margin: 0;
          border-top: 1px solid #e4e9eb;
          padding-top: 16px;
          color: #6b4b18;
        }
        .srOnly {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border: 0;
        }
        @media (max-width: 640px) {
          main {
            padding: 20px 12px;
          }
          h1 {
            font-size: 32px;
          }
          .askBox {
            padding: 16px;
          }
          .panelHeader {
            align-items: flex-start;
            flex-direction: column;
          }
          .propertyList div {
            grid-template-columns: 1fr;
            gap: 4px;
          }
        }
      `}</style>
    </main>
  );
}
