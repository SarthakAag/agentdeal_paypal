import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { api } from "./api";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(
    () => api.me().then((r) => setUser(r.user)).catch(() => setUser(null)).finally(() => setReady(true)),
    []
  );
  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = {
    user,
    ready,
    async login(email, password) {
      const r = await api.login({ email, password });
      setUser(r.user);
    },
    async register(body) {
      const r = await api.register(body);
      setUser(r.user);
    },
    async logout() {
      await api.logout();
      setUser(null);
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

// Wraps pages that need a signed-in user, optionally of one role.
export function RequireAuth({ role }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <p>Loading…</p>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />;
  if (role && user.role !== role) {
    return (
      <div className="card">
        <p>This page is for {role} accounts. You are signed in as a {user.role}.</p>
      </div>
    );
  }
  return <Outlet />;
}