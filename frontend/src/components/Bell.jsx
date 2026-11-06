
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { fmtTime } from "../format";

export default function Bell() {
  const nav = useNavigate();
  const box = useRef(null);

  const [data, setData] = useState({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);

  const load = useCallback(
    () => api.notifications().then(setData).catch(() => {}),
    []
  );

  useEffect(() => {
    load();

    const t = setInterval(() => {
      if (!document.hidden) load();
    }, 20000);

    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    const away = (e) => {
      if (box.current && !box.current.contains(e.target)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  async function go(n) {
    setOpen(false);

    if (!n.is_read) {
      await api.markRead([n.id]).catch(() => {});
      await load();
    }

    if (n.negotiation_id) {
      nav(`/deals/${n.negotiation_id}`);
    }
  }

  async function readAll() {
    try {
      await api.markRead();
      await load();
    } catch {
      // The existing notification state remains visible if the request fails.
    }
  }

  return (
    <div className="bell" ref={box}>
      <button
        className="bell-btn"
        aria-label={`Notifications, ${data.unread} unread`}
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
          if (!open) load();
        }}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9" />
          <path d="M10 19a2 2 0 0 0 4 0" />
        </svg>

        {data.unread > 0 && (
          <span className="bell-count">
            {data.unread > 99 ? "99+" : data.unread}
          </span>
        )}
      </button>

      {open && (
        <div className="bell-panel" role="region" aria-label="Notifications">
          <div className="bell-head">
            <b>Notifications</b>

            {data.unread > 0 && (
              <button className="link" onClick={readAll}>
                Mark all read
              </button>
            )}
          </div>

          {data.items.length === 0 && (
            <p
              className="muted"
              style={{ padding: ".7rem .75rem", margin: 0 }}
            >
              Nothing yet.
            </p>
          )}

          {data.items.map((n) => (
            <button
              key={n.id}
              className={`bell-item ${n.is_read ? "" : "unread"}`}
              onClick={() => go(n)}
            >
              {n.text}
              <small>{fmtTime(n.created)}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
