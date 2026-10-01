import React, { createContext, useContext, useEffect, useState } from 'react';
import { getLicenseInfo, getLicenseFeatures } from '../api/license';
import type { LicenseInfo, LicenseFeatures } from '../api/license';

interface LicenseContextValue {
  license: LicenseInfo | null;
  licenseStatus: LicenseFeatures['license_status'];
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
  licenseStatus: null,
  loading: true,
});

export function LicenseProvider({ children }: { children: React.ReactNode }) {
  const [license, setLicense] = useState<LicenseInfo | null>(null);
  const [licenseStatus, setLicenseStatus] = useState<LicenseFeatures['license_status']>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getLicenseInfo().catch(() => DEFAULT_COMMUNITY),
      getLicenseFeatures().catch(() => null),
    ]).then(([info, features]) => {
      setLicense(info);
      setLicenseStatus(features?.license_status ?? null);
      setLoading(false);
    });
  }, []);

  return (
    <LicenseContext.Provider value={{ license, licenseStatus, loading }}>
      {children}
    </LicenseContext.Provider>
  );
}

export function useLicenseContext(): LicenseContextValue {
  return useContext(LicenseContext);
}
