import Link from "next/link";
import Legacy from "@/components/Legacy";
import { StatusPill } from "@/components/Tags";
import { api, int, monthLabel, pct } from "@/lib/api";

/** Role switcher. Every view is one click away and has its own URL; no login in the demo. */
export default async function Landing() {
  const [meta, nat, st] = await Promise.all([api("/meta/states"), api("/national/summary"), api("/national/states")]);
  const k = nat.kpis;
  const byCode: Record<string, any> = Object.fromEntries(st.states.map((s: any) => [s.code ?? s.state_code, s]));

  return (
    <Legacy>
      <section className="hero">
        <div className="eyebrow">Operational risk × data confidence · {monthLabel(nat.month, true)} analysis</div>
        <h1>See risk before it becomes a shortage.</h1>
        <p className="lead">
          PHC Sentinel tells health managers which primary health care facilities need action, which need their data
          verified first, and why. Low observed risk with low confidence is never shown as safe.
        </p>
      </section>

      <div className="roles">
        <Link href="/national" className="role national">
          <div className="eyebrow">Federal view · FMoH / NPHCDA</div>
          <h2>National Command Centre</h2>
          <p>State-level summaries across {k.states} states in all six geopolitical zones: where to act, where the evidence is too weak to trust, and how each state is trending.</p>
          <div className="stats">
            <div><b>{int(k.facilities)}</b><span>PHCs assessed</span></div>
            <div><b>{int(k.act_now)}</b><span>act now</span></div>
            <div><b>{int(k.verification)}</b><span>do not assume safe</span></div>
            <div><b>{pct(k.reporting_completeness)}</b><span>reporting</span></div>
          </div>
          <ul className="role-list">
            <li>Interactive Nigeria map, coloured by the metric you choose</li>
            <li>A one-click brief for every state, with its top LGAs and six-month trend</li>
            <li>The six geopolitical zones side by side</li>
            <li>Briefing mode: large type, ready to present</li>
          </ul>
          <span className="go">Open the Command Centre <span aria-hidden>→</span></span>
        </Link>

        <div className="role">
          <div className="eyebrow">State view · State PHC Board / Agency</div>
          <h2>State portal</h2>
          <p className="secondary">Choose a state to open its overview, LGA action and verification queues, and facility explanations.</p>
          <div className="state-picker">
            {meta.zones.map((z: string) => (
              <div key={z}>
                <h4>{z}</h4>
                {meta.states.filter((s: any) => s.zone === z).map((s: any) => {
                  const r = byCode[s.code];
                  return (
                    <Link key={s.code} href={`/state/${s.code}`} className="state-link" title={r ? `${r.facilities} PHCs · ${r.act_now} act now` : undefined}>
                      <span>{s.name}{r && <small style={{ display: "block" }}>{int(r.facilities)} PHCs</small>}</span>
                      <span aria-hidden>→</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="access-note" role="note">
        <span aria-hidden>🔓</span>
        <span>
          <strong>Demo access, no login.</strong> Every view has its own address (<code>/national</code>, <code>/state/bauchi</code>, …) so
          reviewers can open any view in one click. A pilot deployment adds real authentication with state-scoped access:
          a state team sees only its own state; federal users see the national roll-up.
        </span>
      </div>

      <section className="section">
        <div className="section-head">
          <div>
            <h2>States at a glance</h2>
            <p>Status mirrors the Risk × Confidence matrix at state level and is always shown in words.</p>
          </div>
          <Link className="btn" href="/national/briefing">Open briefing mode</Link>
        </div>
        <div className="card" style={{ padding: 0, overflowX: "auto" }}>
          <table className="data">
            <thead>
              <tr><th>State</th><th>Zone</th><th>Status</th><th className="n">PHCs</th><th className="n">Act now</th><th className="n">Do not assume safe</th><th className="n">Reporting</th></tr>
            </thead>
            <tbody>
              {st.states.map((s: any) => (
                <tr key={s.state_code}>
                  <td><Link href={`/state/${s.state_code}`}><strong>{s.state}</strong></Link></td>
                  <td className="secondary">{s.zone}</td>
                  <td><StatusPill status={s.status} /></td>
                  <td className="n">{int(s.facilities)}</td>
                  <td className="n">{int(s.act_now)} <span className="muted">({pct(s.pct_act_now)})</span></td>
                  <td className="n">{int(s.verification)} <span className="muted">({pct(s.pct_verification)})</span></td>
                  <td className="n">{pct(s.reporting_completeness)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </Legacy>
  );
}
