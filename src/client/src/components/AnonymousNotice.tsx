import type { CurrentIdentity } from "../types";

interface AnonymousNoticeProps {
  identity: CurrentIdentity;
  onSignIn: () => void;
}

export function AnonymousNotice({ identity, onSignIn }: AnonymousNoticeProps) {
  return (
    <section className="card anonymous-notice">
      <h2>Browsing as anonymous</h2>
      {identity.customer_id ? (
        <p>
          You are currently an anonymous user. Usage below is read-only until you
          sign up. To start the free Pro trial (to create avatars, upload documents, and more!) use{" "}
          <strong>Sign up for free Pro trial</strong> in the plan section.
        </p>
      ) : (
        <p>
          You have not yet used the Neural Nexus. There is no active metered usage record for your anonymous usage. Sign up for the free Pro trial below, or sign in if you already
          have an account.
        </p>
      )}
      <div className="button-row">
        <button className="link-button" onClick={onSignIn}>
          I already have an account
        </button>
      </div>
    </section>
  );
}
