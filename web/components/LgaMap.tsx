"use client";
import maplibregl from "maplibre-gl";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";

import { QUEUE_BY_TAG } from "@/lib/tokens";

const TAG_HEX: Record<string, string> = Object.fromEntries(Object.entries(QUEUE_BY_TAG).map(([t, s]) => [t, s.hex]));
// Sequential ramp (light to deep red) for the Act now share of each LGA.
const SEQ = ["#fee2e2", "#fecaca", "#fca5a5", "#f87171", "#dc2626", "#991b1b"];

function bbox(fc: any): [number, number, number, number] {
  let [x0, y0, x1, y1] = [180, 90, -180, -90];
  const walk = (c: any) => {
    if (typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); y0 = Math.min(y0, c[1]); x1 = Math.max(x1, c[0]); y1 = Math.max(y1, c[1]);
    } else c.forEach(walk);
  };
  fc.features.forEach((f: any) => walk(f.geometry.coordinates));
  return [x0, y0, x1, y1];
}

export default function LgaMap({ lgas: rawLgas, facilities, month, focusLga }: {
  lgas: any; facilities: any; month: string; focusLga?: string;
}) {
  // Shade by the share of each LGA's PHCs that are Act now.
  const lgas = useMemo(() => ({
    ...rawLgas,
    features: rawLgas.features.map((f: any) => ({
      ...f, properties: { ...f.properties, act_share: f.properties.facilities ? (f.properties.act_now ?? 0) / f.properties.facilities : 0 },
    })),
  }), [rawLgas]);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!ref.current) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const vals = lgas.features.map((f: any) => f.properties.act_share ?? 0);
    const max = Math.max(1, ...vals);
    const stops = SEQ.flatMap((c, i) => [(max * i) / (SEQ.length - 1), c]);
    const surface = dark ? "#111a2e" : "#ffffff";
    const bounds = bbox(focusLga ? { features: lgas.features.filter((f: any) => f.properties.lga_id === focusLga) } : lgas);
    const map = new maplibregl.Map({
      container: ref.current,
      // Sources and layers are inline in the style, so nothing waits on a load event.
      style: {
        version: 8,
        sources: { lgas: { type: "geojson", data: lgas }, fac: { type: "geojson", data: facilities } },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": surface } },
          {
            id: "lga-fill", type: "fill", source: "lgas",
            paint: {
              "fill-color": ["interpolate", ["linear"], ["coalesce", ["get", "act_share"], 0], ...stops] as any,
              "fill-opacity": focusLga ? ["case", ["==", ["get", "lga_id"], focusLga], 0.55, 0.15] as any : 0.75,
            },
          },
          { id: "lga-line", type: "line", source: "lgas", paint: { "line-color": surface, "line-width": 1.5 } },
          {
            id: "fac", type: "circle", source: "fac",
            paint: {
              "circle-radius": focusLga ? 5 : 2.6,
              "circle-color": ["match", ["get", "tag"], ...Object.entries(TAG_HEX).flat(), "#898781"] as any,
              "circle-stroke-color": surface,
              "circle-stroke-width": focusLga ? 1.5 : 0.6,
            },
          },
        ],
      },
      bounds,
      fitBoundsOptions: { padding: 24 },
      attributionControl: { customAttribution: "Boundaries & facilities: GRID3 (CC BY 4.0)" },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    // The container can settle after construction (grid layout); re-fit once it has.
    const fit = () => { map.resize(); map.fitBounds(bounds, { padding: 24, animate: false }); };
    map.once("load", fit);
    const ro = new ResizeObserver(fit);
    ro.observe(ref.current);
    {
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      map.on("mousemove", "fac", (e) => {
        const p: any = e.features?.[0]?.properties;
        if (!p) return;
        map.getCanvas().style.cursor = "pointer";
        popup.setLngLat(e.lngLat).setHTML(`<strong>${p.name}</strong><br/>${p.tag}`).addTo(map);
      });
      map.on("mouseleave", "fac", () => { popup.remove(); map.getCanvas().style.cursor = ""; });
      map.on("click", "fac", (e) => {
        const p: any = e.features?.[0]?.properties;
        if (p) router.push(`/facility/${p.facility_id}?month=${month}`);
      });
      if (!focusLga) {
        map.on("mousemove", "lga-fill", (e) => {
          if (map.queryRenderedFeatures(e.point, { layers: ["fac"] }).length) return;
          const p: any = e.features?.[0]?.properties;
          if (!p) return;
          map.getCanvas().style.cursor = "pointer";
          popup.setLngLat(e.lngLat).setHTML(
            `<strong>${p.lga}</strong><br/>${p.act_now} act now · ${p.verify_then_act} verify then act<br/>${p.facilities} PHCs`).addTo(map);
        });
        map.on("mouseleave", "lga-fill", () => { popup.remove(); map.getCanvas().style.cursor = ""; });
        map.on("click", "lga-fill", (e) => {
          if (map.queryRenderedFeatures(e.point, { layers: ["fac"] }).length) return;
          const p: any = e.features?.[0]?.properties;
          if (p) router.push(`/lga/${p.lga_id}?month=${month}`);
        });
      }
    }
    return () => { ro.disconnect(); map.remove(); };
  }, [lgas, facilities, month, focusLga, router]);

  const max = Math.max(0, ...lgas.features.map((f: any) => f.properties.act_share ?? 0));
  return (
    <div>
      <div ref={ref} className="h-[520px] w-full overflow-hidden rounded border border-line" role="img" aria-label="Map of LGAs shaded by share of Act now facilities" />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12px] text-ink-2">
        {!focusLga && (
          <span className="flex items-center gap-2">
            Act now share of PHCs
            <span className="flex">{SEQ.map((c) => <i key={c} style={{ background: c, width: 18, height: 10, display: "inline-block" }} />)}</span>
            <span className="tabular-nums">0%–{Math.round(max * 100)}%</span>
          </span>
        )}
        <span className="flex gap-3">
          {Object.entries(QUEUE_BY_TAG).map(([t, q]) => (
            <span key={t} className="flex items-center gap-1">
              <i style={{ background: q.hex, width: 8, height: 8, borderRadius: "50%", display: "inline-block" }} />{q.label}
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}
