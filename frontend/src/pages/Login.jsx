import { useEffect, useState } from "react";
import {
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { useAuth } from "../auth";
import { ErrorBox, Field } from "../components/Ui";

const DEMO_ACCOUNTS_ENABLED =
  import.meta.env.VITE_DEMO_ACCOUNTS_ENABLED === "true";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(
  /\/+$/,
  ""
);

const DEMO_ACCOUNTS = {
  buyer: {
    email: "buyer@demo.test",
    password: "demo-pass-123",
  },
  seller: {
    email: "seller@demo.test",
    password: "demo-pass-123",
  },
};

const ERRORS = {
  failed:
    "PayPal sign-in didn't complete. Try again, or use your AgentDeal account.",
  noemail:
    "PayPal didn't share an email address, so we couldn't create the account.",
  email_unverified:
    "Your PayPal email could not be verified. Please use your AgentDeal account.",
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
  const [err, setErr] = useState(ERRORS[params.get("error")] || "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) nav(from, { replace: true });
  }, [user, nav, from]);

  const paypalLoginUrl =
    `${API_BASE}/api/auth/paypal/login?role=${encodeURIComponent(role)}`;

  function set(k) {
    return (e) =>
      setF((current) => ({
        ...current,
        [k]: e.target.value,
      }));
  }

  function selectDemoAccount(selectedRole) {
    const account = DEMO_ACCOUNTS[selectedRole];

    setRole(selectedRole);
    setMode("login");
    setErr("");

    setF({
      name: "",
      email: account.email,
      password: account.password,
    });
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);

    try {
      if (mode === "login") {
        await login(f.email, f.password);
      } else {
        await register({ ...f, role });
      }
    } catch (e2) {
      setErr(e2.message || "Unable to sign in.");
      setBusy(false);
    }
  }

  return (
    <div className="signin">
      <h1>Welcome to AgentDeal</h1>

      <p className="muted">
        Explore AI-powered negotiations and smarter commerce.
        You don't need a PayPal account to try the demo.
      </p>

      {DEMO_ACCOUNTS_ENABLED && (
        <section className="demo-section">
          <h2>Try AgentDeal with a demo account</h2>

          <p className="muted">
            Choose a shared demo account. Credentials are automatically
            filled into the login form.
          </p>

          <div className="demo-cards">
            <div className="card demo-card">
              <h3>Demo Buyer</h3>
              <p>
                Explore products, negotiate prices and manage buyer deals.
              </p>
              <p className="muted">buyer@demo.test</p>

              <button
                type="button"
                className="btn primary"
                onClick={() => selectDemoAccount("buyer")}
              >
                Continue as Demo Buyer
              </button>
            </div>

            <div className="card demo-card">
              <h3>Demo Seller</h3>
              <p>
                Create listings, negotiate with buyers and manage seller
                deals.
              </p>
              <p className="muted">seller@demo.test</p>

              <button
                type="button"
                className="btn primary"
                onClick={() => selectDemoAccount("seller")}
              >
                Continue as Demo Seller
              </button>
            </div>
          </div>

          <small className="muted">
            Shared demo accounts are for testing only. Do not store personal
            or confidential information. PayPal payments are disabled for
            demo accounts.
          </small>
        </section>
      )}

      <hr />

      <h2>Optional: Continue with PayPal</h2>

      <p className="muted">
        You will be redirected to PayPal's official website to authorize
        access to your basic account information. AgentDeal never asks for
        your PayPal password.
      </p>

      <fieldset className="roles">
        <legend>Choose your account role</legend>

        {[
          ["buyer", "Buyer", "Send an agent to negotiate for you"],
          ["seller", "Seller", "List items with private limits"],
        ].map(([value, title, description]) => (
          <label
            key={value}
            className={role === value ? "on" : ""}
          >
            <input
              type="radio"
              name="role"
              value={value}
              checked={role === value}
              onChange={() => setRole(value)}
            />

            <b>{title}</b>
            <span>{description}</span>
          </label>
        ))}
      </fieldset>

      <a className="btn paypal" href={paypalLoginUrl}>
        Continue with PayPal
      </a>

      <ErrorBox>{err}</ErrorBox>

      <details className="alt" open={!!err || !!f.email}>
        <summary>
          {DEMO_ACCOUNTS_ENABLED
            ? "Use your AgentDeal account"
            : "Use email and password"}
        </summary>

        <form className="form" onSubmit={submit}>
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

          <Field label="AgentDeal email">
            <input
              required
              type="email"
              value={f.email}
              onChange={set("email")}
              autoComplete="email"
            />
          </Field>

          <Field label="AgentDeal password">
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

          <div className="row auth-actions">
            <button
              className="btn primary"
              disabled={busy}
              type="submit"
            >
              {busy
                ? "Please wait..."
                : mode === "login"
                  ? "Sign in"
                  : "Create account"}
            </button>

            <button
              type="button"
              className="link"
              onClick={() => {
                setErr("");
                setMode((current) =>
                  current === "login" ? "register" : "login"
                );
              }}
            >
              {mode === "login"
                ? "Create an account"
                : "I already have an account"}
            </button>
          </div>
        </form>
      </details>
    </div>
  );
}
