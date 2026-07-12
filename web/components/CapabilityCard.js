import Link from "next/link";

function CapabilityIcon({ type }) {
  if (type === "kg") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="6" cy="7" r="2.5" />
        <circle cx="18" cy="7" r="2.5" />
        <circle cx="12" cy="17" r="2.5" />
        <path d="M8.2 8.6 10.7 15M15.8 8.6 13.3 15M8.5 7h7" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5 5.75A2.75 2.75 0 0 1 7.75 3h8.5A2.75 2.75 0 0 1 19 5.75v12.5A2.75 2.75 0 0 1 16.25 21h-8.5A2.75 2.75 0 0 1 5 18.25Z" />
      <path d="M8.5 8h7M8.5 12h7M8.5 16h4" />
    </svg>
  );
}

export default function CapabilityCard({ href, title, label, description, features, action, icon = "rag" }) {
  return (
    <Link href={href} className={`capability-card capability-card--${icon}`}>
      <span className="capability-card__icon">
        <CapabilityIcon type={icon} />
      </span>
      <span className="capability-card__label">{label}</span>
      <span className="capability-card__title">{title}</span>
      <span className="capability-card__description">{description}</span>
      <span className="capability-card__features">
        {features.map((feature) => (
          <span key={feature}>{feature}</span>
        ))}
      </span>
      <span className="capability-card__action">
        {action}
        <span aria-hidden="true">→</span>
      </span>
    </Link>
  );
}
