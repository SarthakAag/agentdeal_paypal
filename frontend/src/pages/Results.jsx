import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox } from "../components/Ui";

const pct = (x) => Math.round(x * 100) + "%";

function RoleTable({ title, data }) {
  const rows = [{ ...data.baseline, desc: "Fixed concession curve, no model." }, ...data.versions];
  return (
    <div className="card">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr><th>Version</th><th>Closes feasible deals</th><th>Score</th><th></th><th>Rule fixes per deal</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <td><b>{r.name}</b><br /><small className="muted">{r.desc}</small></td>
              <td>{pct(r.closure)}</td>
              <td>{r.score.toFixed(3)}</td>
              <td style={{ width: "28%" }}>
                <div className="bar"><span style={{ width: `${Math.round(r.score * 100)}%` }} /></div>
              </td>
              <td>{r.mistakes.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Results() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.results().then(setD).catch((e) => setErr(e.message));
  }, []);

  if (!d) return err ? <ErrorBox>{err}</ErrorBox> : <p>Loading…</p>;

  return (
    <>
      <h1>Model results</h1>
      <p className="muted">{d.note}</p>
      <RoleTable title="Buyer agent" data={d.roles.buyer} />
      <RoleTable title="Seller agent" data={d.roles.seller} />

      <div className="card">
        <h3>Two fine-tuned agents against each other</h3>
        <p>
          Closure on feasible deals went from <b>{pct(d.model_vs_model.before)}</b> to{" "}
          <b>{pct(d.model_vs_model.after)}</b>. <span className="muted">{d.model_vs_model.detail}</span>
        </p>
      </div>

      <div className="card">
        <h3>Assist models</h3>
        <ul className="plain">
          {d.assist.map((a) => (
            <li key={a.name}><b>{a.name}:</b> {a.result}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>Limits of these numbers</h3>
        <ul className="plain">
          {d.caveats.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      </div>
    </>
  );
}