
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

export default function DealChat({ dealId, mySide }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const lastIdRef = useRef(0);

  const loadMessages = useCallback(async () => {
    try {
      const data = await api.messages(dealId);
      setMessages(data.items || []);
      lastIdRef.current = Math.max(
        0,
        ...(data.items || []).map((m) => m.id)
      );
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, [dealId]);

  useEffect(() => {
    loadMessages();

    const timer = setInterval(() => {
      if (!document.hidden) loadMessages();
    }, 4000);

    return () => clearInterval(timer);
  }, [loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(e) {
    e.preventDefault();

    const message = text.trim();
    if (!message || sending) return;

    setSending(true);
    setError("");

    try {
      await api.sendMessage(dealId, message);
      setText("");
      await loadMessages();
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  function time(value) {
    if (!value) return "";
    const date = new Date(value.replace(" ", "T") + "Z");
    return Number.isNaN(date.getTime())
      ? value
      : date.toLocaleString();
  }

  return (
    <section className="card deal-chat">
      <div className="deal-chat-header">
        <div>
          <h3>Buyer–Seller Conversation</h3>
          <p className="muted">
            Direct messages between both parties
          </p>
        </div>
        <span className="chat-live">Deal chat</span>
      </div>

      <div className="deal-chat-messages">
        {messages.length === 0 && (
          <p className="muted chat-empty">
            No messages yet. Start the conversation.
          </p>
        )}

        {messages.map((message) => {
          const mine = message.sender_side === mySide;

          return (
            <div
              key={message.id}
              className={`chat-message ${
                mine ? "chat-mine" : "chat-theirs"
              }`}
            >
              <div className="chat-message-meta">
                <b>
                  {mine
                    ? "You"
                    : message.sender_side === "buyer"
                    ? "Buyer"
                    : "Seller"}
                </b>
                <small>{time(message.created_at)}</small>
              </div>

              <div className="chat-bubble">
                {message.body}
              </div>
            </div>
          );
        })}

        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="chat-error" role="alert">
          {error}
        </p>
      )}

      <form className="deal-chat-form" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Write a message..."
          maxLength={2000}
          disabled={sending}
        />

        <button
          className="btn primary"
          type="submit"
          disabled={sending || !text.trim()}
        >
          {sending ? "Sending..." : "Send"}
        </button>
      </form>

      <small className="muted">
        Messages are visible to both parties involved in this deal.
      </small>
    </section>
  );
}
