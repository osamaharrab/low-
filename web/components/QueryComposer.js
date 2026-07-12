export default function QueryComposer({
  id,
  value,
  onChange,
  onSubmit,
  label,
  placeholder,
  helperText,
  submitLabel,
  loadingLabel,
  loading = false,
  suggestions = [],
  onSuggestionSelect,
  minLength = 2,
}) {
  const trimmedValue = value.trim();
  const submitDisabled = loading || trimmedValue.length < minLength;
  const helperId = `${id}-help`;

  return (
    <section className="query-panel" aria-busy={loading ? "true" : "false"}>
      <form onSubmit={onSubmit} className="query-form">
        <label htmlFor={id}>{label}</label>
        <textarea
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          rows={5}
          placeholder={placeholder}
          aria-describedby={helperId}
          dir="auto"
          className="legal-input"
        />
        <div className="query-form__footer">
          <p id={helperId} className="query-form__help">
            {helperText}
          </p>
          <button type="submit" className="button button--primary" disabled={submitDisabled}>
            {loading ? loadingLabel : submitLabel}
          </button>
        </div>
      </form>

      {suggestions.length > 0 && (
        <div className="suggestion-list" aria-label="Suggested legal questions">
          {suggestions.map((sample) => (
            <button key={sample} type="button" className="suggestion-chip" onClick={() => onSuggestionSelect?.(sample)} disabled={loading} dir="rtl" lang="ar">
              {sample}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
