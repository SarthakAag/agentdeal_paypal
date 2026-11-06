export const inr = (n) =>
  n == null ? "—" : "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });

export const usd = (n) => (n == null ? "—" : "$" + Number(n).toFixed(2));

// the database stores UTC timestamps like "2026-10-15 05:56:12"
export const fmtTime = (s) => (s ? new Date(s.replace(" ", "T") + "Z").toLocaleString() : "");