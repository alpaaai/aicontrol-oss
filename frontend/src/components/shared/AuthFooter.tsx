import { useEffect, useState } from "react";
import { getLicenseInfo } from "@/api/license";

const PLAN_LABELS: Record<string, string> = {
  community: "Community tier",
  business: "Business tier",
  enterprise: "Enterprise tier",
  trial: "Enterprise tier (trial)",
};

export function AuthFooter() {
  const [tierLabel, setTierLabel] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLicenseInfo()
      .then((info) => {
        if (!cancelled) setTierLabel(PLAN_LABELS[info.plan] ?? null);
      })
      .catch(() => {
        if (!cancelled) setTierLabel(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <p className="mt-10 text-[11px] text-ac-muted/60 text-center">
      Secured by AIControl{tierLabel ? ` · ${tierLabel}` : ""}
    </p>
  );
}
