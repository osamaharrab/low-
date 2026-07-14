export default function StatusBadge({ children, tone = "neutral", className = "" }) {
  return <span className={`status-badge status-badge--${tone} ${className}`.trim()}>{children}</span>;
}
