import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/router";
import { useState } from "react";

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
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="brand" aria-label="Lawz AI JO home">
          <span className="brand__logo-frame brand__logo-frame--wide">
            <Image
              src="/brand/logo-horizontal.png"
              alt="Lawz AI JO - Jordanian Labour Law Assistant"
              width={2172}
              height={724}
              priority
            />
          </span>
          <span className="brand__logo-frame brand__logo-frame--compact">
            <Image src="/brand/logo-icon.png" alt="Lawz AI JO" width={1254} height={1254} priority />
          </span>
        </Link>

        <button
          type="button"
          className="menu-toggle"
          aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen((current) => !current)}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>

        <nav id="primary-navigation" className={menuOpen ? "site-nav is-open" : "site-nav"} aria-label="Primary navigation">
          {navigation.map((item) => {
            const active = isActivePath(router.pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? "site-nav__link is-active" : "site-nav__link"}
                aria-current={active ? "page" : undefined}
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
              </Link>
            );
          })}
          <span className="prototype-badge prototype-badge--mobile">Experimental</span>
        </nav>

        <span className="prototype-badge">Experimental</span>
      </div>
    </header>
  );
}
