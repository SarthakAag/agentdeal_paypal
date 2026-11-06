import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { fmtTime, inr } from "../format";
import { ErrorBox, StatusBadge } from "../components/Ui";

const ACTION = new Set([
  "Review buyer's offer",
  "Review and approve",
  "Pay with PayPal",
  "Finish payment at PayPal",
  "Confirm delivery",
]);

function todo(d) {
  if (d.status === "seller_review") return d.side === "seller" ? "Review buyer's offer" : "Waiting for the seller";
  if (d.status === "awaiting_approval") {
    const done = d.side === "buyer" ? d.buyer_approved : d.seller_approved;
    return done ? "Waiting for the other side" : "Review and approve";
  }
  if (d.status === "approved") return d.side === "buyer" ? "Pay with PayPal" : "Waiting for payment";
  if (d.status === "payment_pending") return d.side === "buyer" ? "Finish payment at PayPal" : "Waiting for payment";
  if (d.status === "funds_held") return d.side === "seller" ? "Confirm delivery" : "Waiting for delivery";
  return "";
}

export default function Account() {
  const { user } = useAuth();
  const [sum, setSum] = useState(null);
  const [deals, setDeals] = useState(null);
  const [mine, setMine] = useState([]);
  const [filter, setFilter] = useState("all");
  const [err, setErr] = useState("");
  const seller = user.role === "seller";

  function load() {
    api.summary().then(setSum).catch((e) => setErr(e.message));
    api.myDeals().then(setDeals).catch((e) => setErr(e.message));
    if (seller) api.myListings().then(setMine).catch((e) => setErr(e.message));
  }
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function close(id) {
    if (!window.confirm("Close this listing? It disappears from the marketplace. Deals in progress continue.")) return;
    try {
      await api.closeListing(id);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  const statuses = [...new Set((deals || []).map((d) => d.status))];
  const shown = (deals || []).filter((d) => filter === "all" || d.status === filter);
  const waiting = (deals || []).filter((d) => ACTION.has(todo(d)));

  return (
    <>
      <h1>My account</h1>
      <p className="muted">{user.name} · {user.role} account</p>
      <ErrorBox>{err}</ErrorBox>

      {sum && (
        <div className="stats">
          <div className="card stat"><b>{sum.deals}</b><span>deals</span></div>
          <div className="card stat"><b>{inr(sum.paid_inr)}</b><span>{seller ? "earned (paid)" : "spent (paid)"}</span></div>
          <div className="card stat"><b>{inr(sum.refunded_inr)}</b><span>refunded</span></div>
          {seller && (
            <div className="card stat">
              <b>{sum.delivery?.deals ? `${sum.delivery.on_time}/${sum.delivery.deals}` : "–"}</b>
              <span>on-time deliveries</span>
            </div>
          )}
        </div>
      )}

      {waiting.length > 0 && (
        <div className="notice ok">
          <b>Needs your action:</b>{" "}
          {waiting.map((d) => (
            <span key={d.id}><Link to={`/deals/${d.id}`}>#{d.id} {d.product}</Link> ({todo(d).toLowerCase()}) </span>
          ))}
        </div>
      )}

      <div className="card">
        <div className="row between">
          <h2>Deal history</h2>
          <select style={{ width: "auto" }} value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All statuses</option>
            {statuses.map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
          </select>
        </div>
        {!deals && <p>Loading…</p>}
        {deals && shown.length === 0 && (
          <p className="muted">
            No deals yet. {seller ? "When a buyer's agent negotiates one of your items it appears here."
              : <>Pick an item on the <Link to="/">Marketplace</Link> and send your agent.</>}
          </p>
        )}
        {shown.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr><th>#</th><th>Item</th><th>{seller ? "Buyer" : "Seller"}</th><th>Agreed</th><th>Status</th><th>Next step</th><th>Outcome</th><th>Date</th></tr>
              </thead>
              <tbody>
                {shown.map((d) => (
                  <tr key={d.id}>
                    <td><Link to={`/deals/${d.id}`}>#{d.id}</Link></td>
                    <td>{d.product}</td>
                    <td>{d.counterparty || "–"}</td>
                    <td>{d.agreed_price != null ? `${inr(d.agreed_price)} · ${d.agreed_days} d` : "–"}</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td>{todo(d) || "–"}</td>
                    <td>{d.outcome ? d.outcome.replaceAll("_", " ") : "–"}</td>
                    <td><small className="muted">{fmtTime(d.created)}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {seller && (
        <div className="card">
          <h2>My listings</h2>
          {mine.length === 0 && <p className="muted">No listings yet. <Link to="/sell">Sell an item</Link>.</p>}
          {mine.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr><th>Item</th><th>Asking</th><th>Your minimum</th><th>Fastest</th><th>Deals</th><th>Paid</th><th></th></tr>
                </thead>
                <tbody>
                  {mine.map((l) => (
                    <tr key={l.id}>
                      <td><Link to={`/listings/${l.id}`}>{l.product}</Link>{!l.active && <> <span className="chip">closed</span></>}</td>
                      <td>{inr(l.ask_price)}</td>
                      <td>{inr(l.min_price)}</td>
                      <td>{l.fastest_days} d</td>
                      <td>{l.negotiations}</td>
                      <td>{l.paid}</td>
                      <td>{l.active ? <button className="btn small" onClick={() => close(l.id)}>Close</button> : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}