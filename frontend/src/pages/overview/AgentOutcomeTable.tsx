import type { AgentOutcome } from "@/api/dashboard";

interface AgentOutcomeTableProps {
  agents: AgentOutcome[];
}

export function AgentOutcomeTable({ agents }: AgentOutcomeTableProps) {
  if (agents.length === 0) {
    return (
      <div className="text-center text-ac-muted py-12">
        <p className="text-body-md">No governed activity yet — once agents start calling tools, what governance did shows up here.</p>
      </div>
    );
  }

  const maxCalls = Math.max(...agents.map((a) => a.calls), 1);

  return (
    <div className="border border-ac-hairline rounded-lg overflow-hidden">
      <div className="grid grid-cols-[28px_1.6fr_1fr_1fr_1fr] gap-2 p-4 bg-ac-canvas-soft border-b border-ac-hairline-strong">
        <div className="font-label-uc text-ac-muted text-11px"></div>
        <div className="font-label-uc text-ac-muted text-11px">Agent</div>
        <div className="font-label-uc text-ac-muted text-11px text-right">Calls</div>
        <div className="font-label-uc text-ac-muted text-11px text-right">Approval Needed</div>
        <div className="font-label-uc text-ac-muted text-11px text-right">Denied</div>
      </div>
      <div className="divide-y divide-ac-hairline-soft">
        {agents.map((agent, idx) => {
          const barWidth = Math.max((agent.calls / maxCalls) * 100, 2);
          return (
            <div
              key={agent.agent_name}
              className="grid grid-cols-[28px_1.6fr_1fr_1fr_1fr] gap-2 p-4 items-center hover:bg-ac-canvas-soft transition-colors"
            >
              <div className="font-identifier text-ac-muted-soft text-12px">{String(idx + 1).padStart(2, "0")}</div>
              <div>
                <div className="font-title-sm text-ac-body-strong text-14px mb-2">{agent.agent_name}</div>
                <div className="bg-ac-hairline-soft rounded-sm h-1.5 overflow-hidden">
                  <div
                    className="bg-ac-body h-full transition-all"
                    style={{ width: `${barWidth}%` }}
                  />
                </div>
              </div>
              <div className="font-code text-ac-body text-14px text-right font-variant-numeric-tabular-nums">
                {agent.calls.toLocaleString()}
              </div>
              <div className="font-code text-ac-body text-14px text-right font-variant-numeric-tabular-nums">
                {agent.held_for_approval.toLocaleString()}
              </div>
              <div className="font-code text-ac-body text-14px text-right font-variant-numeric-tabular-nums">
                {agent.denied.toLocaleString()}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
