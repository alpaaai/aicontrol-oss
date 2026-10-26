import { apiClient } from './client';

export interface LicenseInfo {
  plan: 'community' | 'business' | 'enterprise' | 'trial';
  company: string | null;
  is_enterprise: boolean;
  is_business: boolean;
  expires_at: string | null;
}

export const getLicenseInfo = (): Promise<LicenseInfo> =>
  apiClient.get<LicenseInfo>('/license-info').then(r => r.data);

export interface FeatureFlags {
  nl_authoring: boolean;
  simulation: boolean;
  hitl: boolean;
  compliance_reports: boolean;
}

export interface LicenseFeatures {
  tier: 'free' | 'business' | 'enterprise';
  features: FeatureFlags;
  // "active" | "expired" | null (no code). See app/routers/license.py.
  license_status: 'active' | 'expired' | null;
}

export const getLicenseFeatures = (): Promise<LicenseFeatures> =>
  apiClient.get<LicenseFeatures>('/license/features').then(r => r.data);
