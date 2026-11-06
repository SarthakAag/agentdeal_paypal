
const BASE = "/api";

function message(detail, fallback) {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`)
      .join("; ");
  }

  return fallback;
}

async function req(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let errorMessage = res.statusText || "Request failed";

    try {
      const data = await res.json();
      errorMessage = message(data.detail, errorMessage);
    } catch {
      // Keep the original status message.
    }

    throw new Error(errorMessage);
  }

  if (res.status === 204) return null;

  return res.json();
}

export const api = {
  // --------------------------------------------------
  // Configuration
  // --------------------------------------------------

  config: () => req("/config"),

  // --------------------------------------------------
  // Authentication
  // --------------------------------------------------

  me: () => req("/auth/me"),

  login: (body) =>
    req("/auth/login", {
      method: "POST",
      body,
    }),

  register: (body) =>
    req("/auth/register", {
      method: "POST",
      body,
    }),

  logout: () =>
    req("/auth/logout", {
      method: "POST",
    }),

  // --------------------------------------------------
  // Marketplace listings
  // --------------------------------------------------

  listings: () => req("/listings"),

  myListings: () => req("/listings/mine"),

  listing: (id) =>
    req(`/listings/${id}`),

  createListing: (body) =>
    req("/listings", {
      method: "POST",
      body,
    }),

  closeListing: (id) =>
    req(`/listings/${id}/close`, {
      method: "POST",
    }),

  // --------------------------------------------------
  // Negotiations
  // --------------------------------------------------

  startNegotiation: (body) =>
    req("/negotiations", {
      method: "POST",
      body,
    }),

  bid: (body) =>
    req("/bids", {
      method: "POST",
      body,
    }),

  negotiations: (listingId) =>
    req(`/negotiations?listing_id=${encodeURIComponent(listingId)}`),

  myDeals: () =>
    req("/negotiations"),

  summary: () =>
    req("/account/summary"),

  deal: (id) =>
    req(`/negotiations/${id}`),

  // --------------------------------------------------
  // Human approval and review
  // --------------------------------------------------

  decide: (id, approve = true) =>
    req(`/negotiations/${id}/decision`, {
      method: "POST",
      body: { approve },
    }),

  review: (id, accept) =>
    req(`/negotiations/${id}/review`, {
      method: "POST",
      body: { accept },
    }),

  // --------------------------------------------------
  // Buyer–seller messaging
  // Requires backend/agentdeal/messages.py
  // --------------------------------------------------

  messages: (id) =>
    req(`/negotiations/${id}/messages`),

  sendMessage: (id, body) =>
    req(`/negotiations/${id}/messages`, {
      method: "POST",
      body: { body },
    }),

  // --------------------------------------------------
  // PayPal payments
  // --------------------------------------------------

  pay: (id) =>
    req(`/negotiations/${id}/pay`, {
      method: "POST",
    }),

  deliver: (id) =>
    req(`/negotiations/${id}/deliver`, {
      method: "POST",
    }),

  voidFunds: (id) =>
    req(`/negotiations/${id}/void`, {
      method: "POST",
      body: {
        reason: "seller_missed_deadline",
      },
    }),

  refund: (id) =>
    req(`/negotiations/${id}/refund`, {
      method: "POST",
      body: {
        reason: "seller_refund",
      },
    }),

  // --------------------------------------------------
  // Activity and deadlines
  // --------------------------------------------------

  activity: () =>
    req("/activity"),

  sweep: () =>
    req("/deadlines/sweep", {
      method: "POST",
    }),

  expire: (id) =>
    req(`/demo/expire/${id}`, {
      method: "POST",
    }),

  // --------------------------------------------------
  // Notifications
  // These require notification routes in the backend.
  // --------------------------------------------------

  notifications: () =>
    req("/notifications"),

  markRead: (ids) =>
    req("/notifications/read", {
      method: "POST",
      body: ids ? { ids } : {},
    }),

  // --------------------------------------------------
  // AI assistance
  // --------------------------------------------------

  assistStatus: () =>
    req("/assist/status"),

  assistMandate: (text, ask_price) =>
    req("/assist/mandate", {
      method: "POST",
      body: {
        text,
        ask_price,
      },
    }),

  narrate: (id) =>
    req(`/negotiations/${id}/narrate`, {
      method: "POST",
    }),

  // --------------------------------------------------
  // Training and evaluation results
  // --------------------------------------------------

  results: () =>
    req("/results"),
};
