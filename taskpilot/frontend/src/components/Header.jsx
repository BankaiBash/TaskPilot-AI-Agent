import React, { useEffect } from 'react';
import {
  Bot,
  Sparkles,
  CheckCircle2,
  Clock,
  Activity,
  GraduationCap,
  Cpu,
  ShieldAlert,
  RefreshCw,
} from 'lucide-react';

export default function Header({
  agentStatus,
  metrics,
  learningMode,
  onToggleLearningMode,
  onRefresh,
  isRefreshing,
}) {
  // Conditionally load input-switch-polyfill only when native HTML switch is unsupported
  useEffect(() => {
    if (typeof window !== 'undefined' && !('switch' in HTMLInputElement.prototype)) {
      const pkg = 'input-switch-polyfill';
      import(/* @vite-ignore */ pkg).catch(() => {});
    }
  }, []);

  const isConfigured = agentStatus?.api_key_configured;
  const modelName = agentStatus?.model || 'gemini-2.5-flash';

  return (
    <header className="border-b border-white/10 bg-[#0b0d16]/85 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Brand & Welcome Message */}
        <div className="flex items-start sm:items-center gap-4">
          <div className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-600/30 via-indigo-600/20 to-sky-500/30 border border-purple-500/40 shadow-[0_0_25px_rgba(139,92,246,0.25)]">
            <Bot className="h-6 w-6 text-purple-300" />
            <span
              className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-[#0b0d16] ${
                isConfigured ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="font-display text-xl sm:text-2xl font-bold tracking-tight text-white">
                TaskPilot
              </h1>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-500/15 border border-purple-500/30 px-2.5 py-0.5 text-xs font-medium text-purple-300">
                <Sparkles className="h-3 w-3 text-sky-400" />
                Agentic AI Workspace
              </span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-mono-code border ${
                  isConfigured
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                }`}
              >
                {isConfigured ? (
                  <>
                    <Cpu className="h-3 w-3" />
                    ONLINE · {modelName}
                  </>
                ) : (
                  <>
                    <ShieldAlert className="h-3 w-3" />
                    API KEY NEEDED ({modelName})
                  </>
                )}
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Welcome back, Commander. Observe how Gemini reasons, selects tools, executes Python functions, and synthesizes answers.
            </p>
          </div>
        </div>

        {/* Right Controls: Metrics & Learning Mode Switch */}
        <div className="flex flex-wrap items-center justify-between lg:justify-end gap-3">
          {/* Metric Pills */}
          <div className="grid grid-cols-3 gap-2 sm:flex sm:items-center">
            <div className="flex items-center gap-2 rounded-xl bg-[#111422] border border-white/8 px-3 py-2">
              <Clock className="h-4 w-4 text-sky-400 shrink-0" />
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Active</div>
                <div className="text-sm font-bold font-mono-code text-white">
                  {metrics?.active_tasks ?? 0}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-xl bg-[#111422] border border-white/8 px-3 py-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Completed</div>
                <div className="text-sm font-bold font-mono-code text-white">
                  {metrics?.completed_tasks ?? 0}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-xl bg-[#111422] border border-white/8 px-3 py-2">
              <Activity className="h-4 w-4 text-purple-400 shrink-0" />
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-400">Traces</div>
                <div className="text-sm font-bold font-mono-code text-white">
                  {metrics?.total_activities ?? 0}
                </div>
              </div>
            </div>
          </div>

          {/* Learning Mode Native HTML Switch */}
          <div
            className={`flex items-center gap-3 rounded-xl px-3.5 py-2 border transition-all duration-200 ${
              learningMode
                ? 'bg-gradient-to-r from-purple-900/40 to-sky-900/30 border-purple-400/50 shadow-[0_0_20px_rgba(139,92,246,0.2)]'
                : 'bg-[#111422] border-white/10'
            }`}
          >
            <GraduationCap
              className={`h-4 w-4 ${learningMode ? 'text-sky-300' : 'text-slate-400'}`}
            />
            <label
              htmlFor="learning-mode-switch"
              className="flex items-center gap-2.5 cursor-pointer select-none text-xs sm:text-sm font-semibold tracking-wide"
            >
              <span className={learningMode ? 'text-white' : 'text-slate-300'}>
                LEARNING MODE
              </span>
              <input
                id="learning-mode-switch"
                type="checkbox"
                {...{ switch: '' }}
                checked={learningMode}
                onChange={(e) => onToggleLearningMode(e.target.checked)}
              />
            </label>
          </div>

          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Sync dashboard state"
            className="inline-flex items-center justify-center h-9 w-9 rounded-xl bg-[#111422] border border-white/10 text-slate-300 hover:text-white hover:border-purple-500/40 transition disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
}
