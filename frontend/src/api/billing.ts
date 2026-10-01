import { apiClient } from './client';

export interface MonthUsage {
  period: string;
  intercepts: number;
}

export interface BillingUsage {
  plan: 'community' | 'business' | 'enterprise' | 'trial';
  company: string | null;
  annual_price_usd: number;
  retention_days: number | null;
  features: string[];
  this_month: MonthUsage;
  last_month: MonthUsage;
  manage_subscription_url: string | null;
  upgrade_url: string | null;
  license_status: 'active' | 'past_due' | 'canceled' | 'unreachable' | 'expired' | null;
  license_synced_at: string | null;
}

export const getBillingUsage = (): Promise<BillingUsage> =>
  apiClient.get<BillingUsage>('/billing/usage').then(r => r.data);

export interface ActivateLicenseResponse {
  license_status: 'active' | 'past_due' | 'canceled' | 'unreachable' | null;
  license_plan: string | null;
  license_synced_at: string | null;
}

export const activateLicense = (activationCode: string): Promise<ActivateLicenseResponse> =>
  apiClient
    .put<ActivateLicenseResponse>('/settings/license-activation', { activation_code: activationCode })
    .then(r => r.data);
