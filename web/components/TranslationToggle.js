import { useEffect, useMemo, useState } from "react";

const UNAVAILABLE_MESSAGE = "Translation is temporarily unavailable.";

export default function TranslationToggle({ text, apiUrl, className = "" }) {
  const sourceText = useMemo(() => (typeof text === "string" ? text.trim() : ""), [text]);
  const [translatedText, setTranslatedText] = useState("");
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setTranslatedText("");
    setVisible(false);
    setLoading(false);
    setError("");
  }, [sourceText]);

  if (!sourceText) {
    return null;
  }

  async function requestTranslation() {
    if (loading) {
      return;
    }

    if (translatedText) {
      setVisible(true);
      setError("");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${apiUrl}/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: sourceText }),
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok || typeof data.translated_text !== "string" || !data.translated_text.trim()) {
        throw new Error(UNAVAILABLE_MESSAGE);
      }

      setTranslatedText(data.translated_text.trim());
      setVisible(true);
    } catch {
      setError(UNAVAILABLE_MESSAGE);
    } finally {
      setLoading(false);
    }
  }

  function toggleTranslation() {
    if (loading) {
      return;
    }
    if (visible) {
      setVisible(false);
      return;
    }
    requestTranslation();
  }

  const buttonLabel = loading
    ? "Translating..."
    : visible
      ? "Hide translation"
      : translatedText
        ? "Show English translation"
        : "Translate to English";

  return (
    <div className={`translation-toggle ${className}`.trim()}>
      <button type="button" className="result-action-button" onClick={toggleTranslation} disabled={loading}>
        {buttonLabel}
      </button>

      {error && (
        <div className="translation-message translation-message--error" role="status">
          <span>{error}</span>
          <button type="button" className="text-button" onClick={requestTranslation} disabled={loading}>
            Retry
          </button>
        </div>
      )}

      {visible && translatedText && (
        <section className="translation-panel" lang="en" dir="ltr">
          <h3>English Translation</h3>
          <p>{translatedText}</p>
          <small>Machine-generated translation. The Arabic response remains the authoritative version.</small>
        </section>
      )}
    </div>
  );
}
