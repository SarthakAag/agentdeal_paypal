
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { ErrorBox, Field } from "../components/Ui";

// Local demo accounts created by scripts/seed_demo.py
const DEMO_PW = "demo-pass-123";

// Backend URL:
// Local development: uses Vite proxy.
// Production: uses the Render backend.
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/+$/, "");

const ERRORS = {
  failed:
    "PayPal sign-in didn't complete. Try again, or use email and password below.",
  noemail:
    "PayPal didn't share an email address, so we couldn't create the account.",
};

export default function Login() {
  const { user, login, register } = useAuth();

  const nav = useNavigate();
  const loc = useLocation();
  const [params] = useSearchParams();

  const from = loc.state?.from || "/";

  const [role, setRole] = useState("buyer");
  const [mode, setMode] = useState("login");

  const [f, setF] = useState({
    name: "",
    email: "",
    password: "",
  });

  const [err, setErr] = useState(
    ERRORS[params.get("error")] || ""
  );

  const [busy, setBusy] = useState(false);
  const [cfg, setCfg] = useState(null);

  const set = (k) => (e) =>
    setF({ ...f, [k]: e.target.value });

  // Load application configuration.
  useEffect(() => {
    api.config()
      .then(setCfg)
      .catch(() => {});
  }, []);

  // Redirect authenticated users.
  useEffect(() => {
    if (user) {
      nav(from, { replace: true });
    }
  }, [user, nav, from]);

  // PayPal OAuth login URL.
  const paypalLoginUrl =
    `${API_BASE}/api/auth/paypal/login?role=${encodeURIComponent(role)}`;

  async function submit(e) {
    e.preventDefault();

    setErr("");
    setBusy(true);

    try {
      if (mode === "login") {
        await login(f.email, f.password);
      } else {
        await register({
          ...f,
          role,
        });
      }
    } catch (e2) {
      setErr(e2.message);
      setBusy(false);
    }
  }

  return (
    <div className="signin">
      <h1>Sign in to AgentDeal</h1>

      <p className="muted">
        Your PayPal account is your identity here.
        We only read your email address.
      </p>

      <fieldset className="roles">
        <legend>
          First time here? Choose how you'll use it
        </legend>

        {[
          [
            "buyer",
            "Buyer",
            "Send an agent to negotiate for you",
          ],
          [
            "seller",
            "Seller",
            "List items with private limits",
          ],
        ].map(([v, t, d]) => (
          <label
            key={v}
            className={role === v ? "on" : ""}
          >
            <input
              type="radio"
              name="role"
              value={v}
              checked={role === v}
              onChange={() => setRole(v)}
            />

            <b>{t}</b>
            <span>{d}</span>
          </label>
        ))}
      </fieldset>

      {/* PayPal login now redirects to the backend domain */}
      <a
        className="btn paypal"
        href={paypalLoginUrl}
      >
        Continue with PayPal
      </a>

      <small className="muted">
        Existing accounts keep their original role.
      </small>

      <ErrorBox>{err}</ErrorBox>

      <details className="alt" open={!!err}>
        <summary>
          Use email and password instead
        </summary>

        <form
          className="form"
          onSubmit={submit}
        >
          {mode === "register" && (
            <Field label="Your name">
              <input
                required
                minLength={2}
                maxLength={60}
                value={f.name}
                onChange={set("name")}
              />
            </Field>
          )}

          <Field label="Email">
            <input
              required
              type="email"
              value={f.email}
              onChange={set("email")}
              autoComplete="email"
            />
          </Field>

          <Field
            label="Password"
            hint={
              mode === "register"
                ? "At least 8 characters. Uses the role chosen above."
                : undefined
            }
          >
            <input
              required
              type="password"
              minLength={mode === "register" ? 8 : 1}
              value={f.password}
              onChange={set("password")}
              autoComplete={
                mode === "login"
                  ? "current-password"
                  : "new-password"
              }
            />
          </Field>

          <div className="row">
            <button
              className="btn primary"
              disabled={busy}
            >
              {mode === "login"
                ? "Sign in"
                : "Create account"}
            </button>

            <button
              type="button"
              className="link"
              onClick={() => {
                setErr("");
                setMode(
                  mode === "login"
                    ? "register"
                    : "login"
                );
              }}
            >
              {mode === "login"
                ? "Create an account"
                : "I already have one"}
            </button>
          </div>

          {cfg?.demo && (
            <div className="row">
              <small className="muted">
                Demo:
              </small>

              {["buyer", "seller"].map((r) => (
                <button
                  type="button"
                  key={r}
                  className="link"
                  onClick={() => {
                    setMode("login");

                    setF({
                      ...f,
                      email: `${r}@demo.test`,
                      password: DEMO_PW,
                    });
                  }}
                >
                  {r}
                </button>
              ))}
            </div>
          )}
        </form>
      </details>
    </div>
  );
}
