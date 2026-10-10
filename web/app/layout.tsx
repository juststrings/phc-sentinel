import type { Metadata } from "next";
import { Suspense } from "react";
import "./legacy.css";
import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";
import { api } from "@/lib/api";
import FacilitySearch from "@/components/FacilitySearch";
import MonthPicker from "@/components/MonthPicker";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "PHC Sentinel",
  description: "See risk before it becomes a shortage: operational risk x data confidence for Bauchi State PHCs.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [meta, st] = await Promise.all([api<any>("/meta/months"), api<any>("/meta/state")]);
  return (
    <html lang="en">
      {/* IBM Plex Sans loads from a runtime stylesheet link, so builds never depend on the network; the font stack falls back. */}
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" />
      </head>
      <body>
        <div className="banner" role="note">
          Demonstration: facility list and boundaries are real (GRID3). All operational reporting data are{" "}
          <strong>simulated</strong> and do not describe actual Bauchi facilities.
        </div>
        <div className="md:flex">
          <Suspense fallback={null}><Sidebar state={st.state} /></Suspense>
          <div className="min-w-0 flex-1">
            <header className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-card px-4 py-3 md:px-6">
              <div className="text-[14px] font-semibold text-ink">
                {st.state} State
                <span className="ml-2 text-[12px] font-normal text-ink-3">{st.lgas} LGAs · {st.facilities.toLocaleString()} PHCs</span>
              </div>
              <div className="ml-auto flex flex-wrap items-center gap-3">
                <Suspense fallback={null}><MonthPicker months={meta.months} latest={meta.latest} /></Suspense>
                <Suspense fallback={null}><FacilitySearch /></Suspense>
              </div>
            </header>
            <main className="p-4 md:p-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
