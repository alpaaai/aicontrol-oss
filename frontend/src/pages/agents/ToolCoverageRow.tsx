import { ShieldCheck, ShieldAlert } from "lucide-react";

interface Props {
  tool: string;
  governed: boolean;
  policyName: string | null;
}

export function ToolCoverageRow({ tool, governed, policyName }: Props) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-gray-50 last:border-0 text-[13px]">
      {governed ? (
        <ShieldCheck size={13} className="text-ac-allow shrink-0" />
      ) : (
        <ShieldAlert size={13} className="text-ac-review shrink-0" />
      )}
      <span className="font-mono text-[12px] text-ac-text-primary flex-1">
        {tool}
      </span>
      {governed ? (
        <span className="text-[11px] text-ac-allow">{policyName}</span>
      ) : (
        <span className="text-[11px] text-ac-review font-medium">
          Ungoverned
        </span>
      )}
    </div>
  );
}
