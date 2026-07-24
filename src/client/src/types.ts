export interface PortalConfiguration {
  publishable_key: string;
  environment: "test" | "live";
  nn_api_base_url: string;
}

export interface CurrentIdentity {
  kind: "verified" | "anonymous";
  customer_id: string | null;
  email: string | null;
  name: string | null;
}

export interface TierCatalogMeter {
  meter_event_name: string;
  monthly_allotment: number;
  overage_price_per_million: number | null;
  overage_price_per_unit_usd: number | null;
  unit: "tokens" | "units";
}

export interface TierCatalogEntry {
  tier: "free" | "pro" | "premium";
  display_name: string;
  monthly_base_fee_usd: number;
  trial_period_days: number;
  meters: TierCatalogMeter[];
}

export interface SubscriptionStatus {
  kind: "verified" | "anonymous";
  customer_id: string | null;
  email: string | null;
  tier: "free" | "pro" | "premium";
  status: string | null;
  subscription_id: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  cancel_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  pending_downgrade_tier: string | null;
  monthly_base_fee_usd: number;
  pay_per_use_enabled: boolean;
  /** Which tier's free trial a signup grants (null when none is offered). */
  trial_tier: string | null;
  /** One trial per Stripe customer ever — true once this customer has used it. */
  trial_already_used: boolean;
  trialing: boolean;
  /** Whole days left in the running trial; null when not trialing. */
  trial_days_remaining: number | null;
  tier_catalog: TierCatalogEntry[];
}

export interface MeterUsage {
  monthly_allotment: number;
  used_to_date: number;
  remaining: number;
  /** Usage past the included allotment — billable when pay-per-use is on. */
  over_allotment: number;
  overage_price_per_million: number | null;
  overage_price_per_unit_usd: number | null;
  unit: "tokens" | "units";
}

export interface UsageReport {
  tier: string;
  status: string | null;
  trialing: boolean;
  pay_per_use_enabled: boolean;
  usage_period_start: string;
  usage_period_end: string;
  meters: Record<string, MeterUsage>;
}

export interface RefundResult {
  refund_id: string;
  status: string;
  subscription_action: string;
  subscription_tier?: string | null;
  message: string;
}

export interface InvoiceSummary {
  invoice_id: string;
  created: number;
  status: string;
  amount_due: number;
  amount_paid: number;
  currency: string;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
  line_descriptions: string[];
  refundable: boolean;
  refunded: boolean;
}

export interface PaymentMethodSummary {
  payment_method_id: string;
  brand: string | null;
  last4: string | null;
  exp_month: number | null;
  exp_year: number | null;
  is_default: boolean;
}

export interface BillingAddress {
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
}

export interface BillingInformation {
  name: string | null;
  email: string | null;
  phone: string | null;
  address: BillingAddress | null;
}

export interface SubscriptionActionResult {
  action: string;
  message: string;
  url?: string;
}
