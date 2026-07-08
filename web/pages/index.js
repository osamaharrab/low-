import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const sampleQuestions = [
  "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "ما المقصود بالفصل التعسفي؟",
  "ما حقوق العامل في الإجازة السنوية؟",
  "هل يجوز الخصم من أجر العامل؟",
];

export default function Home() {
  const [question, setQuestion] = useState(sampleQuestions[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function askQuestion(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/rag/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, k: 5 }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "تعذر الحصول على إجابة.");
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
          <p className="eyebrow">مساعد معلوماتي مبني على RAG</p>
          <h1>Lawz AI JO</h1>
          <p className="subtitle">
            مساعد عربي مبسط لأسئلة قانون العمل الأردني، يعتمد على استرجاع النصوص القانونية ثم توليد إجابة
            موثقة بالمراجع المسترجعة.
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
              {loading ? "جارٍ السؤال..." : "اسأل"}
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

        {result && (
          <section className="result">
            <div className="answer">
              <h2>الإجابة</h2>
              <p>{result.answer}</p>
              <p className="confidence">الثقة: {Math.round((result.confidence || 0) * 100)}%</p>
            </div>

            <div>
              <h2>المراجع</h2>
              {result.citations?.length ? (
                <ul>
                  {result.citations.map((citation) => (
                    <li key={citation.chunk_id}>
                      <strong>{citation.topic}</strong>
                      <span>{citation.reference}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>لا توجد مراجع مسترجعة.</p>
              )}
            </div>

            <div>
              <h2>النصوص المسترجعة</h2>
              {result.retrieved_chunks?.map((chunk) => (
                <article key={chunk.chunk_id} className="chunk">
                  <div>
                    <strong>{chunk.topic}</strong>
                    <span>{chunk.reference}</span>
                  </div>
                  <p>{chunk.text_preview}</p>
                </article>
              ))}
            </div>

            <p className="disclaimer">{result.disclaimer}</p>
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
        .subtitle {
          max-width: 760px;
          margin: 12px 0 0;
          line-height: 1.8;
          color: #45515d;
        }
        .askBox,
        .result {
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
          min-width: 96px;
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
        .result {
          display: grid;
          gap: 22px;
        }
        .answer p,
        .chunk p,
        .disclaimer {
          line-height: 1.8;
        }
        .confidence {
          color: #54705f;
          font-weight: 700;
        }
        ul {
          margin: 0;
          padding: 0;
          list-style: none;
          display: grid;
          gap: 10px;
        }
        li,
        .chunk {
          border: 1px solid #e4e9eb;
          border-radius: 8px;
          padding: 12px;
          background: #fbfcfc;
        }
        li span,
        .chunk span {
          display: block;
          margin-top: 6px;
          color: #586772;
          line-height: 1.6;
        }
        .disclaimer {
          margin: 0;
          border-top: 1px solid #e4e9eb;
          padding-top: 16px;
          color: #6b4b18;
        }
        @media (max-width: 640px) {
          main {
            padding: 20px 12px;
          }
          h1 {
            font-size: 32px;
          }
          .askBox,
          .result {
            padding: 16px;
          }
        }
      `}</style>
    </main>
  );
}
