"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { issues } from "@/lib/issues";

export function Masthead() {
  const pathname = usePathname();
  const picker = useRef<HTMLDetailsElement>(null);
  const trigger = useRef<HTMLElement>(null);
  const close = () => { if (picker.current) picker.current.open = false; };

  useEffect(() => { if (picker.current) picker.current.open = false; }, [pathname]);
  useEffect(() => {
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !picker.current?.contains(event.target)) close();
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape" && picker.current?.open) {
        close(); trigger.current?.focus();
      }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, []);

  return (
    <header className="masthead">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="masthead-folio">
          <details className="issue-picker" ref={picker} onBlur={event => {
            if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget as Node)) close();
          }}>
            <summary ref={trigger}>
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3 4.5h5.5L10 6l1.5-1.5H17v11h-5.5L10 17l-1.5-1.5H3zM10 6v11" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>
              <span>Browse issues</span>
              <svg className="issue-chevron" width="10" height="7" viewBox="0 0 10 7" fill="none" aria-hidden="true"><path d="m1 1 4 4 4-4" stroke="currentColor" strokeWidth="1.2"/></svg>
            </summary>
            <nav className="issue-picker-panel" aria-label="Issues">
              <div className="issue-picker-heading"><span>The journal</span><span>{String(issues.length).padStart(2, "0")} issues</span></div>
              {issues.map((issue, index) => (
                <Link key={issue.id} href={issue.href} prefetch={false} onClick={close} className="issue-picker-row" aria-current={pathname === issue.href || (pathname === "/" && index === 0) ? "page" : undefined}>
                  <span className={`issue-miniature ${index === 0 ? "is-latest" : ""}`} aria-hidden="true"><span>LS</span><b>{issue.id}</b></span>
                  <span className="min-w-0"><span className="issue-picker-kicker">Issue {issue.id}{index === 0 ? " · Latest" : ""}</span><span className="issue-picker-title">{issue.title}</span></span>
                  <span className="issue-picker-arrow" aria-hidden="true">↗</span>
                </Link>
              ))}
              <Link href="/issues" prefetch={false} onClick={close} className="issue-picker-all">View the issue archive <span aria-hidden="true">→</span></Link>
            </nav>
          </details>
          <p className="masthead-note">Music, read closely.</p>
        </div>
        <Link href="/" className="masthead-wordmark" aria-label="LyricStats — front page">LyricStats</Link>
        <nav className="masthead-nav" aria-label="Main navigation">
          {[
            {href: "/", label: "Journal", active: pathname === "/" || pathname.startsWith("/issues")},
            {href: "/song", label: "Songs", active: pathname === "/song"},
            {href: "/artist", label: "Artists", active: pathname === "/artist"},
          ].map(item => <Link key={item.href} href={item.href} prefetch={false} data-active={item.active} aria-current={pathname === item.href ? "page" : undefined}>{item.label}</Link>)}
        </nav>
      </div>
    </header>
  );
}
