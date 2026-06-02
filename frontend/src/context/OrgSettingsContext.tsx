import React, { createContext, useContext, useEffect, useState } from "react";
import { getOrgSettings } from "../api/orgSettings";

interface OrgSettingsValue {
  orgName: string;
  timezone: string;
}

const DEFAULT: OrgSettingsValue = { orgName: "", timezone: "UTC" };

const OrgSettingsContext = createContext<OrgSettingsValue>(DEFAULT);

export function OrgSettingsProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState<OrgSettingsValue>(DEFAULT);

  useEffect(() => {
    getOrgSettings()
      .then(({ data }) => setValue({ orgName: data.org_name, timezone: data.timezone }))
      .catch(() => {});
  }, []);

  return (
    <OrgSettingsContext.Provider value={value}>
      {children}
    </OrgSettingsContext.Provider>
  );
}

export function useOrgSettings(): OrgSettingsValue {
  return useContext(OrgSettingsContext);
}
