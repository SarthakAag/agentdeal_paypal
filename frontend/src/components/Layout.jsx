import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Bell from "./Bell";

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [cfg, setCfg] = useState(null);

  useEffect(() => {
    api.config().then(setCfg).catch(() => {});
  }, []);

  async function signOut() {
    await logout();
    nav("/");
  }

  return (
    <>
      <header className="nav">
        <div className="nav-inner">
          <NavLink to="/" className="brand">AgentDeal</NavLink>
          <nav>
            <NavLink to="/" end>Marketplace</NavLink>
            {user?.role === "seller" && <NavLink to="/sell">Sell</NavLink>}
            {user && <NavLink to="/account">My deals</NavLink>}
            {user && <NavLink to="/activity">PayPal activity</NavLink>}
            <NavLink to="/results">How the agents did</NavLink>
          </nav>
          <div className="spacer" />
          {cfg && <span className="tag">{cfg.engine === "lora" ? "Fine-tuned agents" : "Rule-based agents"}</span>}
          {user ? (
            <span className="who">
              <Bell />
              {user.name} <span className="tag">{user.role}</span>
              <button className="link" onClick={signOut}>Sign out</button>
            </span>
          ) : (
            <Link className="btn small primary" to="/login">Sign in</Link>
          )}
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
      <footer className="foot">Runs on the PayPal sandbox. No real money moves. Prices are charged in USD at a fixed rate.</footer>
    </>
  );
}