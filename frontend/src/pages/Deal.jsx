
import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { inr, usd, fmtTime } from "../format";
import { ErrorBox, StatusBadge, Steps } from "../components/Ui";
import TranscriptPlayer from "../components/TranscriptPlayer";

const WHO = {
  buyer: "Buyer",
  seller: "Seller",
  paypal: "PayPal",
  system: "System",
};

const WHAT = {
  negotiation_started: "agents finished negotiating",
  deal_reached: "agents reached terms",
  review_requested: "agents could not close, final offer sent to the seller",
  review_accepted: "seller accepted the buyer's final offer",
  review_declined: "seller declined the final offer",
  review_expired: "review window closed with no answer",
  no_deal: "no deal",
  approved: "approved the deal",
  declined: "declined the deal",
  both_approved: "both sides approved",
  payment_started: "started the PayPal payment",
  payment_cancelled: "cancelled at PayPal",
  funds_held: "funds placed on hold",
  delivered: "confirmed delivery, payment captured",
  voided: "held funds released to the buyer",
  refunded: "payment refunded",
};

const label = (what = "") =>
  WHAT[what] ||
  what.replaceAll("_", " ").replaceAll(".", " ").toLowerCase();

// --------------------------------------------------
// Buyer-Seller Chat
// --------------------------------------------------

function DealChat({ dealId, disabled }) {
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const loadMessages = useCallback(async () => {
    try {
      const data = await api.messages(dealId);

      setMessages(
        Array.isArray(data) ? data : data.items || []
      );

      setError("");
    } catch (e) {
      setError(e.message || "Unable to load messages.");
    } finally {
      setLoading(false);
    }
  }, [dealId]);

  // Load messages and refresh every four seconds.
  useEffect(() => {
    let active = true;

    async function refresh() {
      if (!active || document.hidden) return;
      await loadMessages();
    }

    refresh();

    const timer = setInterval(refresh, 4000);

    const handleVisibility = () => {
      if (!document.hidden) refresh();
    };

    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener(
        "visibilitychange",
        handleVisibility
      );
    };
  }, [loadMessages]);

  async function send(event) {
    event.preventDefault();

    const body = message.trim();

    if (!body || sending || disabled) return;

    setSending(true);
    setError("");

    try {
      await api.sendMessage(dealId, body);

      setMessage("");

      await loadMessages();
    } catch (e) {
      setError(e.message || "Message could not be sent.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="card deal-chat">
      <div className="row between">
        <h3>Buyer–seller conversation</h3>
        <small className="muted">Deal #{dealId}</small>
      </div>

      <p className="muted">
        Chat directly with the other person involved in this deal.
      </p>

      <div className="deal-chat-messages">
        {loading ? (
          <p className="muted">Loading messages…</p>
        ) : messages.length === 0 ? (
          <p className="muted">
            No messages yet. Start the conversation.
          </p>
        ) : (
          messages.map((item) => (
            <div
              className="deal-chat-message"
              key={item.id}
            >
              <div className="row between">
                <b>
                  {item.sender_side
                    ? item.sender_side.charAt(0).toUpperCase() +
                      item.sender_side.slice(1)
                    : "Participant"}
                </b>

                <small className="muted">
                  {item.created_at
                    ? fmtTime(item.created_at)
                    : ""}
                </small>
              </div>

              <p>{item.body}</p>
            </div>
          ))
        )}
      </div>

      <ErrorBox>{error}</ErrorBox>

      <form className="deal-chat-form" onSubmit={send}>
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Write a message to the buyer or seller…"
          maxLength={2000}
          disabled={sending || disabled}
        />

        <button
          className="btn primary"
          type="submit"
          disabled={!message.trim() || sending || disabled}
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}

// --------------------------------------------------
// Deal Page
// --------------------------------------------------

export default function Deal() {
  const { id } = useParams();
  const [params] = useSearchParams();

  const [deal, setDeal] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [ai, setAi] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(
    () =>
      api
        .deal(id)
        .then((data) => {
          setDeal(data);
          setErr("");
        })
        .catch((e) => setErr(e.message)),
    [id]
  );

  useEffect(() => {
    load();
  }, [load]);

  // Refresh deal information every 15 seconds.
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) {
        api.deal(id).then(setDeal).catch(() => {});
      }
    }, 15000);

    return () => clearInterval(timer);
  }, [id]);

  useEffect(() => {
    api.config().then(setCfg).catch(() => {});

    api
      .assistStatus()
      .then((data) => setAi(data.available))
      .catch(() => {});
  }, []);

  async function run(name, fn, after) {
    setBusy(name);
    setErr("");

    try {
      const result = await fn();

      if (after) after(result);

      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy("");
    }
  }

  if (!deal) {
    return err ? <ErrorBox>{err}</ErrorBox> : <p>Loading…</p>;
  }

  const s = deal.status;
  const side = deal.my_side;
  const isBuyer = side === "buyer";
  const mine = deal[side];

  const iApproved = isBuyer
    ? deal.buyer_approved
    : deal.seller_approved;

  const agreed = deal.agreed_price != null;
  const rate = cfg?.inr_per_usd || 88;

  const amountUsd =
    deal.amount_usd ??
    (agreed
      ? Math.round((deal.agreed_price / rate) * 100) / 100
      : null);

  const disabled = !!busy;
  const sm = deal.summary;

  const other =
    deal.counterparty || (isBuyer ? "the seller" : "the buyer");

  // Show the buyer's offer against the seller's private limits.
  const outside = [];

  if (!isBuyer && mine && deal.proposal_price != null) {
    if (deal.proposal_price < mine.price_limit) {
      outside.push(
        `the price is ${inr(
          mine.price_limit - deal.proposal_price
        )} below your minimum`
      );
    }

    if (deal.proposal_days < mine.delivery_limit) {
      outside.push(
        `delivery is ${
          mine.delivery_limit - deal.proposal_days
        } day(s) faster than your fastest`
      );
    }
  }

  function approve() {
    if (
      sm?.near_limit &&
      !window.confirm(
        "These terms are very close to your limit. Approve anyway?"
      )
    ) {
      return;
    }

    run("approve", () => api.decide(id, true));
  }

  function acceptReview() {
    const message = outside.length
      ? `This offer breaks your own limits (${outside.join(
          "; "
        )}). Accept anyway?`
      : "Accept the buyer's final offer?";

    if (window.confirm(message)) {
      run("review", () => api.review(id, true));
    }
  }

  return (
    <>
      <Link to="/account" className="muted">
        ← My deals
      </Link>

      <div className="row between">
        <h1>
          Deal #{deal.id}: {deal.product}
        </h1>

        <StatusBadge status={s} />
      </div>

      <p className="muted">
        You are the <b>{side}</b>
        {deal.counterparty ? <> · with {deal.counterparty}</> : null}
      </p>

      <Steps status={s} />

      {params.get("paypal") === "held" && (
        <div className="notice ok">
          PayPal authorized the payment. The funds are on hold until the
          seller confirms delivery.
        </div>
      )}

      {params.get("paypal") === "cancelled" && (
        <div className="notice">
          Payment was cancelled at PayPal. You can continue to PayPal again
          below.
        </div>
      )}

      <ErrorBox>{err}</ErrorBox>

      <div className="cols">
        <div>
          {ai &&
            (deal.transcript || []).length > 0 &&
            !deal.transcript.some((item) => item.natural) && (
              <button
                className="btn small"
                disabled={disabled}
                onClick={() =>
                  run("narrate", () => api.narrate(id))
                }
              >
                {busy === "narrate"
                  ? "Rewriting…"
                  : "Make the messages sound natural"}
              </button>
            )}

          <TranscriptPlayer transcript={deal.transcript || []} />

          {/* Direct buyer-seller chat is always visible. */}
          <DealChat
            dealId={id}
            disabled={disabled}
          />
        </div>

        <div className="stack">
          {agreed ? (
            <div className="card">
              <h3>Agreed terms</h3>

              <div className="price">
                {inr(deal.agreed_price)}
              </div>

              <p>
                Delivery in <b>{deal.agreed_days} days</b> ·{" "}
                {deal.rounds} rounds
              </p>

              <small className="muted">
                PayPal charges {usd(amountUsd)} (fixed rate: ₹{rate} per $1)
              </small>

              {deal.deliver_by && (
                <p>
                  Delivery deadline: <b>{deal.deliver_by}</b>
                </p>
              )}

              {sm && (
                <>
                  <h3>What you gave up</h3>

                  <ul className="plain">
                    <li>
                      Your score:{" "}
                      <b>
                        {Math.max(0, Math.round(sm.score * 100))}%
                      </b>{" "}
                      <small className="muted">
                        (100% = your ideal, 0% = your limit)
                      </small>
                    </li>

                    <li>
                      Price vs your ideal:{" "}
                      {inr(Math.abs(sm.price_given_up))}{" "}
                      {sm.price_given_up > 0 ? "worse" : "better"}
                    </li>

                    <li>
                      Delivery vs your ideal:{" "}
                      {Math.abs(sm.days_given_up)} days{" "}
                      {sm.days_given_up > 0 ? "worse" : "better"}
                    </li>

                    <li>
                      Room left before your limit:{" "}
                      {sm.price_cushion >= 0
                        ? inr(sm.price_cushion)
                        : `${inr(-sm.price_cushion)} beyond your limit`}{" "}
                      and{" "}
                      {sm.days_cushion >= 0
                        ? `${sm.days_cushion} days`
                        : `${-sm.days_cushion} days beyond your limit`}
                    </li>
                  </ul>

                  {sm.near_limit && (
                    <p className="guard">
                      This deal is at or beyond one of your limits.
                    </p>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="card">
              <h3>No agreement yet</h3>

              <p className="muted">
                {s === "seller_review"
                  ? "The agents could not close. The buyer's final offer is waiting for the seller."
                  : deal.no_deal_reason ||
                    "The two sides' limits did not overlap, or the rounds ran out."}
              </p>
            </div>
          )}

          {mine && (
            <div className="card">
              <h3>Your private limits ({side})</h3>

              <ul className="plain">
                <li>
                  {isBuyer ? "Maximum budget" : "Minimum price"}:{" "}
                  <b>{inr(mine.price_limit)}</b>
                </li>

                <li>Ideal price: {inr(mine.ideal_price)}</li>

                <li>
                  {isBuyer ? "Latest delivery" : "Fastest delivery"}:{" "}
                  <b>{mine.delivery_limit} days</b>
                </li>

                <li>
                  Ideal delivery: {mine.ideal_delivery} days
                </li>
              </ul>
            </div>
          )}

          <div className="card">
            <h3>Next step</h3>

            {s === "seller_review" &&
              (isBuyer ? (
                <>
                  <p>
                    The agents could not agree, so your agent's final offer
                    went to {other}:
                  </p>

                  <div className="price">
                    {inr(deal.proposal_price)}
                  </div>

                  <p>{deal.proposal_days} days</p>

                  <p className="muted">
                    If {other} does not answer by{" "}
                    {fmtTime(deal.review_by)}, the deal ends. You'll be
                    notified either way. Nothing is charged.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    The agents could not close. The buyer's final offer is:
                  </p>

                  <div className="price">
                    {inr(deal.proposal_price)}
                  </div>

                  <p>{deal.proposal_days} days</p>

                  {outside.length > 0 ? (
                    <div className="notice">
                      <b>This offer is outside your private limits:</b>{" "}
                      {outside.join("; ")}. Accepting means you override your
                      agent's limit.
                    </div>
                  ) : (
                    <p className="muted">
                      This offer is inside your private limits.
                    </p>
                  )}

                  <div className="row">
                    <button
                      className="btn primary"
                      disabled={disabled}
                      onClick={acceptReview}
                    >
                      Accept this offer
                    </button>

                    <button
                      className="btn"
                      disabled={disabled}
                      onClick={() =>
                        run("review", () => api.review(id, false))
                      }
                    >
                      Decline
                    </button>
                  </div>

                  <p className="muted">
                    Accepting sends it to the buyer for final approval.
                    Answer by {fmtTime(deal.review_by)}.
                  </p>
                </>
              ))}

            {s === "awaiting_approval" && (
              <>
                <p>
                  Buyer: {deal.buyer_approved ? "✓ approved" : "waiting"} ·
                  Seller: {deal.seller_approved ? "✓ approved" : "waiting"}
                </p>

                {!iApproved ? (
                  <div className="row">
                    <button
                      className="btn primary"
                      disabled={disabled}
                      onClick={approve}
                    >
                      Approve this deal
                    </button>

                    <button
                      className="btn"
                      disabled={disabled}
                      onClick={() =>
                        run("decline", () => api.decide(id, false))
                      }
                    >
                      Decline
                    </button>
                  </div>
                ) : (
                  <p className="muted">
                    You approved. Waiting for {other} to approve.
                  </p>
                )}
              </>
            )}

            {s === "approved" &&
              (isBuyer ? (
                <>
                  <p>
                    Both sides approved. PayPal will hold {usd(amountUsd)}{" "}
                    until the seller confirms delivery.
                  </p>

                  <button
                    className="btn primary"
                    disabled={disabled}
                    onClick={() =>
                      run("pay", () => api.pay(id), (result) => {
                        if (result?.approve_url) {
                          window.location.href = result.approve_url;
                        }
                      })
                    }
                  >
                    {busy === "pay"
                      ? "Opening PayPal…"
                      : "Pay with PayPal"}
                  </button>

                  <small className="muted">
                    Sandbox: log in with your Personal test account.
                  </small>
                </>
              ) : (
                <p className="muted">Waiting for {other} to pay.</p>
              ))}

            {s === "payment_pending" &&
              (isBuyer ? (
                <>
                  <p>
                    Your PayPal order is created but not approved yet.
                  </p>

                  {deal.approve_url && (
                    <a className="btn primary" href={deal.approve_url}>
                      Continue to PayPal
                    </a>
                  )}
                </>
              ) : (
                <p className="muted">
                  Waiting for {other} to approve the payment at PayPal.
                </p>
              ))}

            {s === "funds_held" && (
              <>
                <p>
                  The buyer's money is held by PayPal and not yet paid out.
                </p>

                {!isBuyer ? (
                  <button
                    className="btn primary"
                    disabled={disabled}
                    onClick={() =>
                      run("deliver", () => api.deliver(id))
                    }
                  >
                    Confirm delivery and get paid
                  </button>
                ) : (
                  <button
                    className="btn"
                    disabled={disabled}
                    onClick={() =>
                      run("void", () => api.voidFunds(id))
                    }
                  >
                    Delivery missed? Release my funds
                  </button>
                )}

                {cfg?.demo && (
                  <p>
                    <button
                      className="link"
                      disabled={disabled}
                      onClick={() =>
                        run("expire", () => api.expire(id))
                      }
                    >
                      Demo: make the deadline pass
                    </button>
                  </p>
                )}
              </>
            )}

            {s === "paid" && (
              <>
                <p>
                  {deal.outcome === "delivered_late"
                    ? "Delivered late, payment captured."
                    : "Delivered on time. Payment captured."}
                </p>

                {!isBuyer && (
                  <button
                    className="btn"
                    disabled={disabled}
                    onClick={() =>
                      run("refund", () => api.refund(id))
                    }
                  >
                    Refund the buyer
                  </button>
                )}
              </>
            )}

            {s === "voided" && (
              <p>
                The seller missed the deadline, so PayPal released the held
                funds back to the buyer.
              </p>
            )}

            {s === "refunded" && (
              <p>The payment was refunded to the buyer.</p>
            )}

            {s === "declined" && (
              <p>One side declined the deal. Nothing was charged.</p>
            )}

            {s === "no_deal" && (
              <p>No deal was reached. Nothing was charged.</p>
            )}
          </div>

          {deal.history?.length > 0 && (
            <div className="card">
              <h3>Deal activity timeline</h3>

              <ul className="plain">
                {deal.history.map((item, index) => (
                  <li key={item.id || index}>
                    <b>{WHO[item.who] || item.who}</b>:{" "}
                    {label(item.what)}

                    {item.detail ? (
                      <small className="muted">
                        {" "}({item.detail})
                      </small>
                    ) : null}

                    {" "}
                    <small className="muted">
                      {fmtTime(item.at)}
                    </small>
                  </li>
                ))}
              </ul>

              <small className="muted">
                PayPal lines are webhook events whose signature PayPal
                verified.
              </small>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
