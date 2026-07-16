export function EnvironmentBanner({ environment }: { environment: "test" | "live" }) {
  if (environment !== "test") {
    return null;
  }
  return (
    <div className="environment-banner">
      TEST MODE — this portal is connected to the Stripe test environment. No real
      charges occur.
    </div>
  );
}
