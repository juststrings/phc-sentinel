"use client";
import { useTheme } from "@/components/useTheme";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { METRICS, pct, int } from "@/lib/api";
import { StatusPill } from "@/components/Tags";

/* Sequential single-hue ramp (blue), 5 classes. Light mode: light -> dark = less -> more attention.
 * Dark mode is its own selection: dark -> light, so "more attention" is the brighter fill. */
const RAMP_LIGHT = ["#b7d3f6", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"];   // step 150 first: stays distinct from the "Not in demo" grey
const RAMP_DARK = ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"];
const NIGERIA: [number, number, number, number] = [2.67, 4.27, 14.68, 13.89];

export type Bins = { edges: number[]; ramp: string[] };

/** Equal-interval classes on the "attention" scale, so darker always means more attention.
 * For completeness (higher is better) the scale runs high -> low. */
export function makeBins(values: number[], worse: boolean, dark: boolean): Bins {
  const ramp = dark ? RAMP_DARK : RAMP_LIGHT;
  const v = values.filter((x) => x != null && !Number.isNaN(x));
  let lo = Math.min(...v), hi = Math.max(...v);
  const step = 0.01;
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  if (hi - lo < 0.05) { lo = Math.max(0, lo - 0.025); hi = lo + 0.05; }
  const edges = Array.from({ length: ramp.length + 1 }, (_, i) => lo + ((hi - lo) * i) / ramp.length);
  return { edges: worse ? edges : [...edges].reverse(), ramp };
}

export function binIndex(v: number, bins: Bins, worse: boolean) {
  const e = bins.edges, n = bins.ramp.length;
  for (let i = 0; i < n; i++) {
    const a = e[i], b = e[i + 1];
    if (worse ? v <= b + 1e-9 : v >= b - 1e-9) return i;
  }
  return n - 1;
}

function ringArea(r: number[][]) {
  let a = 0;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) a += (r[j][0] + r[i][0]) * (r[j][1] - r[i][1]);
  return a / 2;
}
function labelPoint(geom: any): [number, number] {
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  let best = polys[0], ba = 0;
  for (const p of polys) { const a = Math.abs(ringArea(p[0])); if (a > ba) { ba = a; best = p; } }
  const r = best[0];
  let x = 0, y = 0, A = 0;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const f = r[j][0] * r[i][1] - r[i][0] * r[j][1];
    x += (r[j][0] + r[i][0]) * f; y += (r[j][1] + r[i][1]) * f; A += f;
  }
  return A ? [x / (3 * A), y / (3 * A)] : [r[0][0], r[0][1]];
}

function useDark() {
  return useTheme() === "dark";   // follows the theme toggle and the system setting
}

export default function NationalMap({ geo, states, metric, selected, onSelect, height, showLabels = true }: {
  geo: any; states: any[]; metric: string; selected?: string | null; onSelect?: (code: string) => void;
  height?: number; showLabels?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const dark = useDark();
  const [tip, setTip] = useState<{ x: number; y: number; code: string | null; name: string } | null>(null);
  const m = METRICS.find((x) => x.key === metric)!;
  const byCode = useMemo(() => Object.fromEntries(states.map((s) => [s.state_code, s])), [states]);
  const bins = useMemo(() => makeBins(states.map((s) => s[metric]), m.worse, dark), [states, metric, m.worse, dark]);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const data = useMemo(() => ({
    ...geo,
    features: geo.features.map((f: any, i: number) => {
      const s = f.properties.state_code ? byCode[f.properties.state_code] : null;
      const v = s ? s[metric] : null;
      const bi = v == null ? -1 : binIndex(v, bins, m.worse);
      return { ...f, id: i, properties: { ...f.properties, covered: !!s, fill: bi >= 0 ? bins.ramp[bi] : null, bin: bi } };
    }),
  }), [geo, byCode, metric, bins, m.worse]);

  // Create the map once per theme. Construction waits until the page has laid out and
  // fonts are ready: the map then starts at its final size instead of resizing mid-load.
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true;
    const go = () => requestAnimationFrame(() => alive && setReady(true));
    (document as any).fonts?.ready ? (document as any).fonts.ready.then(go) : go();
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!ref.current || !ready) return;
    const css = getComputedStyle(document.documentElement);
    const surface = css.getPropertyValue("--surface-1").trim() || "#fcfcfb";
    const nodata = css.getPropertyValue("--nodata").trim() || "#e4e3dd";
    const nodataLine = css.getPropertyValue("--nodata-line").trim() || "#cfcdc5";
    const text = css.getPropertyValue("--text-primary").trim() || "#0b0b0b";
    const map = new maplibregl.Map({
      container: ref.current,
      style: {
        version: 8,
        sources: { st: { type: "geojson", data } },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": surface } },
          { id: "fill", type: "fill", source: "st", paint: {
            "fill-color": ["case", ["get", "covered"], ["get", "fill"], nodata] as any,
            "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.85, 1] as any } },
          { id: "line", type: "line", source: "st", paint: {
            "line-color": ["case", ["get", "covered"], surface, nodataLine] as any, "line-width": ["case", ["get", "covered"], 1.6, 0.8] as any } },
          { id: "hover", type: "line", source: "st", paint: {
            "line-color": text, "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 1.6, 0] as any } },
          { id: "sel", type: "line", source: "st", filter: ["==", ["get", "state_code"], "__none__"], paint: { "line-color": text, "line-width": 3 } },
        ],
      },
      bounds: NIGERIA,
      fitBoundsOptions: { padding: 20 },
      dragRotate: false, pitchWithRotate: false, touchPitch: false, scrollZoom: false,
      preserveDrawingBuffer: true,   // lets the map print (briefing mode) and appear in screenshots
      attributionControl: { customAttribution: "Boundaries: GRID3 (CC BY 4.0)" },
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    let hovered: number | null = null;
    const setHover = (id: number | null) => {
      if (hovered != null) map.setFeatureState({ source: "st", id: hovered }, { hover: false });
      hovered = id;
      if (id != null) map.setFeatureState({ source: "st", id }, { hover: true });
    };
    map.on("mousemove", "fill", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      setHover(f.id as number);
      map.getCanvas().style.cursor = f.properties.covered ? "pointer" : "default";
      setTip({ x: e.point.x, y: e.point.y, code: f.properties.covered ? f.properties.state_code : null, name: f.properties.name });
    });
    map.on("mouseleave", "fill", () => { setHover(null); setTip(null); map.getCanvas().style.cursor = ""; });
    map.on("click", "fill", (e) => {
      const p: any = e.features?.[0]?.properties;
      if (p?.covered && onSelectRef.current) onSelectRef.current(p.state_code);
    });
    const fit = () => { map.resize(); map.fitBounds(NIGERIA, { padding: 20, animate: false }); };
    map.once("load", fit);
    const ro = new ResizeObserver(fit);
    ro.observe(ref.current);
    mapRef.current = map;
    return () => { ro.disconnect(); markers.current.forEach((mk) => mk.remove()); map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark, ready]);

  // Data, selection and labels follow props without rebuilding the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      (map.getSource("st") as maplibregl.GeoJSONSource)?.setData(data);
      map.setFilter("sel", ["==", ["get", "state_code"], selected ?? "__none__"]);
      markers.current.forEach((mk) => mk.remove());
      markers.current = [];
      if (!showLabels) return;
      for (const f of data.features) {
        if (!f.properties.covered) continue;
        const s = byCode[f.properties.state_code];
        const el = document.createElement("div");
        el.className = "map-label" + (f.properties.bin >= 3 !== dark ? " dark" : "");
        el.innerHTML = `${s.state.replace(" (Abuja)", "")}<small>${pct(s[metric])}</small>`;
        markers.current.push(new maplibregl.Marker({ element: el }).setLngLat(labelPoint(f.geometry)).addTo(map));
      }
    };
    if (map.isStyleLoaded()) apply(); else map.once("load", apply);
  }, [data, selected, byCode, metric, showLabels, dark, ready]);

  const s = tip?.code ? byCode[tip.code] : null;
  return (
    <div className="map-wrap">
      <div ref={ref} className="map-national" style={height ? { height } : undefined} role="img"
        aria-label={`Map of Nigeria: covered states shaded by ${m.label}; other states greyed, not in demo`} />
      {tip && (
        <div className="map-tip" style={{ left: tip.x, top: tip.y }}>
          {s ? (
            <>
              <b>{s.state}</b> <span className="muted">· {s.zone}</span>
              <div style={{ margin: "6px 0" }}><StatusPill status={s.status} /></div>
              <div className="row"><span>{m.label}</span><span>{pct(s[metric], 1)}</span></div>
              <div className="row"><span>PHCs assessed</span><span>{int(s.facilities)}</span></div>
              <div className="row"><span>Act now</span><span>{int(s.act_now)}</span></div>
              <div className="row"><span>Verify then act</span><span>{int(s.verify_then_act)}</span></div>
              <div className="row"><span>Do not assume safe</span><span>{int(s.verification)}</span></div>
              <div className="row"><span>Reporting completeness</span><span>{pct(s.reporting_completeness)}</span></div>
              <div className="muted" style={{ marginTop: 6, fontSize: 11.5 }}>Click for the state brief</div>
            </>
          ) : (
            <><b>{tip.name}</b><div className="muted" style={{ marginTop: 2 }}>Not in demo</div></>
          )}
        </div>
      )}
      <div className="scale" aria-label="Map legend">
        <span>{m.label}{m.worse ? "" : ` (${dark ? "brighter" : "darker"} = lower)`}:</span>
        <span className="bins">
          {bins.ramp.map((c, i) => (
            <span key={c}><i style={{ background: c }} />{i === 0 ? pct(bins.edges[0]) : i === bins.ramp.length - 1 ? pct(bins.edges[bins.ramp.length]) : " "}</span>
          ))}
        </span>
        <span className="muted">{dark ? "brighter" : "darker"} = needs more attention</span>
        <span className="nodata" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><i /> Not in demo</span>
      </div>
    </div>
  );
}
