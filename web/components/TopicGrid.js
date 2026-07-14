const topics = [
  "Termination of Employment",
  "Working Hours and Rest",
  "Leave and Holidays",
  "Wages and Benefits",
  "Disciplinary Rules",
  "Contracts and Obligations",
];

function TopicIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M6 4h12v15.5A1.5 1.5 0 0 1 16.5 21h-9A1.5 1.5 0 0 1 6 19.5Z" />
      <path d="M8.5 8h7M8.5 11.5h7M8.5 15h4" />
    </svg>
  );
}

export default function TopicGrid() {
  return (
    <section className="topics-section" aria-labelledby="topics-title">
      <div className="section-heading-row">
        <h2 id="topics-title">Explore by topic</h2>
        <span>Current project scope</span>
      </div>
      <div className="topic-grid">
        {topics.map((topic) => (
          <div className="topic-card" key={topic}>
            <span>
              <TopicIcon />
            </span>
            <strong>{topic}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
