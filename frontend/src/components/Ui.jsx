export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export const ErrorBox = ({ children }) => (children ? <div className="error" role="alert">{children}</div> : null);

const LABELS = {
  seller_review: "With seller",
  awaiting_approval: "Awaiting approval",
  approved: "Approved",
  payment_pending: "Payment pending",
  funds_held: "Funds held",
  paid: "Paid",
  voided: "Funds released",
  refunded: "Refunded",
  declined: "Declined",
  no_deal: "No deal",
};

export function StatusBadge({ status }) {
  return <span className={`badge s-${status}`}>{LABELS[status] || status}</span>;
}

const STEPS = ["Negotiated", "Both approve", "Funds held", "Delivered"];
const DONE = { seller_review: 0, awaiting_approval: 1, approved: 2, payment_pending: 2, funds_held: 3, paid: 4 };

export function Steps({ status }) {
  const done = DONE[status];
  if (done == null) return null;
  return (
    <ol className="steps" aria-label="Deal progress">
      {STEPS.map((s, i) => (
        <li key={s} className={i < done ? "done" : i === done ? "now" : ""}>{s}</li>
      ))}
    </ol>
  );
}