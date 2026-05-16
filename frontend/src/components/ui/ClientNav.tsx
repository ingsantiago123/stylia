"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "Documentos", exact: true },
  { href: "/costs", label: "Costos", exact: false },
  { href: "/audit", label: "Auditoría", exact: false },
  { href: "/profiles/studio", label: "Studio", exact: false },
];

export function ClientNav() {
  const pathname = usePathname();

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  return (
    <nav className="flex items-center gap-0.5" aria-label="Navegación principal">
      {NAV_LINKS.map((link) => {
        const active = isActive(link.href, link.exact);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={[
              "relative px-3 py-1.5 text-sm rounded-lg transition-all duration-150 font-medium",
              active
                ? "text-krypton"
                : "text-plomo hover:text-bruma hover:bg-surface-hover",
            ].join(" ")}
          >
            {link.label}
            {active && (
              <span className="absolute bottom-0.5 left-3 right-3 h-px bg-krypton rounded-full" />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
