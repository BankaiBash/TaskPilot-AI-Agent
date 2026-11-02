import React from 'react';
import {
  GraduationCap,
  MessageSquare,
  BrainCircuit,
  Wrench,
  Code2,
  Terminal,
  Database,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

export default function LearningModePanel({ learningData, modelName }) {
  if (!learningData) {
    return (
      <section className="rounded-2xl bg-gradient-to-r from-purple-950/35 via-[#101322] to-sky-950/30 border border-purple-500/35 p-4 sm:p-5 shadow-[0_0_30px_rgba(139,92,246,0.12)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/20 border border-purple-400/40 text-purple-300">
              <GraduationCap className="h-4 w-4" />
            </div>
            <div>
              <h2 className="font-display text-sm sm:text-base font-semibold text-white">
                Learning Mode Active — How Your AI Agent Works Behind the Scenes
              </h2>
              <p className="text-xs text-slate-300">
                Unlike a standard chatbot that only predicts text, TaskPilot uses an{' '}
                <span className="text-sky-300 font-medium">Agent Execution Loop</span> with tool declarations.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono-code rounded-lg bg-sky-500/15 border border-sky-400/30 px-2.5 py-1 text-sky-300 self-start sm:self-auto">
            Brain: {modelName || 'gemini-2.5-flash'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
          <div className="rounded-xl bg-[#0c0e18]/90 border border-white/10 p-3">
            <div className="font-mono-code text-purple-300 font-semibold mb-1">
              1. Intent & Tool Selection
            </div>
            <p className="text-slate-400 leading-relaxed">
              Gemini reads your natural-language prompt alongside JSON schemas of all 5 Python tools and decides whether a function call is required.
            </p>
          </div>
          <div className="rounded-xl bg-[#0c0e18]/90 border border-white/10 p-3">
            <div className="font-mono-code text-sky-300 font-semibold mb-1">
              2. Structured Arguments
            </div>
            <p className="text-slate-400 leading-relaxed">
              Instead of replying to you immediately, Gemini outputs a structured{' '}
              <code className="text-slate-200">function_call</code> object containing validated arguments.
            </p>
          </div>
          <div className="rounded-xl bg-[#0c0e18]/90 border border-white/10 p-3">
            <div className="font-mono-code text-emerald-300 font-semibold mb-1">
              3. Python Execution
            </div>
            <p className="text-slate-400 leading-relaxed">
              FastAPI intercepts the tool request, runs the real Python code (AST math, clock, or JSON storage), and captures the result.
            </p>
          </div>
          <div className="rounded-xl bg-[#0c0e18]/90 border border-white/10 p-3">
            <div className="font-mono-code text-amber-300 font-semibold mb-1">
              4. Loop & Final Synthesis
            </div>
            <p className="text-slate-400 leading-relaxed">
              Python sends <code className="text-slate-200">Part.from_function_response</code> back to Gemini, which either chains another tool or writes the final answer!
            </p>
          </div>
        </div>
      </section>
    );
  }

  const steps = learningData.steps || [];

  return (
    <section className="rounded-2xl bg-gradient-to-br from-purple-950/35 via-[#0e1120] to-sky-950/30 border border-purple-500/40 p-4 sm:p-5 shadow-[0_0_30px_rgba(139,92,246,0.15)]">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4 pb-3 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/20 border border-purple-400/40 text-purple-300">
            <GraduationCap className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-display text-sm sm:text-base font-bold text-white">
              Behind-the-Scenes Agent Anatomy (Learning Mode)
            </h3>
            <p className="text-xs text-slate-400">
              Observable execution summary of how TaskPilot processed your latest request
            </p>
          </div>
        </div>
        <span className="text-xs font-mono-code rounded-full bg-purple-500/20 border border-purple-400/30 px-3 py-0.5 text-purple-200">
          {steps.length} Tool Call{steps.length === 1 ? '' : 's'} Executed
        </span>
      </div>

      {/* Top 3 Macro Insights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div className="rounded-xl bg-[#090b14]/90 border border-white/8 p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-sky-300 mb-1.5">
            <MessageSquare className="h-3.5 w-3.5" />
            1. What You Requested
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">{learningData.user_requested}</p>
        </div>

        <div className="rounded-xl bg-[#090b14]/90 border border-white/8 p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-purple-300 mb-1.5">
            <BrainCircuit className="h-3.5 w-3.5" />
            2. What Gemini Understood
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">{learningData.gemini_understood}</p>
        </div>

        <div className="rounded-xl bg-[#090b14]/90 border border-white/8 p-3.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300 mb-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            3. How Final Answer Was Built
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            {learningData.how_final_answer_generated}
          </p>
        </div>
      </div>

      {/* Per-Tool Detailed Breakdown */}
      {steps.length > 0 && (
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Step-by-Step Tool Execution Breakdown
          </div>
          {steps.map((step) => (
            <div
              key={step.step_number}
              className="rounded-xl bg-[#090b14] border border-purple-500/25 p-3.5 grid grid-cols-1 lg:grid-cols-4 gap-3 text-xs"
            >
              <div>
                <div className="flex items-center gap-1.5 font-mono-code font-semibold text-purple-300 mb-1">
                  <Wrench className="h-3.5 w-3.5 text-sky-400" />
                  Step #{step.step_number}: {step.tool_name}()
                </div>
                <p className="text-slate-400 leading-relaxed">{step.why_selected}</p>
              </div>

              <div>
                <div className="flex items-center gap-1.5 font-semibold text-sky-300 mb-1">
                  <Code2 className="h-3.5 w-3.5" />
                  Arguments Passed by Gemini
                </div>
                <pre className="font-mono-code text-[11px] bg-[#111526] text-sky-200 p-2 rounded-lg border border-white/5 overflow-x-auto">
                  {JSON.stringify(step.arguments_passed, null, 2)}
                </pre>
              </div>

              <div>
                <div className="flex items-center gap-1.5 font-semibold text-amber-300 mb-1">
                  <Terminal className="h-3.5 w-3.5" />
                  What Python Executed ({step.duration_ms}ms)
                </div>
                <p className="text-slate-300 leading-relaxed">{step.python_executed}</p>
              </div>

              <div>
                <div className="flex items-center gap-1.5 font-semibold text-emerald-300 mb-1">
                  <Database className="h-3.5 w-3.5" />
                  Observable Result Returned
                </div>
                <pre className="font-mono-code text-[11px] bg-[#111526] text-emerald-200 p-2 rounded-lg border border-white/5 overflow-x-auto max-h-28 scroller">
                  {JSON.stringify(step.result_returned, null, 2)}
                </pre>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
