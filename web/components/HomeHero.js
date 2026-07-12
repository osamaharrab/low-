import Link from "next/link";

const indicators = [
  "Source-grounded answers",
  "Clear legal references",
  "Inspectable relationships",
  "Responsible legal AI",
];

function IndicatorIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 3 19 6v5c0 4.4-2.8 8.3-7 9.7C7.8 19.3 5 15.4 5 11V6Z" />
      <path d="m9.2 12 1.9 1.9 3.9-4.2" />
    </svg>
  );
}

export default function HomeHero() {
  return (
    <section className="home-hero" aria-labelledby="home-hero-title">
      <div className="network-pattern" aria-hidden="true" />
      <div className="home-hero__inner">
        <div className="home-hero__copy">
          <p className="home-hero__eyebrow">Experimental Legal-Tech Platform</p>
          <h1 id="home-hero-title">
            <span className="headline-line">Understand Jordanian</span>
            <span className="headline-line">
              Labour Law with <span className="headline-highlight">clarity</span>
            </span>
          </h1>
          <p className="home-hero__description">
            Lawz AI JO combines source-grounded semantic retrieval with a knowledge graph for exploring Jordanian labour-law
            articles and relationships.
          </p>
          <div className="home-hero__actions">
            <Link href="/rag" className="button button--primary button--hero">
              <span className="button__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H11l-4.5 4v-4A2.5 2.5 0 0 1 4 13.5Z" />
                  <path d="M8 7h8M8 10.5h5" />
                </svg>
              </span>
              Open Legal Assistant
              <span aria-hidden="true">→</span>
            </Link>
            <Link href="/kg" className="button button--outline-dark button--hero">
              <span className="button__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <circle cx="6" cy="7" r="2.4" />
                  <circle cx="18" cy="7" r="2.4" />
                  <circle cx="12" cy="17" r="2.4" />
                  <path d="M8.2 8.7 10.8 15M15.8 8.7 13.2 15M8.5 7h7" />
                </svg>
              </span>
              Explore Knowledge Graph
              <span aria-hidden="true">→</span>
            </Link>
          </div>
          <div className="hero-indicators" aria-label="Platform trust indicators">
            {indicators.map((item) => (
              <div className="hero-indicator" key={item}>
                <span>
                  <IndicatorIcon />
                </span>
                <strong>{item}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="home-hero__image" aria-label="Amman Citadel at sunset">
          <img src="/images/amman-citadel-hero.jpg" alt="Amman Citadel at sunset" width="1672" height="941" loading="eager" />
        </div>
      </div>
    </section>
  );
}
