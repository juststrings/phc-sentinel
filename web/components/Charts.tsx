"use client";
import {
  Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const axis = { stroke: "var(--line)", tick: { fill: "var(--ink-3)", fontSize: 11 }, tickLine: false };
const grid = { stroke: "var(--line)", vertical: false };
const tip = {
  contentStyle: { background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)" },
  labelStyle: { color: "var(--ink-2)", fontWeight: 600 },
  cursor: { fill: "var(--muted-bg)" },
};
const legend = { wrapperStyle: { fontSize: 12, color: "var(--ink-2)" }, iconSize: 10 };
const short = (m: string) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleString("en-GB", { month: "short", year: "2-digit" });
};

/** Queue sizes over time, stacked in the four queue tokens. Months before `warmup` ends are not passed in. */
export function QueueTrend({ data }: { data: any[] }) {
  return (
    <div>
      {/* Hatch pattern for Do not assume safe, so it never reads as a plain colour. */}
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <defs>
          <pattern id="dnas-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="var(--q-dnas)" />
            <rect width="2" height="6" fill="rgba(255,255,255,0.55)" />
          </pattern>
        </defs>
      </svg>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }} barCategoryGap={2}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="analysis_month" tickFormatter={short} stroke="var(--line)" tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} interval={2} />
          <YAxis stroke="var(--line)" tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} allowDecimals={false} />
          <Tooltip
            contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 6, fontSize: 12, color: "var(--ink)" }}
            labelStyle={{ color: "var(--ink-2)", fontWeight: 600 }} cursor={{ fill: "var(--muted-bg)" }} labelFormatter={short}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--ink-2)" }} iconSize={10} />
          <Bar isAnimationActive={false} dataKey="act_now" name="Act now" stackId="q" fill="var(--q-act)" />
          <Bar isAnimationActive={false} dataKey="verify_then_act" name="Verify then act" stackId="q" fill="var(--q-verify)" />
          <Bar isAnimationActive={false} dataKey="verification" name="Do not assume safe" stackId="q" fill="url(#dnas-hatch)" />
          <Bar isAnimationActive={false} dataKey="monitor" name="Monitor" stackId="q" fill="var(--q-monitor)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const WINDOW = 18;

/** The WINDOW calendar months ending at `end` (YYYY-MM), oldest first. */
function monthsEndingAt(end: string, n: number): string[] {
  const [y, m] = end.split("-").map(Number);
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(y, m - 1 - (n - 1 - i), 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
}

/** One indicator: reported value vs seasonal baseline, for the last 18 months ending at the analysis month. */
export function ServiceChart({ rows, indicator, title, month }: { rows: any[]; indicator: string; title: string; month: string }) {
  const by = new Map(rows.filter((r) => r.indicator === indicator).map((r) => [r.analysis_month, r]));
  const data = monthsEndingAt(month, WINDOW).map((m) => ({ m, value: by.get(m)?.value ?? null, expected: by.get(m)?.expected ?? null }));
  if (!data.some((d) => d.value != null || d.expected != null)) return <div className="py-6 text-center text-[13px] text-ink-3">No history</div>;
  return (
    <div>
      <h4 className="mb-2 text-[13px] font-medium text-ink-2">{title}</h4>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 8, right: 28, left: -8, bottom: 0 }}>
          <CartesianGrid {...grid} />
          <XAxis dataKey="m" tickFormatter={short} {...axis} ticks={data.filter((_, i) => (data.length - 1 - i) % 3 === 0).map((d) => d.m)} interval={0} padding={{ left: 8, right: 8 }} />
          <YAxis {...axis} />
          <Tooltip {...tip} labelFormatter={short}
            formatter={(v: any, n: any) => [v == null ? "not reported" : Math.round(v).toLocaleString(), n]} />
          <Legend {...legend} />
          <Line isAnimationActive={false} dataKey="expected" name="Expected (baseline)" stroke="var(--ink-3)" strokeWidth={2} dot={false} connectNulls />
          <Line isAnimationActive={false} dataKey="value" name="Reported" stroke="var(--s1)" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const PRODUCTS: [string, string, string][] = [
  ["ACT_AL_ADULT", "ACT adult", "var(--s1)"],
  ["ACT_AL_CHILD", "ACT child", "var(--s2)"],
  ["RDT_MAL", "Malaria RDT", "var(--s3)"],
];

/** Months of stock per NHLMIS period, with the policy minimum and emergency order point. */
export function CommodityChart({ rows, minMonths, eopMonths }: { rows: any[]; minMonths: number; eopMonths: number }) {
  const by: Record<string, any> = {};
  for (const r of rows) {
    const k = r.period_start;
    by[k] ??= { period: k };
    by[k][r.commodity_code] = r.amc > 0 ? Math.max(0, +(r.physical_stock / r.amc).toFixed(2)) : null;
  }
  const data = Object.values(by).slice(-9);
  if (!data.length) return <div className="empty">No NHLMIS reports on record</div>;
  const label = (p: string) => {
    const [y, m] = p.split("-").map(Number);
    const a = new Date(y, m - 1, 1), b = new Date(y, m, 1);
    return `${a.toLocaleString("en-GB", { month: "short" })}–${b.toLocaleString("en-GB", { month: "short" })} ${String(y).slice(2)}`;
  };
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }} barGap={2} barCategoryGap="22%">
        <CartesianGrid {...grid} />
        <XAxis dataKey="period" tickFormatter={label} {...axis} />
        <YAxis {...axis} label={{ value: "months of stock", angle: -90, position: "insideLeft", offset: 18, fill: "var(--ink-3)", fontSize: 11 }} />
        <Tooltip {...tip} labelFormatter={label} formatter={(v: any, n: any) => [v == null ? "n/a" : `${v} months`, n]} />
        <Legend {...legend} />
        <ReferenceLine y={minMonths} stroke="var(--q-verify)" strokeDasharray="4 3" label={{ value: `${minMonths}-month minimum`, fill: "var(--ink-3)", fontSize: 10, position: "insideTopLeft" }} />
        <ReferenceLine y={eopMonths} stroke="var(--q-act)" strokeDasharray="4 3" label={{ value: "emergency order point", fill: "var(--ink-3)", fontSize: 10, position: "insideBottomLeft" }} />
        {PRODUCTS.map(([k, n, c]) => (
          <Bar isAnimationActive={false} key={k} dataKey={k} name={n} fill={c} radius={[4, 4, 0, 0]} maxBarSize={18}>
            {/* A zero-height bar is invisible: mark stocked-out periods explicitly. */}
            <LabelList dataKey={k} position="top" fill="var(--q-act)" fontSize={10} fontWeight={700}
              formatter={(v: any) => (v === 0 ? "0" : "")} />
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
