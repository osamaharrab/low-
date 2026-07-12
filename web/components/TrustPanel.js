const trustItems = [
  "Source-grounded answers",
  "Visible legal references",
  "Inspectable results",
  "Responsible legal disclaimer",
];

export default function TrustPanel() {
  return (
    <section className="trust-panel" aria-labelledby="trust-title">
      <div>
        <p className="section-kicker">Trust and responsibility</p>
        <h2 id="trust-title">Built for inspection, not blind reliance</h2>
        <p>
          Lawz AI JO provides an initial informational explanation. It is not legal advice and does not replace reviewing
          official legal text or consulting a qualified lawyer.
        </p>
      </div>
      <div className="trust-panel__grid">
        {trustItems.map((item) => (
          <div className="trust-panel__item" key={item}>
            <span aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M12 3 19 6v5c0 4.4-2.8 8.3-7 9.7C7.8 19.3 5 15.4 5 11V6Z" />
                <path d="m9.2 12 1.9 1.9 3.9-4.2" />
              </svg>
            </span>
            <strong>{item}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
