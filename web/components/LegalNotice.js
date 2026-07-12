const fallbackDisclaimer = [
  "This tool provides an initial explanation for general informational purposes only. It is not legal advice and does not replace reviewing the official legal text or consulting a qualified lawyer.",
  "هذه الأداة تقدم شرحاً أولياً لأغراض المعلومات العامة فقط، ولا تُعد استشارة قانونية ولا تغني عن مراجعة النص القانوني الرسمي أو محامٍ مختص.",
];

function hasArabic(value) {
  return /[\u0600-\u06FF]/.test(value);
}

export default function LegalNotice({ disclaimer }) {
  const messages = typeof disclaimer === "string" && disclaimer.trim() ? [disclaimer.trim()] : fallbackDisclaimer;

  return (
    <aside className="legal-notice" aria-label="Legal notice">
      <h2>Legal notice</h2>
      {messages.map((message) => (
        <p key={message} dir={hasArabic(message) ? "rtl" : "ltr"} lang={hasArabic(message) ? "ar" : "en"}>
          {message}
        </p>
      ))}
    </aside>
  );
}
