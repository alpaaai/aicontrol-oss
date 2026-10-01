import { useLicenseContext } from '../context/LicenseContext';

export interface UseLicenseResult {
  plan: 'community' | 'business' | 'enterprise' | 'trial';
  isEnterprise: boolean;
  isBusiness: boolean;
  company: string | null;
  // "active" | "past_due" | "canceled" | "unreachable" | null (community,
  // or business/enterprise not yet synced). See app/routers/license.py.
  licenseStatus: 'active' | 'past_due' | 'canceled' | 'unreachable' | null;
  // True when this org had (or has) a paid plan but its subscription needs
  // attention -- distinct from "never subscribed" (plans/v4 task 25).
  needsReactivation: boolean;
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
    needsReactivation:
      licenseStatus === 'past_due' || licenseStatus === 'canceled' || licenseStatus === 'unreachable',
    loading,
  };
}
