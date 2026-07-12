import StatusBadge from "./StatusBadge";

export default function PageHero({ eyebrow, title, description, badge, children, className = "" }) {
  return (
    <section className={`page-hero ${className}`.trim()}>
      <div className="page-hero__copy">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <div className="page-hero__title-row">
          <h1>{title}</h1>
          {badge && <StatusBadge tone="accent">{badge}</StatusBadge>}
        </div>
        {description && <p className="page-hero__description">{description}</p>}
      </div>
      {children && <div className="page-hero__actions">{children}</div>}
    </section>
  );
}
