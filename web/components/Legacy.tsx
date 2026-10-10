/** Wrapper for pages that still use the older class-based styles (legacy.css, scoped to `.legacy`):
 *  the landing page, National Command Centre, briefing mode and the not-found page. */
export default function Legacy({ children }: { children: React.ReactNode }) {
  return <div className="legacy" style={{ maxWidth: 1360, margin: "0 auto" }}>{children}</div>;
}
