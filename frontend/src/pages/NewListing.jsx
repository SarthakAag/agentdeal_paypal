import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Field } from "../components/Ui";

export default function NewListing() {
  const nav = useNavigate();
  const [f, setF] = useState({ product: "", ask_price: "", min_price: "", fastest_days: "", ideal_days: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr("");
    const body = {
      product: f.product.trim(),
      ask_price: +f.ask_price,
      min_price: +f.min_price,
      fastest_days: +f.fastest_days,
      ideal_days: +f.ideal_days,
    };
    if (body.ask_price < body.min_price) return setErr("Your asking price can't be below your minimum price.");
    if (body.ideal_days < body.fastest_days) return setErr("Ideal delivery can't be faster than your fastest delivery.");
    setBusy(true);
    try {
      const r = await api.createListing(body);
      nav(`/listings/${r.id}`);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h1>Sell an item</h1>
      <Field label="Item or service">
        <input required maxLength={120} value={f.product} onChange={set("product")} placeholder="Logo design" />
      </Field>
      <div className="two">
        <Field label="Asking price (₹)" hint="Shown publicly. Your agent opens here.">
          <input required type="number" min="1" step="any" value={f.ask_price} onChange={set("ask_price")} />
        </Field>
        <Field label="Minimum price (₹)" hint="Private. Your agent will never go below this.">
          <input required type="number" min="1" step="any" value={f.min_price} onChange={set("min_price")} />
        </Field>
      </div>
      <div className="two">
        <Field label="Fastest delivery (days)" hint="Private. The quickest you can really deliver.">
          <input required type="number" min="1" value={f.fastest_days} onChange={set("fastest_days")} />
        </Field>
        <Field label="Ideal delivery (days)" hint="What you would prefer.">
          <input required type="number" min="1" value={f.ideal_days} onChange={set("ideal_days")} />
        </Field>
      </div>
      <ErrorBox>{err}</ErrorBox>
      <button className="btn primary" disabled={busy}>{busy ? "Listing…" : "List item"}</button>
    </form>
  );
}