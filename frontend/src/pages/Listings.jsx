import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Listings() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listings()
      .then(setItems)
      .catch(() => setError("Unable to load marketplace listings."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="loading">Loading marketplace...</div>;
  }

  return (
    <section className="marketplace">
      <div className="marketplace-heading">
        <div>
          <p className="eyebrow">AI-POWERED COMMERCE</p>
          <h1>Marketplace</h1>
          <p>
            Browse products and let AI agents negotiate a fair deal for you.
          </p>
        </div>

        <Link className="btn primary" to="/sell">
          List a product
        </Link>
      </div>

      {error && <p className="error">{error}</p>}

      {!items.length && !error ? (
        <div className="empty">
          <h2>No listings yet</h2>
          <p>Be the first seller to list a product.</p>
        </div>
      ) : (
        <div className="grid">
          {items.map((item) => (
            <article className="card listing-card" key={item.id}>
              {item.image_url ? (
                <img
                  className="listing-image"
                  src={item.image_url}
                  alt={item.title || item.name || "Product"}
                />
              ) : (
                <div className="listing-image listing-image-placeholder">
                  No image
                </div>
              )}

              <div className="listing-content">
                <h2 className="listing-title">
                  {item.title || item.name}
                </h2>

                {item.description && (
                  <p className="muted">{item.description}</p>
                )}

                <div className="listing-price">
                  ${Number(item.price || 0).toFixed(2)}
                </div>

                <Link
                  className="btn primary block"
                  to={`/deal/${item.id}`}
                >
                  Negotiate deal
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
