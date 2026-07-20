import { FormEvent, useState } from "react";
import { apiRequest, setSessionToken } from "../api";

interface LoginCardProps {
  onSignedIn: () => void;
  onDismiss: () => void;
  /** When set, copy explains this sign-in continues the free Pro trial checkout. */
  pendingTier?: string | null;
}

type AuthMode = "signin" | "signup";

export function LoginCard({ onSignedIn, onDismiss, pendingTier }: LoginCardProps) {
  const isProTrialSignup = pendingTier === "pro";
  // A pending Pro-trial CTA is a new-account intent, so open on the signup form;
  // returning users can toggle to sign in.
  const [mode, setMode] = useState<AuthMode>(isProTrialSignup ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setErrorMessage(null);
    setPassword("");
  };

  const signIn = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      const session = await apiRequest<{ token: string }>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setSessionToken(session.token);
      onSignedIn();
    } catch (signInError) {
      setErrorMessage(
        signInError instanceof Error ? signInError.message : "Sign-in failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const signUp = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      await apiRequest<{ ok: boolean }>("/auth/signup", {
        method: "POST",
        body: { email, password, name: name || null },
      });
      setNoticeMessage(
        "Account created. Check your email to verify it, then sign in below.",
      );
      switchMode("signin");
    } catch (signUpError) {
      setErrorMessage(
        signUpError instanceof Error ? signUpError.message : "Sign-up failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const heading =
    mode === "signup"
      ? isProTrialSignup
        ? "Sign up for free Pro trial"
        : "Create an account"
      : "Sign in";

  return (
    <section className="card login-card">
      <div className="card-header-row">
        <h2>{heading}</h2>
        <button className="link-button" onClick={onDismiss}>
          Close
        </button>
      </div>

      {mode === "signin" ? (
        <form onSubmit={signIn} className="stacked-form">
          <p>Sign in with your Neural Nexus email and password.</p>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              placeholder="you@example.com"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <button className="primary-button" disabled={busy || !email || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="muted">
            Don't have an account?{" "}
            <button
              type="button"
              className="link-button"
              onClick={() => switchMode("signup")}
              disabled={busy}
            >
              Create an account
            </button>
          </p>
        </form>
      ) : (
        <form onSubmit={signUp} className="stacked-form">
          <p>
            {isProTrialSignup ? (
              <>
                Create your Neural Nexus account. After verifying your email and
                signing in, we open Stripe Checkout for the free Pro trial.
              </>
            ) : (
              <>Create your Neural Nexus account with an email and password.</>
            )}
          </p>
          <label>
            Name (optional)
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ada Lovelace"
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              placeholder="you@example.com"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          <button className="primary-button" disabled={busy || !email || !password}>
            {busy ? "Creating account…" : "Create account"}
          </button>
          <p className="muted">
            Already have an account?{" "}
            <button
              type="button"
              className="link-button"
              onClick={() => switchMode("signin")}
              disabled={busy}
            >
              Back to sign in
            </button>
          </p>
        </form>
      )}

      {noticeMessage ? <p className="notice-text">{noticeMessage}</p> : null}
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
