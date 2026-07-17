import { useCallback, useEffect, useState } from "react";
import { apiRequest, clearSessionToken, getSessionToken } from "./api";
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
      if (getSessionToken() !== null) {
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

  useEffect(() => {
    const checkoutResult = new URLSearchParams(window.location.search).get("checkout");
    if (checkoutResult) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  const handleSignOut = () => {
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

  return (
    <div className="portal-shell">
      <EnvironmentBanner environment={configuration.environment} />
      <header className="portal-header">
        <div>
          <h1>Neural Nexus</h1>
          <p className="subtitle">Customer portal</p>
        </div>
        <div className="header-identity">
          <ThemeToggle
            theme={theme}
            onToggle={() => setTheme((current) => toggleTheme(current))}
          />
          {isVerified ? (
            <>
              <span>{identity?.name || identity?.email}</span>
              <button className="link-button" onClick={handleSignOut}>
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
          <BillingInformationSection refreshCounter={refreshCounter} />
          <InvoiceHistorySection refreshCounter={refreshCounter} />
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
      </footer>
    </div>
  );
}
