import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { inr } from "../format";
import { ErrorBox } from "../components/Ui";

function Reliability({ r }) {
  if (!r || !r.deals) {
    return <small className="muted">No delivery history yet</small>;
  }

  return (
    <small className="muted">
      On-time delivery: {r.on_time}/{r.deals} (
      {Math.round(r.rate * 100)}%)
    </small>
  );
}

export default function Listings() {
  const { user } = useAuth();
  const nav = useNavigate();

  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  const [picked, setPicked] = useState([]);

  const isBuyer = user?.role === "buyer";

  useEffect(() => {
    api.listings()
      .then(setItems)
      .catch((e) => setErr(e.message));
  }, []);

  function toggle(id) {
    setPicked((p) =>
      p.includes(id)
        ? p.filter((x) => x !== id)
        : p.length < 5
          ? [...p, id]
          : p
    );
  }

  return (
    <>
      <div className="row between marketplace-heading">
        <div>
          <h1>Marketplace</h1>

          <p className="muted">
            {!user && (
              <>
                Browse the items.{" "}
                <Link to="/login">Sign in</Link> as a buyer to send an
                agent, or as a seller to list one.
              </>
            )}

            {isBuyer &&
              "Open an item to negotiate, or tick 2 to 5 items and compare them with one mandate."}

            {user?.role === "seller" &&
              "List an item with your private limits. Buyers' agents negotiate with yours."}
          </p>
        </div>

        {user?.role === "seller" && (
          <Link className="btn primary" to="/sell">
            Sell an item
          </Link>
        )}
      </div>

      <ErrorBox>{err}</ErrorBox>

      {!items && !err && <p>Loading…</p>}

      {items && items.length === 0 && (
        <div className="card empty">No items yet.</div>
      )}

      <div className="grid">
        {(items || []).map((l) => (
          <div
            key={l.id}
            className={`card pick ${picked.includes(l.id) ? "on" : ""}`}
          >
            {isBuyer && (
              <label className="tick">
                <input
                  type="checkbox"
                  checked={picked.includes(l.id)}
                  onChange={() => toggle(l.id)}
                />
                <span>Compare</span>
              </label>
            )}

            <Link to={`/listings/${l.id}`} className="item">
              <div className="row between listing-title">
                <h3>{l.product}</h3>
                {l.mine && <span className="chip">Yours</span>}
              </div>

              <div className="price">{inr(l.ask_price)}</div>

              <small className="muted">
                asking price · by {l.seller_name || "a seller"} ·{" "}
                {l.negotiations} negotiation
                {l.negotiations === 1 ? "" : "s"}
              </small>

              <div>
                <Reliability r={l.reliability} />
              </div>
            </Link>
          </div>
        ))}
      </div>

      {isBuyer && picked.length > 0 && (
        <div className="bidbar">
          <span>
            {picked.length} selected
            {picked.length === 5 ? " (maximum)" : ""}
          </span>

          <button
            className="btn primary"
            disabled={picked.length < 2}
            onClick={() => nav(`/bid?ids=${picked.join(",")}`)}
          >
            {picked.length < 2
              ? "Pick at least 2"
              : "Compare and negotiate"}
          </button>
        </div>
      )}
    </>
  );
}
