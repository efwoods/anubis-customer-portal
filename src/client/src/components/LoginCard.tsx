import { FormEvent, useState } from "react";
import { apiRequest, setSessionToken } from "../api";

interface LoginCardProps {
  onSignedIn: () => void;
  onDismiss: () => void;
  /** When set, copy explains this sign-in continues the free Pro trial checkout. */
  pendingTier?: string | null;
}

export function LoginCard({ onSignedIn, onDismiss, pendingTier }: LoginCardProps) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeRequested, setCodeRequested] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isProTrialSignup = pendingTier === "pro";

  const requestCode = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      await apiRequest<void>("/auth/request_otp", {
        method: "POST",
        body: { email },
      });
      setCodeRequested(true);
    } catch (requestError) {
      setErrorMessage(
        requestError instanceof Error ? requestError.message : "Could not send the code.",
      );
    } finally {
      setBusy(false);
    }
  };

  const verifyCode = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      const verification = await apiRequest<{ token: string }>("/auth/verify_otp", {
        method: "POST",
        body: { email, code },
      });
      setSessionToken(verification.token);
      onSignedIn();
    } catch (verifyError) {
      setErrorMessage(
        verifyError instanceof Error ? verifyError.message : "Verification failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card login-card">
      <div className="card-header-row">
        <h2>{isProTrialSignup ? "Sign up for free Pro trial" : "Sign in"}</h2>
        <button className="link-button" onClick={onDismiss}>
          Close
        </button>
      </div>
      {!codeRequested ? (
        <form onSubmit={requestCode} className="stacked-form">
          <p>
            {isProTrialSignup ? (
              <>
                Enter the email for your Neural Nexus account. After the one-time
                code, we open Stripe Checkout for the free Pro trial.
              </>
            ) : (
              <>
                Enter the email on your Neural Nexus account and we will send a
                one-time sign-in code.
              </>
            )}
          </p>
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
          <button className="primary-button" disabled={busy || !email}>
            {busy ? "Sending…" : "Send code"}
          </button>
        </form>
      ) : (
        <form onSubmit={verifyCode} className="stacked-form">
          <p>
            If an account exists for <strong>{email}</strong>, a 6-digit code was
            sent. Enter the code below (the code expires in 10 minutes).
          </p>
          <label>
            One-time code
            <input
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
              placeholder="123456"
            />
          </label>
          <div className="button-row">
            <button className="primary-button" disabled={busy || code.length !== 6}>
              {busy
                ? "Verifying…"
                : isProTrialSignup
                  ? "Verify and start trial"
                  : "Verify and sign in"}
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => setCodeRequested(false)}
              disabled={busy}
            >
              Use a different email
            </button>
          </div>
        </form>
      )}
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
