export default function LoadingState({ message }) {
  return (
    <section className="state-card state-card--loading" role="status" aria-live="polite" aria-busy="true">
      <span className="loading-mark" aria-hidden="true" />
      <div className="loading-copy">
        <p>{message}</p>
        <span className="loading-skeleton" aria-hidden="true" />
      </div>
    </section>
  );
}
