import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  Wrench,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Trash2,
  XCircle,
  Calculator,
  CalendarClock,
  ListTodo,
  PlusCircle,
} from 'lucide-react';

const SAMPLE_PROMPTS = [
  {
    label: 'Multi-Tool Chain',
    icon: Sparkles,
    prompt:
      "Check today's date, calculate (240 * 15) + 400, and add a task to submit that budget total tomorrow at 5:00 PM.",
  },
  {
    label: 'Safe Calculator',
    icon: Calculator,
    prompt: 'Calculate (1850 * 1.18) + sqrt(256) and explain the breakdown.',
  },
  {
    label: 'System Clock',
    icon: CalendarClock,
    prompt: 'What is the exact system date, time, and weekday right now?',
  },
  {
    label: 'View Active Tasks',
    icon: ListTodo,
    prompt: 'Show me all my currently active tasks.',
  },
  {
    label: 'Add Task',
    icon: PlusCircle,
    prompt: 'Add a task called "Review Gemini Function Calling trace" with deadline 2026-11-06 16:00.',
  },
];

function StreamingText({ text, isLatest }) {
  const [displayed, setDisplayed] = useState(isLatest ? '' : text);

  useEffect(() => {
    if (!isLatest || !text) {
      setDisplayed(text);
      return;
    }
    let idx = 0;
    const step = Math.max(2, Math.ceil(text.length / 45));
    const timer = setInterval(() => {
      idx += step;
      if (idx >= text.length) {
        setDisplayed(text);
        clearInterval(timer);
      } else {
        setDisplayed(text.slice(0, idx));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [text, isLatest]);

  return <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{displayed}</div>;
}

function ToolExecutionCard({ toolCall }) {
  const [expanded, setExpanded] = useState(false);
  const isSuccess = toolCall.status === 'completed';
  const isConfirmation = toolCall.status === 'awaiting_confirmation';

  return (
    <div
      className={`rounded-xl border p-3 text-xs transition ${
        isConfirmation
          ? 'bg-amber-950/25 border-amber-500/40'
          : isSuccess
          ? 'bg-[#101426] border-purple-500/30'
          : 'bg-rose-950/25 border-rose-500/40'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center h-6 w-6 rounded-lg bg-purple-500/20 border border-purple-400/30 text-purple-300">
            <Wrench className="h-3.5 w-3.5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono-code font-semibold text-white">
                {toolCall.tool_name}()
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  isConfirmation
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : isSuccess
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                }`}
              >
                {isConfirmation ? (
                  <>
                    <AlertTriangle className="h-2.5 w-2.5" />
                    Awaiting Approval
                  </>
                ) : isSuccess ? (
                  <>
                    <CheckCircle2 className="h-2.5 w-2.5" />
                    Executed ({toolCall.duration_ms}ms)
                  </>
                ) : (
                  <>
                    <XCircle className="h-2.5 w-2.5" />
                    Failed
                  </>
                )}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Args:{' '}
              <code className="font-mono-code text-sky-300">
                {JSON.stringify(toolCall.arguments)}
              </code>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="inline-flex items-center gap-1 rounded-lg bg-white/5 hover:bg-white/10 px-2 py-1 text-[11px] text-slate-300 transition cursor-pointer"
        >
          <span>{expanded ? 'Hide Output' : 'Inspect Output'}</span>
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-2.5 pt-2.5 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">
              Function Arguments (Gemini → Python)
            </div>
            <pre className="font-mono-code text-[11px] bg-[#080a12] text-sky-300 p-2 rounded-lg border border-white/5 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">
              Observable Tool Output (Python → Gemini)
            </div>
            <pre className="font-mono-code text-[11px] bg-[#080a12] text-emerald-300 p-2 rounded-lg border border-white/5 overflow-x-auto max-h-36 scroller">
              {JSON.stringify(toolCall.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChatPanel({
  messages,
  isSending,
  thinkingStage,
  learningMode,
  onSendMessage,
  onConfirmAgentDeletion,
  onCancelAgentDeletion,
}) {
  const [input, setInput] = useState('');
  const formRef = useRef(null);
  const messagesEndRef = useRef(null);
  const lastCompositionEndAtRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending) return;
    setInput('');
    onSendMessage(trimmed);
  };

  // IME-safe Enter-to-submit implementation (modern-web-guidance: ime-safe-enter-submit)
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();

      // Block submission if composing natively or if keyCode is 229 (Safari fallback)
      if (event.isComposing || event.keyCode === 229) {
        return;
      }

      // Block submission if within 50ms window of composition ending
      if (
        lastCompositionEndAtRef.current !== null &&
        Math.abs(event.timeStamp - lastCompositionEndAtRef.current) < 50
      ) {
        return;
      }

      formRef.current?.requestSubmit();
    }
  };

  const handleCompositionEnd = (event) => {
    lastCompositionEndAtRef.current = event.timeStamp;
  };

  return (
    <div className="flex flex-col h-[680px] rounded-2xl bg-[#0c0f1d]/90 border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden">
      {/* Panel Header */}
      <div className="px-4 sm:px-5 py-3.5 border-b border-white/10 bg-[#101426]/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-300">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-display text-sm sm:text-base font-semibold text-white">
              Agent Command Console
            </h2>
            <p className="text-[11px] text-slate-400">
              Natural-language reasoning + real-time Python tool execution
            </p>
          </div>
        </div>
        <span className="text-[11px] font-mono-code rounded-lg bg-white/5 border border-white/10 px-2.5 py-1 text-slate-300">
          5 Tools Armed
        </span>
      </div>

      {/* Quick Prompt Chips */}
      <div className="px-4 py-2.5 border-b border-white/8 bg-[#090b14]/70 flex items-center gap-2 overflow-x-auto scroller">
        <span className="text-[11px] font-medium text-slate-400 shrink-0">Try:</span>
        {SAMPLE_PROMPTS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              type="button"
              disabled={isSending}
              onClick={() => onSendMessage(item.prompt)}
              className="inline-flex items-center gap-1.5 shrink-0 rounded-full bg-[#14182b] hover:bg-purple-500/20 border border-white/10 hover:border-purple-500/40 px-3 py-1 text-xs text-slate-200 transition disabled:opacity-50 cursor-pointer"
            >
              <Icon className="h-3 w-3 text-sky-400" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Conversation Feed */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5 scroller">
        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          const isLatestAgent = !isUser && index === messages.length - 1;

          return (
            <div
              key={msg.id || index}
              className={`flex items-start gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-600/40 to-sky-500/30 border border-purple-400/40 text-purple-200 mt-0.5">
                  <Bot className="h-4 w-4" />
                </div>
              )}

              <div
                className={`max-w-[90%] sm:max-w-[84%] space-y-2.5 ${
                  isUser
                    ? 'rounded-2xl rounded-tr-sm bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3 text-white shadow-[0_8px_25px_rgba(124,58,237,0.3)]'
                    : 'w-full'
                }`}
              >
                {isUser ? (
                  <div className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</div>
                ) : (
                  <div className="space-y-3">
                    {/* Reasoning Summary Header (distinguished from tool outputs) */}
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="rounded-xl bg-[#121629]/90 border border-sky-500/25 px-3.5 py-2.5">
                        <div className="flex items-center justify-between gap-2 text-[11px] font-mono-code text-sky-300 mb-2">
                          <span className="flex items-center gap-1.5 font-semibold">
                            <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                            AGENT TOOL EXECUTION TRACE ({msg.toolCalls.length} step
                            {msg.toolCalls.length === 1 ? '' : 's'})
                          </span>
                          {msg.durationMs && <span>{msg.durationMs}ms total</span>}
                        </div>
                        <div className="space-y-2">
                          {msg.toolCalls.map((tc, tcIdx) => (
                            <ToolExecutionCard key={tcIdx} toolCall={tc} />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Human-in-the-loop Confirmation Gate inside Chat */}
                    {msg.pendingConfirmations && msg.pendingConfirmations.length > 0 && (
                      <div className="rounded-xl bg-rose-950/35 border border-rose-500/45 p-4 space-y-3">
                        {msg.pendingConfirmations.map((pendingTask) => (
                          <div key={pendingTask.id} className="space-y-2.5">
                            <div className="flex items-center gap-2 text-xs font-semibold text-rose-300">
                              <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
                              <span>
                                Human Confirmation Required to Delete Task{' '}
                                <code className="font-mono-code text-white">{pendingTask.id}</code>
                              </span>
                            </div>
                            <p className="text-xs text-slate-300">
                              TaskPilot paused <code className="font-mono-code">delete_task</code>{' '}
                              for <strong>"{pendingTask.name}"</strong> (Deadline:{' '}
                              {pendingTask.deadline}). Approve permanent removal?
                            </p>
                            <div className="flex items-center gap-2.5 pt-1">
                              <button
                                type="button"
                                disabled={isSending}
                                onClick={() => onConfirmAgentDeletion(msg.id, pendingTask)}
                                className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-[0_0_15px_rgba(225,29,72,0.4)] transition cursor-pointer disabled:opacity-50"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                                Approve & Delete {pendingTask.id}
                              </button>
                              <button
                                type="button"
                                disabled={isSending}
                                onClick={() => onCancelAgentDeletion(msg.id, pendingTask)}
                                className="inline-flex items-center gap-1.5 rounded-xl bg-white/10 hover:bg-white/15 px-3 py-1.5 text-xs font-medium text-slate-200 transition cursor-pointer disabled:opacity-50"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Final Natural Language Agent Response Bubble */}
                    <div className="rounded-2xl rounded-tl-sm bg-[#14182b] border border-white/10 px-4 py-3.5 shadow-inner">
                      <div className="flex items-center justify-between gap-2 text-[10px] font-mono-code uppercase tracking-wider text-purple-300/90 mb-1.5">
                        <span>Final Natural-Language Response</span>
                        {msg.model && <span>{msg.model}</span>}
                      </div>
                      <StreamingText text={msg.content} isLatest={isLatestAgent} />
                    </div>

                    {/* Inline Learning Mode Summary Badge when Learning Mode is ON */}
                    {learningMode && msg.learningMode && (
                      <div className="rounded-xl bg-purple-950/30 border border-purple-500/35 p-3 text-xs space-y-1.5">
                        <div className="font-semibold text-purple-300 flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5 text-sky-400" />
                          Learning Mode Note:
                        </div>
                        <p className="text-slate-300 leading-relaxed">
                          {msg.learningMode.gemini_understood}
                        </p>
                        <p className="text-slate-400 leading-relaxed">
                          {msg.learningMode.how_final_answer_generated}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {isUser && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-purple-600/30 border border-purple-400/40 text-purple-200 mt-0.5">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          );
        })}

        {/* Animated Thinking & Tool Loop Indicator */}
        {isSending && (
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-purple-600/30 border border-purple-400/50 text-purple-300 animate-pulse-glow">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-2xl rounded-tl-sm bg-[#14182b] border border-purple-500/35 px-4 py-3 text-xs text-slate-200 space-y-2 max-w-md">
              <div className="flex items-center gap-2.5">
                <span className="flex gap-1">
                  <span className="h-2 w-2 rounded-full bg-purple-400 animate-bounce [animation-delay:-0.3s]" />
                  <span className="h-2 w-2 rounded-full bg-sky-400 animate-bounce [animation-delay:-0.15s]" />
                  <span className="h-2 w-2 rounded-full bg-indigo-400 animate-bounce" />
                </span>
                <span className="font-medium text-purple-200">{thinkingStage}</span>
              </div>
              <div className="text-[11px] font-mono-code text-slate-400">
                User Prompt → Gemini Intent Analysis → Tool Selection → Python Execution
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Form */}
      <form
        ref={formRef}
        onSubmit={handleSubmit}
        className="p-3.5 sm:p-4 border-t border-white/10 bg-[#090b14]/90"
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask TaskPilot to calculate, check time, or manage tasks
        </label>
        <div className="flex items-end gap-2.5">
          <textarea
            id="chat-input"
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onCompositionEnd={handleCompositionEnd}
            disabled={isSending}
            placeholder="Ask TaskPilot anything... e.g. 'Check the current date, compute 18% of 3500, and add a task to pay it tomorrow'"
            className="flex-1 resize-none rounded-xl bg-[#121629] border border-white/12 focus:border-purple-500/60 focus:outline-none px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 scroller"
          />
          <button
            type="submit"
            disabled={isSending || !input.trim()}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-sky-500 hover:from-purple-500 hover:to-sky-400 disabled:opacity-40 px-4 py-3 text-sm font-semibold text-white shadow-[0_0_25px_rgba(139,92,246,0.35)] transition cursor-pointer shrink-0"
          >
            <Send className="h-4 w-4" />
            <span className="hidden sm:inline">Execute</span>
          </button>
        </div>
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-500 px-1">
          <span>Press Enter to send · Shift+Enter for new line</span>
          <span className="font-mono-code">Tools: calculator · add_task · view_tasks · delete_task · get_current_datetime</span>
        </div>
      </form>
    </div>
  );
}
