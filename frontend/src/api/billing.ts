import { apiClient } from './client';

export interface MonthUsage {
  period: string;
  intercepts: number;
  estimated_cost_usd: number;
}

export interface BillingUsage {
  plan: 'community' | 'business' | 'enterprise';
  company: string | null;
  monthly_base_usd: number;
  rate_per_million: number;
  retention_days: number | null;
  features: string[];
  this_month: MonthUsage;
  last_month: MonthUsage;
  manage_subscription_url: string | null;
  upgrade_url: string | null;
}

export const getBillingUsage = (): Promise<BillingUsage> =>
  apiClient.get<BillingUsage>('/billing/usage').then(r => r.data);
