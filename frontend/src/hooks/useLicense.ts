import { useLicenseContext } from '../context/LicenseContext';

export interface UseLicenseResult {
  plan: 'community' | 'business' | 'enterprise' | 'trial';
  isEnterprise: boolean;
  isBusiness: boolean;
  company: string | null;
  // "active" | "expired" | null (no code). See app/routers/license.py.
  licenseStatus: 'active' | 'expired' | null;
  loading: boolean;
}

export function useLicense(): UseLicenseResult {
  const { license, licenseStatus, loading } = useLicenseContext();

  return {
    plan: license?.plan ?? 'community',
    isEnterprise: license?.is_enterprise ?? false,
    isBusiness: license?.is_business ?? false,
    company: license?.company ?? null,
    licenseStatus,
    loading,
  };
}
