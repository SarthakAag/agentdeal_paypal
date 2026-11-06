import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { inr } from "../format";
import { ErrorBox, Field } from "../components/Ui";

export default function Bid() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const ids = (params.get("ids") || "").split(",").map(Number).filter((n) => n > 0).slice(0, 5);
  const [listings, setListings] = useState([]);
  const [f, setF] = useState({ budget: "", ideal_price: "", latest_days: "", ideal_days: "", max_rounds: "8" });
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    Promise.all(ids.map((i) => api.listing(i).catch(() => null))).then((l) => setListings(l.filter(Boolean)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("ids")]);

  if (ids.length < 2) {
    return <div className="card"><p>Pick at least 2 listings on the <Link to="/">Marketplace</Link> first.</p></div>;
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
      setRes(await api.bid({ listing_ids: ids, mandate: m }));
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  async function choose(b) {
    // decline every other deal from this comparison, then open the chosen one
    await Promise.allSettled(
      res.bids.filter((x) => x.negotiation_id !== b.negotiation_id && x.status === "awaiting_approval")
        .map((x) => api.decide(x.negotiation_id, false))
    );
    nav(`/deals/${b.negotiation_id}`);
  }

  return (
    <>
      <Link to="/" className="muted">← Marketplace</Link>
      <h1>Compare sellers</h1>
      <div className="card">
        <h3>Comparing</h3>
        <ul className="plain">
          {listings.map((l) => (
            <li key={l.id}>
              <b>{l.product}</b> · asking {inr(l.ask_price)}
              {l.reliability?.deals ? ` · on-time ${l.reliability.on_time}/${l.reliability.deals}` : ""}
            </li>
          ))}
        </ul>
      </div>

      {!res && (
        <form className="card form" onSubmit={submit}>
          <h2>One mandate for all of them</h2>
          <p className="muted">Your limits are private and your agent never goes past them. Each listing gets its own negotiation.</p>
          <div className="two">
            <Field label="Maximum budget (₹)" hint="Hard limit.">
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
            {busy ? `Negotiating with ${ids.length} sellers, one after another…` : `Negotiate with ${ids.length} sellers`}
          </button>
        </form>
      )}

      {res && (
        <div className="card">
          <h2>Results, best first</h2>
          <p className="muted">Ranked by your own score (100% is your ideal, 0% is your limit).</p>
          <table>
            <thead><tr><th>#</th><th>Item</th><th>Price</th><th>Delivery</th><th>Your score</th><th></th></tr></thead>
            <tbody>
              {res.bids.map((b, i) => (
                <tr key={b.negotiation_id} className={b.negotiation_id === res.best ? "best" : ""}>
                  <td>{b.score == null ? "–" : i + 1}</td>
                  <td><b>{b.product}</b><br /><small className="muted">asking {inr(b.ask_price)}</small></td>
                  <td>{b.score == null ? "No deal" : inr(b.agreed_price)}</td>
                  <td>{b.score == null ? "–" : `${b.agreed_days} days`}</td>
                  <td>{b.score == null ? "–" : `${Math.round(b.score * 100)}%`}</td>
                  <td>
                    {b.score != null ? (
                      <button className="btn small primary" onClick={() => choose(b)}>
                        {b.negotiation_id === res.best ? "Choose best" : "Choose"}
                      </button>
                    ) : (
                      <Link to={`/deals/${b.negotiation_id}`}>View</Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <ErrorBox>{err}</ErrorBox>
          <p className="muted">Choosing a deal declines the others. Nothing is charged until both sides approve and you pay.</p>
        </div>
      )}
    </>
  );
}