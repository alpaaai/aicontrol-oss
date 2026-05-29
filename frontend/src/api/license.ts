import { apiClient } from './client';

export interface LicenseInfo {
  plan: 'community' | 'business' | 'enterprise';
  company: string | null;
  is_enterprise: boolean;
  is_business: boolean;
  expires_at: string | null;
}

export const getLicenseInfo = (): Promise<LicenseInfo> =>
  apiClient.get<LicenseInfo>('/license-info').then(r => r.data);
