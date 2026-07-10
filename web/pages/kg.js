import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "ما المواد المرتبطة بإنهاء عقد العمل؟",
  "ما الموضوعات المرتبطة بالإجازة السنوية؟",
  "أي قانون يحتوي على مواد الفصل التعسفي؟",
];

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function JsonBlock({ value }) {
  return <pre dir="ltr">{JSON.stringify(value, null, 2)}</pre>;
}

export default function KGPage() {
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const answerText = typeof result?.answer === "string" ? result.answer : "";
  const generatedCypher = typeof result?.generated_cypher === "string" ? result.generated_cypher : "";
  const parameters = safeObject(result?.parameters);
  const records = Array.isArray(result?.records) ? result.records : [];
  const nodes = Array.isArray(result?.nodes) ? result.nodes : [];
  const relationships = Array.isArray(result?.relationships) ? result.relationships : [];
  const rowCount = Number.isInteger(result?.row_count) ? result.row_count : records.length;
  const disclaimer = typeof result?.disclaimer === "string" ? result.disclaimer : "";

  async function askQuestion(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/kg/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (!response.ok) {
        throw new Error(data.detail || "تعذر تنفيذ سؤال الرسم المعرفي.");
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
            rows={5}
            placeholder="اكتب سؤالك بالعربية..."
          />
          <div className="actions">
            <button type="submit" disabled={loading || question.trim().length < 2}>
              {loading ? "جارٍ السؤال..." : "اسأل الرسم المعرفي"}
            </button>
          </div>
        </form>

        <div className="samples">
          {sampleQuestions.map((sample) => (
            <button key={sample} type="button" onClick={() => setQuestion(sample)}>
              {sample}
            </button>
          ))}
        </div>

        {error && <p className="error">{error}</p>}
        {loading && <p className="loading">جارٍ توليد Cypher وتنفيذ الاستعلام على Neo4j...</p>}

        {result && (
          <section className="result">
            <div className="answer panel">
              <h2>الإجابة</h2>
              <p className="answerText">{answerText || "لا توجد إجابة متاحة."}</p>
              <p className="rowCount">عدد الصفوف: {rowCount}</p>
            </div>

            <div className="grid">
              <section className="panel">
                <h2>العُقد</h2>
                {nodes.length ? (
                  <div className="cards">
                    {nodes.map((node, index) => (
                      <article key={node.id || index} className="card">
                        <strong>{Array.isArray(node.labels) ? node.labels.join("، ") : "Node"}</strong>
                        <span>{node.id}</span>
                        <JsonBlock value={safeObject(node.properties)} />
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="mutedNotice">لا توجد عُقد في الاستجابة.</p>
                )}
              </section>

              <section className="panel">
                <h2>العلاقات</h2>
                {relationships.length ? (
                  <div className="cards">
                    {relationships.map((relationship, index) => (
                      <article key={relationship.id || index} className="card">
                        <strong>{relationship.type || "Relationship"}</strong>
                        <span>
                          {relationship.source} ← {relationship.target}
                        </span>
                        <JsonBlock value={safeObject(relationship.properties)} />
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="mutedNotice">لا توجد علاقات في الاستجابة.</p>
                )}
              </section>
            </div>

            <details className="details">
              <summary>تفاصيل الاستعلام والسجلات</summary>
              <div className="detailGrid">
                <section>
                  <h3>generated_cypher</h3>
                  <pre dir="ltr">{generatedCypher}</pre>
                </section>
                <section>
                  <h3>parameters</h3>
                  <JsonBlock value={parameters} />
                </section>
                <section>
                  <h3>records</h3>
                  <JsonBlock value={records} />
                </section>
              </div>
            </details>

            {disclaimer && <p className="disclaimer">{disclaimer}</p>}
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
          margin: 0 0 12px;
          font-size: 20px;
        }
        h3 {
          margin: 0 0 8px;
          font-size: 16px;
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
        .grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 16px;
        }
        .cards {
          display: grid;
          gap: 10px;
        }
        .card {
          border: 1px solid #e4e9eb;
          border-radius: 8px;
          padding: 12px;
          background: #ffffff;
          min-width: 0;
        }
        .card span {
          display: block;
          margin-top: 6px;
          color: #586772;
          overflow-wrap: anywhere;
        }
        .answer p,
        .disclaimer {
          line-height: 1.8;
        }
        .answerText {
          white-space: pre-line;
          margin: 0;
          color: #24313c;
        }
        .rowCount {
          color: #54705f;
          font-weight: 700;
          margin: 14px 0 0;
        }
        .mutedNotice {
          margin: 0;
          border: 1px solid #e4e9eb;
          border-radius: 8px;
          padding: 12px 14px;
          background: #ffffff;
          color: #586772;
          line-height: 1.7;
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
        }
        .disclaimer {
          margin: 0;
          border-top: 1px solid #e4e9eb;
          padding-top: 16px;
          color: #6b4b18;
        }
        @media (max-width: 760px) {
          .grid {
            grid-template-columns: 1fr;
          }
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
        }
      `}</style>
    </main>
  );
}
