export default function LoadingState({ message }) {
  return (
    <section className="state-card state-card--loading" role="status" aria-live="polite" aria-busy="true">
      <span className="loading-mark" aria-hidden="true" />
      <p>{message}</p>
    </section>
  );
}
