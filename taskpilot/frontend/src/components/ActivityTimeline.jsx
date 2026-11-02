import React, { useState } from 'react';
import {
  Activity,
  User,
  BrainCircuit,
  Wrench,
  Terminal,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';

const STEP_STYLE = {
  user_request: {
    icon: User,
    badge: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
    line: 'border-sky-500/40',
  },
  gemini_analysis: {
    icon: BrainCircuit,
    badge: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
    line: 'border-purple-500/40',
  },
  tool_selected: {
    icon: Wrench,
    badge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
    line: 'border-indigo-500/40',
  },
  python_execution: {
    icon: Terminal,
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    line: 'border-emerald-500/40',
  },
  final_response: {
    icon: Sparkles,
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    line: 'border-amber-500/40',
  },
  error: {
    icon: AlertTriangle,
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    line: 'border-rose-500/40',
  },
};

export default function ActivityTimeline({ activities }) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const currentActivity = activities?.[selectedIndex] || activities?.[0] || null;
  const timeline = currentActivity?.timeline || [];

  return (
    <div className="flex flex-col rounded-2xl bg-[#0c0f1d]/90 border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden">
      {/* Header */}
      <div className="px-4 sm:px-5 py-3.5 border-b border-white/10 bg-[#101426]/80 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-300">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-display text-sm sm:text-base font-semibold text-white">
              Agent Activity & Execution Timeline
            </h2>
            <p className="text-[11px] text-slate-400">
              Visual trace: User Request → Gemini Analysis → Tool Selection → Python Execution → Final Response
            </p>
          </div>
        </div>

        {activities && activities.length > 1 && (
          <select
            aria-label="Select execution trace"
            value={selectedIndex}
            onChange={(e) => setSelectedIndex(Number(e.target.value))}
            className="rounded-xl bg-[#090b14] border border-white/12 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
          >
            {activities.slice(0, 15).map((act, idx) => (
              <option key={act.id || idx} value={idx}>
                {idx === 0 ? 'Latest: ' : `#${idx + 1}: `}
                {(act.user_request || '').slice(0, 42)}
                {(act.user_request || '').length > 42 ? '...' : ''}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Horizontal Flow Summary Pipeline */}
      {timeline.length > 0 && (
        <div className="px-4 py-2.5 bg-[#090b14]/80 border-b border-white/8 flex items-center gap-1.5 overflow-x-auto scroller text-[11px] font-mono-code">
          {timeline.map((step, i) => (
            <React.Fragment key={step.step || i}>
              <span className="shrink-0 rounded-lg bg-white/5 border border-white/10 px-2 py-0.5 text-slate-200">
                {step.title}
              </span>
              {i < timeline.length - 1 && (
                <ArrowRight className="h-3 w-3 text-purple-400 shrink-0" />
              )}
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Detailed Step-by-Step Vertical Timeline */}
      <div className="p-4 sm:p-5 max-h-[310px] overflow-y-auto scroller space-y-3">
        {!currentActivity ? (
          <div className="text-center py-8 text-xs text-slate-400">
            No agent activity recorded yet. Send a message in chat to watch the execution pipeline live!
          </div>
        ) : (
          timeline.map((item, idx) => {
            const style = STEP_STYLE[item.type] || STEP_STYLE.gemini_analysis;
            const Icon = style.icon;
            return (
              <div key={idx} className="relative flex items-start gap-3">
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${style.badge}`}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 min-w-0 rounded-xl bg-[#111526] border border-white/8 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white">
                      Step {item.step}: {item.title}
                    </span>
                    <div className="flex items-center gap-2 text-[10px] font-mono-code text-slate-400">
                      {item.status === 'completed' && (
                        <span className="inline-flex items-center gap-1 text-emerald-400">
                          <CheckCircle2 className="h-3 w-3" /> OK
                        </span>
                      )}
                      {item.status === 'awaiting_confirmation' && (
                        <span className="inline-flex items-center gap-1 text-amber-300">
                          <AlertTriangle className="h-3 w-3" /> Awaiting Approval
                        </span>
                      )}
                      <span>{item.timestamp}</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-300 mt-1 break-words">{item.detail}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
