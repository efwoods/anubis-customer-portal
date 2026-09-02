import { useCallback, useEffect, useState } from "react";
import { apiRequest, clearSessionToken, getActiveSessionToken } from "./api";
import {
  navigateToApplication,
  readAppReturnUrl,
  resolveApplicationAvatarsUrl,
} from "./appReturn";
import type { CurrentIdentity, PortalConfiguration } from "./types";
import { AnonymousNotice } from "./components/AnonymousNotice";
import { BillingInformationSection } from "./components/BillingInformationSection";
import { EnvironmentBanner } from "./components/EnvironmentBanner";
import { InvoiceHistorySection } from "./components/InvoiceHistorySection";
import { LoginCard } from "./components/LoginCard";
import { PaymentMethodsSection } from "./components/PaymentMethodsSection";
import {
  clearPendingTierChange,
  startPendingTierCheckout,
  storePendingTierChange,
  SubscriptionSection,
} from "./components/SubscriptionSection";
import { ThemeToggle } from "./components/ThemeToggle";
import { UsageSection } from "./components/UsageSection";
import { subscribeToSingleSignOn } from "./singleSignOn";
import { applyTheme, getStoredTheme, toggleTheme, type PortalTheme } from "./theme";

export default function App() {
  const [configuration, setConfiguration] = useState<PortalConfiguration | null>(null);
  const [identity, setIdentity] = useState<CurrentIdentity | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [pendingTier, setPendingTier] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshCounter, setRefreshCounter] = useState(0);
  const [theme, setTheme] = useState<PortalTheme>(() => getStoredTheme());

  const refreshDashboard = useCallback(() => {
    setRefreshCounter((previous) => previous + 1);
  }, []);

  const loadIdentity = useCallback(async () => {
    try {
      const currentIdentity = await apiRequest<CurrentIdentity>("/me");
      setIdentity(currentIdentity);
      // Anonymous visitors are resolved automatically via hashed IP — do not
      // force the login card open.
      if (currentIdentity.kind === "verified") {
        setShowLogin(false);
      }
    } catch (identityError) {
      setIdentity(null);
      // Only a tab that is itself signed in should surface a load failure as an
      // account error; an anonymous tab must not react to another tab's token.
      if (getActiveSessionToken() !== null) {
        setLoadError(
          identityError instanceof Error
            ? identityError.message
            : "Could not load your account.",
        );
      }
    }
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    (async () => {
      try {
        const portalConfiguration =
          await apiRequest<PortalConfiguration>("/config");
        setConfiguration(portalConfiguration);
      } catch {
        setLoadError(
          "The portal server is unreachable. Confirm the server is running and " +
            "VITE_API_BASE_URL points at it.",
        );
        return;
      }
      await loadIdentity();
    })();
  }, [loadIdentity, refreshCounter]);

  // A session handed over by the Neural Nexus application arrives after this
  // component has already drawn the anonymous view, because the exchange is a
  // round trip through two servers. Redrawing on it is what turns that view into
  // the account's own without the customer touching anything.
  useEffect(() => subscribeToSingleSignOn(refreshDashboard), [refreshDashboard]);

  useEffect(() => {
    // Read before the query is stripped below: the address carries both what
    // Checkout did and where the customer came from.
    const searchAtLanding = window.location.search;
    const checkoutResult = new URLSearchParams(searchAtLanding).get("checkout");
    if (!checkoutResult) {
      return;
    }
    window.history.replaceState(null, "", window.location.pathname);
    if (checkoutResult !== "success") {
      return;
    }
    // Checkout attaches the card it charged with allow_redisplay "limited",
    // which Checkout itself will not prefill next time — and if the customer
    // retyped a card they already had, Stripe just created a second copy of it.
    // Reconciling here makes the card reusable and collapses the duplicate, so
    // the wallet the customer returns to is the one they expect.
    // Reconcile first, then leave. The reconcile is why Checkout returns the
    // customer here rather than straight to the application, so the return trip
    // waits for it — and happens whether or not it succeeded, because a card
    // that could not be tidied is no reason to strand somebody on this page.
    const applicationToReturnTo = readAppReturnUrl(searchAtLanding);
    void apiRequest<unknown>("/payment_methods/reconcile", { method: "POST" })
      .catch(() => undefined)
      .finally(() => {
        refreshDashboard();
        if (applicationToReturnTo) {
          navigateToApplication(applicationToReturnTo);
        }
      });
  }, [refreshDashboard]);

  const handleSignOut = async () => {
    // Revoke the Neural Nexus session (best-effort); always clear locally so
    // sign-out never blocks on the server being reachable.
    try {
      await apiRequest<void>("/auth/logout", { method: "POST" });
    } catch {
      // Ignore — the local token is cleared below regardless.
    }
    clearSessionToken();
    clearPendingTierChange();
    setPendingTier(null);
    setIdentity(null);
    refreshDashboard();
  };

  const handleRequestSignupForTier = (tier: string) => {
    storePendingTierChange(tier);
    setPendingTier(tier);
    setShowLogin(true);
  };

  const handleSignedIn = async () => {
    setShowLogin(false);
    try {
      const startedCheckout = await startPendingTierCheckout();
      if (startedCheckout) {
        return;
      }
    } catch {
      // Fall through to dashboard refresh; subscription section can retry.
    }
    setPendingTier(null);
    refreshDashboard();
  };

  if (loadError) {
    return (
      <div className="portal-shell">
        <div className="card error-banner">{loadError}</div>
      </div>
    );
  }

  if (!configuration) {
    return (
      <div className="portal-shell">
        <div className="card">Loading…</div>
      </div>
    );
  }

  const isVerified = identity?.kind === "verified";
  // The page this customer came from when the application sent them here, and
  // the application's front door otherwise.
  // Where "back" goes: the avatar gallery, from wherever the portal is standing.
  // Someone pressing it has finished with billing and wants the application, and
  // returning them to the billing page they came from — embedded or not — is
  // either a reload of the screen they are looking at or a round trip to the one
  // page they were trying to leave. Resuming the exact page is the job of the
  // post-Checkout return above, which is a different journey.
  const returnToApplicationUrl = resolveApplicationAvatarsUrl();

  return (
    <div className="portal-shell">
      <EnvironmentBanner environment={configuration.environment} />
      <header className="portal-header">
        <div>
          <h1>Neural Nexus</h1>
          <p className="subtitle">Customer portal</p>
          {/* The way back to Neural Nexus, present in both places a customer
              can be standing when they need it: here on the portal after
              Checkout returned the tab (the redirect chain ate the history, so
              there is nothing to go Back to), and inside the frame on the
              application's billing page.

              `target="_top"` is what makes the embedded case safe. Without it
              the frame loads the application into itself, and the billing page
              appears inside the billing page — portal and all. */}
          <a
            className="portal-return-link"
            href={returnToApplicationUrl}
            target="_top"
            rel="noopener"
          >
            ← Back to Neural Nexus
          </a>
        </div>
        <div className="header-identity">
          <ThemeToggle
            theme={theme}
            onToggle={() => setTheme((current) => toggleTheme(current))}
          />
          {isVerified ? (
            <>
              <span>{identity?.name || identity?.email}</span>
              <button
                className="link-button"
                onClick={() => {
                  void handleSignOut();
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <button className="primary-button" onClick={() => setShowLogin(true)}>
              Sign in
            </button>
          )}
        </div>
      </header>

      {showLogin && !isVerified ? (
        <LoginCard
          pendingTier={pendingTier}
          onSignedIn={() => {
            void handleSignedIn();
          }}
          onDismiss={() => {
            setShowLogin(false);
            setPendingTier(null);
            clearPendingTierChange();
          }}
        />
      ) : null}

      {!isVerified && identity ? (
        <AnonymousNotice
          identity={identity}
          onSignIn={() => {
            setPendingTier(null);
            setShowLogin(true);
          }}
        />
      ) : null}

      <SubscriptionSection
        isVerified={isVerified}
        refreshCounter={refreshCounter}
        onChanged={refreshDashboard}
        onRequestSignupForTier={handleRequestSignupForTier}
      />
      <UsageSection
        isVerified={isVerified}
        refreshCounter={refreshCounter}
        onChanged={refreshDashboard}
      />
      {isVerified ? (
        <>
          <PaymentMethodsSection
            publishableKey={configuration.publishable_key}
            refreshCounter={refreshCounter}
            onChanged={refreshDashboard}
          />
          <BillingInformationSection
            publishableKey={configuration.publishable_key}
            refreshCounter={refreshCounter}
          />
          <InvoiceHistorySection
            refreshCounter={refreshCounter}
            onChanged={refreshDashboard}
          />
        </>
      ) : null}

      <footer className="portal-footer">
        <span>Powered by Stripe</span>
        <a href="https://stripe.com/legal" target="_blank" rel="noreferrer">
          Terms
        </a>
        <a href="https://stripe.com/privacy" target="_blank" rel="noreferrer">
          Privacy
        </a>
        <a href="mailto:support@neuralnexus.site">Support</a>
      </footer>
    </div>
  );
}
