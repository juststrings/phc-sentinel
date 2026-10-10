import type { Metadata, Viewport } from "next";
import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";

export const metadata: Metadata = {
  title: { default: "PHC Sentinel", template: "%s · PHC Sentinel" },
  description: "See risk before it becomes a shortage: operational risk x data confidence for primary health care in 12 Nigerian states.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

/** The simulated-data banner sits in the root layout, so it is on every page:
 * landing, national map, state briefs, briefing mode, state portals and facility pages. */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* IBM Plex Sans loads from a runtime stylesheet link, so builds never depend on the network; the font stack falls back. */}
      <head>
        {/* Apply a saved theme choice before first paint, so there is no flash. */}
        <script dangerouslySetInnerHTML={{ __html: "try{var t=localStorage.getItem('phc-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}if(window.name==='phc-modal')document.documentElement.dataset.embed='1'" }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" />
      </head>
      <body>
        <div className="banner" role="note" aria-label="Data notice">
          <span className="chip">All operational data simulated</span>
          <span className="long">
            Facility lists and boundaries are real (GRID3 v3.0). Reporting, stock and service figures are{" "}
            <strong>simulated</strong> and do not describe actual facilities.
          </span>
          <span className="short">Facility lists are real (GRID3); all figures are simulated.</span>
        </div>
        {children}
      </body>
    </html>
  );
}
