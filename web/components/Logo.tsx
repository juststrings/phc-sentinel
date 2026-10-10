import Link from "next/link";

/** Brand mark used by briefing mode (styled by legacy.css). The app shell has its own brand block in Sidebar. */
export function Logo() {
  return (
    <Link href="/" className="logo" aria-label="PHC Sentinel home">
      <span className="logo-mark" aria-hidden>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z" /><path d="M12 8v6M9 11h6" />
        </svg>
      </span>
      <span>PHC Sentinel<small>Early warning for primary health care</small></span>
    </Link>
  );
}
