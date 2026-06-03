import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getOrgSettings } from "../api/orgSettings";

interface OrgSettingsValue {
  orgName: string;
  timezone: string;
  refresh: () => void;
}

const DEFAULT: OrgSettingsValue = { orgName: "", timezone: "UTC", refresh: () => {} };

const OrgSettingsContext = createContext<OrgSettingsValue>(DEFAULT);

export function OrgSettingsProvider({ children }: { children: React.ReactNode }) {
  const [orgName, setOrgName] = useState("");
  const [timezone, setTimezone] = useState("UTC");

  const refresh = useCallback(() => {
    getOrgSettings()
      .then(({ data }) => {
        setOrgName(data.org_name);
        setTimezone(data.timezone);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <OrgSettingsContext.Provider value={{ orgName, timezone, refresh }}>
      {children}
    </OrgSettingsContext.Provider>
  );
}

export function useOrgSettings(): OrgSettingsValue {
  return useContext(OrgSettingsContext);
}
