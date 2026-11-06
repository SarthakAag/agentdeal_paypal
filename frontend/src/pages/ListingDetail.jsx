import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { inr, fmtTime } from "../format";
import { ErrorBox, Field, StatusBadge } from "../components/Ui";

export default function ListingDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [listing, setListing] = useState(null);
  const [deals, setDeals] = useState([]);
  const [f, setF] = useState({ budget: "", ideal_price: "", latest_days: "", ideal_days: "", max_rounds: "8" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [ai, setAi] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiNote, setAiNote] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    api.listing(id).then(setListing).catch((e) => setErr(e.message));
    api.assistStatus().then((s) => setAi(s.available)).catch(() => {});
  }, [id]);
  useEffect(() => {
    if (user) api.negotiations(id).then(setDeals).catch(() => {});
  }, [id, user]);

  async function fillWithAI() {
    setErr("");
    setAiNote("");
    setAiBusy(true);
    try {
      const r = await api.assistMandate(aiText, listing.ask_price);
      const x = r.fields;
      setF((p) => ({
        ...p,
        budget: x.budget ?? p.budget,
        ideal_price: x.ideal_price ?? p.ideal_price,
        latest_days: x.latest_days ?? p.latest_days,
        ideal_days: x.ideal_days ?? p.ideal_days,
        max_rounds: x.max_rounds ? String(x.max_rounds) : p.max_rounds,
      }));
      const parts = [];
      if (r.missing.length) parts.push(`Please fill in: ${r.missing.join(", ").replaceAll("_", " ")}.`);
      if (r.note) parts.push(r.note);
      setAiNote(parts.join(" ") || "Filled in below. Check every number before you start.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setAiBusy(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    const m = {
      budget: +f.budget, ideal_price: +f.ideal_price,
      latest_days: +f.latest_days, ideal_days: +f.ideal_days, max_rounds: +f.max_rounds,
    };
    if (m.ideal_price > m.budget) return setErr("Your ideal price can't be higher than your budget.");
    if (m.ideal_days > m.latest_days) return setErr("Ideal delivery can't be later than your latest acceptable delivery.");
    setBusy(true);
    try {
      const r = await api.startNegotiation({ listing_id: +id, mandate: m });
      nav(`/deals/${r.id}`);
    } catch (e2) {
      setErr(e2.message);
      setBusy(false);
    }
  }

  if (!listing) return err ? <ErrorBox>{err}</ErrorBox> : <p>Loading…</p>;

  const isBuyer = user?.role === "buyer";

  return (
    <>
      <Link to="/" className="muted">← Marketplace</Link>
      <div className="card">
        <div className="row between">
          <h1>{listing.product}</h1>
          {listing.mine && <span className="chip">Yours</span>}
        </div>
        <div className="price">{inr(listing.ask_price)}</div>
        <small className="muted">
          asking price · by {listing.seller_name || "a seller"} · listed {fmtTime(listing.created)}
          {listing.reliability?.deals ? ` · on-time ${listing.reliability.on_time}/${listing.reliability.deals}` : ""}
        </small>
        {!listing.active && <p className="guard">This listing is closed.</p>}
      </div>

      {!user && (
        <div className="card"><p><Link to="/login" state={{ from: `/listings/${id}` }}>Sign in</Link> as a buyer to send your agent.</p></div>
      )}

      {isBuyer && listing.active && !listing.mine && (
        <form className="card form" onSubmit={submit}>
          <h2>Send your agent to negotiate</h2>
          <p className="muted">Your limits are private. Your agent never goes past them, and a rule engine enforces that in code.</p>
          {ai && (
            <div className="card">
              <Field label="Describe what you want" hint="e.g. “under ₹4000, within 10 days, price matters more”">
                <input value={aiText} onChange={(e) => setAiText(e.target.value)} maxLength={500} />
              </Field>
              <button type="button" className="btn" disabled={aiBusy || aiText.trim().length < 3} onClick={fillWithAI}>
                {aiBusy ? "Reading…" : "Fill the form with AI"}
              </button>
              {aiNote && <p className="muted">{aiNote}</p>}
            </div>
          )}
          <div className="two">
            <Field label="Maximum budget (₹)" hint="Hard limit. Never exceeded.">
              <input required type="number" min="1" step="any" value={f.budget} onChange={set("budget")} />
            </Field>
            <Field label="Price you'd love (₹)">
              <input required type="number" min="1" step="any" value={f.ideal_price} onChange={set("ideal_price")} />
            </Field>
          </div>
          <div className="two">
            <Field label="Latest acceptable delivery (days)" hint="Hard limit.">
              <input required type="number" min="1" value={f.latest_days} onChange={set("latest_days")} />
            </Field>
            <Field label="Ideal delivery (days)">
              <input required type="number" min="1" value={f.ideal_days} onChange={set("ideal_days")} />
            </Field>
          </div>
          <Field label="Negotiation rounds">
            <select value={f.max_rounds} onChange={set("max_rounds")}>
              <option value="6">6</option><option value="8">8</option><option value="10">10</option>
            </select>
          </Field>
          <ErrorBox>{err}</ErrorBox>
          <button className="btn primary" disabled={busy}>
            {busy ? "Agents are negotiating… this can take a minute with fine-tuned models" : "Start negotiation"}
          </button>
        </form>
      )}

      {user && user.role === "seller" && !listing.mine && (
        <div className="card"><p className="muted">You're signed in as a seller. Use a buyer account to negotiate on this item.</p></div>
      )}

      {user && deals.length > 0 && (
        <div className="card">
          <h2>{listing.mine ? "Negotiations on this item" : "Your negotiations on this item"}</h2>
          {deals.map((d) => (
            <Link key={d.id} to={`/deals/${d.id}`} className="rowlink">
              <span>
                Deal #{d.id}{d.counterparty ? ` · with ${d.counterparty}` : ""}
                {d.agreed_price != null && ` · ${inr(d.agreed_price)} in ${d.agreed_days} days`}
              </span>
              <StatusBadge status={d.status} />
            </Link>
          ))}
        </div>
      )}
    </>
  );
}