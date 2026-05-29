import { Lock, Brain, Lightbulb, AlertTriangle } from 'lucide-react'

interface IntelligenceCardProps {
  icon: React.ReactNode
  title: string
  description: string
  badge?: string
  children?: React.ReactNode
}

function IntelligenceCard({ icon, title, description, badge, children }: IntelligenceCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-[10px] p-5 relative overflow-hidden">
      {/* Lock overlay — P2 removes this when wiring real component */}
      <div className="absolute inset-0 bg-white/60 backdrop-blur-[1px] flex items-center justify-center z-10">
        <div className="bg-purple-50 border border-purple-200/30 rounded-lg px-4 py-3 text-center">
          <Lock className="w-4 h-4 text-purple-600 mx-auto mb-1.5" />
          <p className="text-xs font-medium text-purple-600">Requires Enterprise License</p>
        </div>
      </div>

      {/* Card shape — blurred preview */}
      <div className="blur-sm pointer-events-none select-none opacity-40">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-purple-600">{icon}</span>
          <h3 className="text-[14px] font-semibold text-ac-text-primary">{title}</h3>
          {badge && (
            <span className="ml-auto text-[11px] bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full font-medium">
              {badge}
            </span>
          )}
        </div>
        <p className="text-[13px] text-gray-500 mb-3">{description}</p>
        {children ?? (
          <div className="space-y-2">
            <div className="h-3 bg-gray-100 rounded w-3/4" />
            <div className="h-3 bg-gray-100 rounded w-1/2" />
          </div>
        )}
      </div>
    </div>
  )
}

export function IntelligencePage() {
  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-[18px] font-semibold text-ac-text-primary">Intelligence</h2>
        <p className="text-sm text-gray-400 mt-0.5">AI-native governance features — Enterprise</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* P2-1: Session Threat Summarizer */}
        <IntelligenceCard
          icon={<Brain size={15} />}
          title="Session Threat Summaries"
          description="AI-generated one-sentence threat assessment per session. Severity badge. Pattern detection across tool calls."
          badge="P2-1"
        >
          <div className="space-y-2">
            {[
              { session: 'a3f9b2c1…', severity: 'High', summary: 'Agent attempted to access restricted patient records outside session scope.' },
              { session: 'b8c2d4e6…', severity: 'Low',  summary: 'Normal documentation workflow with expected tool call sequence.' },
            ].map(item => (
              <div key={item.session} className="flex items-start gap-2 py-1.5 border-b border-gray-50 text-[12px]">
                <span className={`shrink-0 font-medium ${item.severity === 'High' ? 'text-red-500' : 'text-green-600'}`}>
                  {item.severity}
                </span>
                <span className="text-gray-600">{item.summary}</span>
              </div>
            ))}
          </div>
        </IntelligenceCard>

        {/* P2-2: Policy Suggestion Agent */}
        <IntelligenceCard
          icon={<Lightbulb size={15} />}
          title="Policy Suggestions"
          description="AI-generated policy recommendations based on observed agent behavior and ungoverned tool usage patterns."
          badge="P2-2"
        >
          <div className="space-y-2">
            {[
              'Add rate limit policy for deploy_infrastructure — called 47 times in 1 hour',
              'Create data access policy for read_patient_record — currently ungoverned on 2 agents',
            ].map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-[12px] text-gray-600 py-1 border-b border-gray-50">
                <Lightbulb size={11} className="text-amber-500 mt-0.5 shrink-0" />
                {s}
              </div>
            ))}
          </div>
        </IntelligenceCard>
      </div>

      {/* Drift Warnings — also surfaced on Policies page */}
      <IntelligenceCard
        icon={<AlertTriangle size={15} />}
        title="Drift Warning Feed"
        description="Real-time policy drift detection. Agents, tools, and policies that have drifted out of compliance."
        badge="P1-5"
      >
        <div className="space-y-1.5">
          {[
            "Tool 'deploy_infra' has no policy on lending-agent",
            "Policy 'pii_access' is inactive but agent is calling PII tools",
          ].map((msg, i) => (
            <div key={i} className="flex items-start gap-2 text-[12px] text-amber-600 py-1">
              <AlertTriangle size={11} className="mt-0.5 shrink-0" />
              {msg}
            </div>
          ))}
        </div>
      </IntelligenceCard>
    </div>
  )
}
