import Link from "next/link";
import { useRouter } from "next/router";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/rag", label: "Legal Assistant" },
  { href: "/kg", label: "Knowledge Graph" },
];

function isActivePath(pathname, href) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Header() {
  const router = useRouter();

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="brand" aria-label="Lawz AI JO home">
          <span className="brand__mark" aria-hidden="true">
            L
          </span>
          <span>
            <span className="brand__name">Lawz AI JO</span>
            <span className="brand__descriptor" dir="rtl" lang="ar">
              مساعد قانون العمل الأردني
            </span>
          </span>
        </Link>

        <nav className="site-nav" aria-label="Primary navigation">
          {navigation.map((item) => {
            const active = isActivePath(router.pathname, item.href);
            return (
              <Link key={item.href} href={item.href} className={active ? "site-nav__link is-active" : "site-nav__link"} aria-current={active ? "page" : undefined}>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <span className="prototype-badge">Experimental</span>
      </div>
    </header>
  );
}
