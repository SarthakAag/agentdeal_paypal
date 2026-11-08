import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Bell from "./Bell";

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const [cfg, setCfg] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    api.config().then(setCfg).catch(() => {});
  }, []);

  async function signOut() {
    setMenuOpen(false);
    await logout();
    nav("/");
  }

  const closeMenu = () => setMenuOpen(false);

  return (
    <>
      <header className="nav">
        <div className="nav-inner">
          <div className="nav-topline">
            <Link to="/" className="brand" onClick={closeMenu}>
              AgentDeal
            </Link>

            <button
              type="button"
              className="nav-toggle"
              aria-label={
                menuOpen
                  ? "Close navigation menu"
                  : "Open navigation menu"
              }
              aria-expanded={menuOpen}
              aria-controls="agentdeal-navigation"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? "✕ Close" : "☰ Menu"}
            </button>
          </div>

          <div
            id="agentdeal-navigation"
            className={`nav-content ${menuOpen ? "open" : ""}`}
          >
            <nav aria-label="Main navigation">
              <NavLink to="/" end onClick={closeMenu}>
                Marketplace
              </NavLink>

              {user?.role === "seller" && (
                <NavLink to="/sell" onClick={closeMenu}>
                  Sell
                </NavLink>
              )}

              {user && (
                <NavLink to="/account" onClick={closeMenu}>
                  My deals
                </NavLink>
              )}

              {user && (
                <NavLink to="/activity" onClick={closeMenu}>
                  PayPal activity
                </NavLink>
              )}

              <NavLink to="/results" onClick={closeMenu}>
                How the agents did
              </NavLink>
            </nav>

            <div className="spacer" />

            <div className="nav-actions">
              {cfg && (
                <span className="tag">
                  {cfg.engine === "lora"
                    ? "Fine-tuned agents"
                    : "Rule-based agents"}
                </span>
              )}

              {user ? (
                <span className="who">
                  <Bell />
                  <span className="who-name">{user.name}</span>
                  <span className="tag">{user.role}</span>

                  <button className="link" onClick={signOut}>
                    Sign out
                  </button>
                </span>
              ) : (
                <Link
                  className="btn small primary"
                  to="/login"
                  onClick={closeMenu}
                >
                  Sign in
                </Link>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="page">
        <Outlet />
      </main>

      <footer className="foot">
        Runs on the PayPal sandbox. No real money moves. Prices are charged
        in USD at a fixed rate.
      </footer>
    </>
  );
}
