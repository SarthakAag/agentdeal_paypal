import { useEffect, useState } from "react";
import { inr } from "../format";

// The negotiation is computed on the server in one go; this replays it turn by turn.
export default function TranscriptPlayer({ transcript, speed = 900 }) {
  const count = transcript.length;
  const [shown, setShown] = useState(0);
  const [run, setRun] = useState(0);

  useEffect(() => {
    setShown(0);
    if (!count) return undefined;
    let i = 0;
    const t = setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= count) clearInterval(t);
    }, speed);
    return () => clearInterval(t);
  }, [count, speed, run]);

  return (
    <div className="card">
      <div className="row between">
        <h3>Negotiation</h3>
        <div className="row">
          <button className="btn small" onClick={() => setRun(run + 1)}>Replay</button>
          <button className="btn small" onClick={() => setShown(count)}>Skip</button>
        </div>
      </div>
      <div className="chat">
        {transcript.slice(0, shown).map((t) => (
          <div key={t.turn} className={`turn ${t.role}`}>
            <div className="who">
              {t.role === "buyer" ? "Buyer's agent" : "Seller's agent"} · round {t.round}
            </div>
            {t.action === "offer" && (
              <div className="offer">
                <b>{inr(t.price)}</b>
                <span>{t.delivery_days} days</span>
              </div>
            )}
            {t.action === "accept" && <div className="offer accepted"><b>Accepted</b></div>}
            {t.action === "reject" && <div className="offer"><b>Walked away</b></div>}
            <p>{t.natural || t.message}</p>
            {t.natural && <small className="muted">rephrased by AI · numbers verified by code</small>}
            {t.violation && <small className="guard">Rule engine corrected this move to stay inside the hard limits</small>}
          </div>
        ))}
        {shown < count && <div className="typing">negotiating…</div>}
      </div>
    </div>
  );
}