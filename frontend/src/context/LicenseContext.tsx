import React, { createContext, useContext, useEffect, useState } from 'react';
import { getLicenseInfo } from '../api/license';
import type { LicenseInfo } from '../api/license';

interface LicenseContextValue {
  license: LicenseInfo | null;
  loading: boolean;
}

const DEFAULT_COMMUNITY: LicenseInfo = {
  plan: 'community',
  company: null,
  is_enterprise: false,
  is_business: false,
  expires_at: null,
};

const LicenseContext = createContext<LicenseContextValue>({
  license: DEFAULT_COMMUNITY,
  loading: true,
});

export function LicenseProvider({ children }: { children: React.ReactNode }) {
  const [license, setLicense] = useState<LicenseInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLicenseInfo()
      .then(setLicense)
      .catch(() => setLicense(DEFAULT_COMMUNITY))
      .finally(() => setLoading(false));
  }, []);

  return (
    <LicenseContext.Provider value={{ license, loading }}>
      {children}
    </LicenseContext.Provider>
  );
}

export function useLicenseContext(): LicenseContextValue {
  return useContext(LicenseContext);
}
