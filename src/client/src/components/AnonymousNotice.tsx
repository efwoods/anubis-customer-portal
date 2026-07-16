import type { CurrentIdentity } from "../types";

interface AnonymousNoticeProps {
  identity: CurrentIdentity;
  nnApiBaseUrl: string;
  onSignIn: () => void;
}

export function AnonymousNotice({ identity, nnApiBaseUrl, onSignIn }: AnonymousNoticeProps) {
  return (
    <section className="card anonymous-notice">
      <h2>You are browsing anonymously</h2>
      {identity.customer_id ? (
        <p>
          Your anonymous free-tier usage (tracked by network address) is shown below.
          To subscribe, manage payment methods, or keep your history across devices,
          create a Neural Nexus account.
        </p>
      ) : (
        <p>
          No anonymous usage record exists for this network address yet. Create a
          Neural Nexus account to subscribe, or sign in if you already have one.
        </p>
      )}
      <div className="button-row">
        <a
          className="primary-button"
          href={`${nnApiBaseUrl}/docs#/default/signup_signup_post`}
          target="_blank"
          rel="noreferrer"
        >
          Create an account
        </a>
        <button className="link-button" onClick={onSignIn}>
          I already have an account
        </button>
      </div>
    </section>
  );
}
