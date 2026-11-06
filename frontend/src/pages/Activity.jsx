import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtTime } from "../format";
import { ErrorBox } from "../components/Ui";

export default function Activity() {
  const [data, setData] = useState(null);
  const [sweep, setSweep] = useState(null);
  const [err, setErr] = useState("");

  const load = () => api.activity().then(setData).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
  }, []);

  async function runSweep() {
    setErr("");
    try {
      setSweep(await api.sweep());
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <>
      <div className="row between">
        <h1>Activity</h1>
        <button className="btn" onClick={runSweep}>Run deadline check</button>
      </div>
      <ErrorBox>{err}</ErrorBox>
      {sweep && (
        <div className="notice">
          Checked {sweep.checked} held payment{sweep.checked === 1 ? "" : "s"}.{" "}
          {sweep.results.filter((r) => r.result === "voided").length} voided for missed deadlines.
        </div>
      )}
      {data && (
        <>
          <div className="stats">
            {Object.entries(data.counts).map(([k, v]) => (
              <div key={k} className="card stat"><b>{v}</b><span>{k.replaceAll("_", " ")}</span></div>
            ))}
            {Object.keys(data.counts).length === 0 && <p className="muted">No outcomes recorded yet.</p>}
          </div>
          <p className="muted">
            Outcomes are the labels used to retrain the agents. {data.simulated_deals} simulated marketplace deals used
            for the learning loop are not shown here.
          </p>
          <div className="card">
            <h3>PayPal event log</h3>
            <table>
              <thead><tr><th>Event</th><th>Deal</th><th>Verified</th><th>Time</th></tr></thead>
              <tbody>
                {data.events.map((e) => (
                  <tr key={e.id}>
                    <td>{e.event_type.replaceAll("_", " ").toLowerCase()}</td>
                    <td>{e.negotiation_id ? <Link to={`/deals/${e.negotiation_id}`}>#{e.negotiation_id}</Link> : "—"}</td>
                    <td>{e.verified ? "yes" : "no"}</td>
                    <td>{fmtTime(e.created)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}