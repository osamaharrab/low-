export default function ErrorState({ title = "Request failed", message, onRetry, retryLabel = "Retry" }) {
  return (
    <section className="state-card state-card--error" role="alert">
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </section>
  );
}
