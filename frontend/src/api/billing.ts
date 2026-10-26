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
  license_status: 'active' | 'expired' | null;
  expires_at: string | null;
}

export const getBillingUsage = (): Promise<BillingUsage> =>
  apiClient.get<BillingUsage>('/billing/usage').then(r => r.data);

export interface ActivateLicenseResponse {
  license_status: 'active' | 'expired' | null;
  license_plan: string | null;
}

export const activateLicense = (activationCode: string): Promise<ActivateLicenseResponse> =>
  apiClient
    .put<ActivateLicenseResponse>('/settings/license-activation', { activation_code: activationCode })
    .then(r => r.data);
