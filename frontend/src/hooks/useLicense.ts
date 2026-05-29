import { useLicenseContext } from '../context/LicenseContext';

export interface UseLicenseResult {
  plan: 'community' | 'business' | 'enterprise';
  isEnterprise: boolean;
  isBusiness: boolean;
  company: string | null;
  loading: boolean;
}

export function useLicense(): UseLicenseResult {
  const { license, loading } = useLicenseContext();

  return {
    plan: license?.plan ?? 'community',
    isEnterprise: license?.is_enterprise ?? false,
    isBusiness: license?.is_business ?? false,
    company: license?.company ?? null,
    loading,
  };
}
