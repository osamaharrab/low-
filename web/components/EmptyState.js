export default function EmptyState({ title = "No results", message, children }) {
  return (
    <section className="state-card state-card--empty">
      <div>
        <h2>{title}</h2>
        {message && <p>{message}</p>}
      </div>
      {children}
    </section>
  );
}
