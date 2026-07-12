const steps = [
  {
    title: "Enter a legal question",
    description: "Ask in Arabic or English about Jordanian labour law.",
    icon: "message",
  },
  {
    title: "Retrieve evidence and graph relationships",
    description: "Use grounded retrieval and connected legal data.",
    icon: "database",
  },
  {
    title: "Review results and references",
    description: "Verify answers, citations, evidence, and graph records.",
    icon: "review",
  },
  {
    title: "Make an informed decision",
    description: "Use the output as informational support, not legal advice.",
    icon: "shield",
  },
];

function StepIcon({ type }) {
  if (type === "database") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <ellipse cx="12" cy="5" rx="7" ry="3" />
        <path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />
        <path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      </svg>
    );
  }
  if (type === "review") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M6 3h8l4 4v14H6Z" />
        <path d="M13 3v5h5M8.5 13h4M8.5 16h3" />
        <circle cx="16.5" cy="15.5" r="2.2" />
        <path d="m18 17 2 2" />
      </svg>
    );
  }
  if (type === "shield") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M12 3 19 6v5c0 4.4-2.8 8.3-7 9.7C7.8 19.3 5 15.4 5 11V6Z" />
        <path d="m9.3 12 1.8 1.8 3.8-4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H11l-4.5 4v-4A2.5 2.5 0 0 1 4 13.5Z" />
      <path d="M8 7.5h8M8 11h5" />
    </svg>
  );
}

export default function HowItWorks() {
  return (
    <section className="how-section" aria-labelledby="workflow-title">
      <h2 id="workflow-title">How it works</h2>
      <div className="workflow-grid">
        {steps.map((step, index) => (
          <article className="workflow-step" key={step.title}>
            <span className="workflow-step__number">{index + 1}</span>
            <span className="workflow-step__icon">
              <StepIcon type={step.icon} />
            </span>
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
