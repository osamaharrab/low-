import Footer from "./Footer";
import Header from "./Header";

export default function AppShell({ children }) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Header />
      <main id="main-content" className="site-main">
        {children}
      </main>
      <Footer />
    </div>
  );
}
