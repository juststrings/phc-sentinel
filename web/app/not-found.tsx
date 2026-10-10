import Link from "next/link";
import Legacy from "@/components/Legacy";

export default function NotFound() {
  return (
    <Legacy><main>
      <div className="card" style={{ maxWidth: 560, margin: "48px auto", textAlign: "center", padding: 32 }}>
        <div className="eyebrow">Not found</div>
        <h1 style={{ marginTop: 6 }}>That view is not in the demo</h1>
        <p className="secondary">The state, LGA or facility may not be covered. Twelve states are available, two per geopolitical zone.</p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 16 }}>
          <Link className="btn primary" href="/national">National Command Centre</Link>
          <Link className="btn" href="/">Choose a state</Link>
        </div>
      </div>
    </main></Legacy>
  );
}
