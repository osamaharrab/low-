import Image from "next/image";
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="footer-brand">
          <span className="footer-brand__mark">
            <Image src="/brand/logo-icon.png" alt="" width={1254} height={1254} />
          </span>
          <p>
            <strong>Lawz AI JO</strong> is an experimental legal-tech platform providing information for general purposes only.
          </p>
        </div>
        <nav className="footer-links" aria-label="Footer navigation">
          <Link href="/">Home</Link>
          <Link href="/rag">Legal Assistant</Link>
          <Link href="/kg">Knowledge Graph</Link>
        </nav>
        <p className="site-footer__stack">RAG · Neo4j · Weaviate · FastAPI</p>
        <p className="site-footer__notice">Not legal advice. Verify with official legal sources or a qualified lawyer.</p>
      </div>
    </footer>
  );
}
