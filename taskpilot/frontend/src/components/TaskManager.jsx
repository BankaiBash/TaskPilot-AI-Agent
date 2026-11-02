import React, { useState } from 'react';
import {
  CheckSquare,
  Square,
  Trash2,
  Plus,
  Calendar,
  ListChecks,
  CheckCircle2,
  Clock,
} from 'lucide-react';

export default function TaskManager({
  tasks,
  filter,
  onFilterChange,
  onCreateTask,
  onToggleTask,
  onRequestDeleteTask,
}) {
  const [name, setName] = useState('');
  const [deadline, setDeadline] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState('');

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) {
      setError('Please enter a task name.');
      return;
    }
    setError('');
    setIsCreating(true);
    try {
      await onCreateTask({
        name: cleanName,
        deadline: deadline.trim() || 'No deadline specified',
      });
      setName('');
      setDeadline('');
    } catch (err) {
      setError(err.message || 'Failed to add task.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex flex-col rounded-2xl bg-[#0c0f1d]/90 border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden">
      {/* Header & Filter Tabs */}
      <div className="px-4 sm:px-5 py-3.5 border-b border-white/10 bg-[#101426]/80 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/20 border border-sky-500/40 text-sky-300">
            <ListChecks className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-display text-sm sm:text-base font-semibold text-white">
              Persistent Task Manager
            </h2>
            <p className="text-[11px] text-slate-400">
              Synced with <code className="font-mono-code text-purple-300">data/tasks.json</code>
            </p>
          </div>
        </div>

        <div className="flex items-center rounded-xl bg-[#090b14] p-1 border border-white/10 text-xs">
          {['all', 'active', 'completed'].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => onFilterChange(tab)}
              className={`px-2.5 py-1 rounded-lg font-medium capitalize transition cursor-pointer ${
                filter === tab
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Quick Add Task Form */}
      <form
        onSubmit={handleAddSubmit}
        className="p-3.5 border-b border-white/8 bg-[#090b14]/60 space-y-2"
      >
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
          <div className="sm:col-span-6">
            <label htmlFor="new-task-name" className="sr-only">
              Task Name
            </label>
            <input
              id="new-task-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="New task title..."
              className="w-full rounded-xl bg-[#121629] border border-white/10 focus:border-purple-500/50 focus:outline-none px-3 py-2 text-xs text-white placeholder:text-slate-500"
            />
          </div>
          <div className="sm:col-span-4">
            <label htmlFor="new-task-deadline" className="sr-only">
              Deadline
            </label>
            <input
              id="new-task-deadline"
              type="text"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              placeholder="Deadline (e.g. Tomorrow 5 PM)"
              className="w-full rounded-xl bg-[#121629] border border-white/10 focus:border-purple-500/50 focus:outline-none px-3 py-2 text-xs text-white placeholder:text-slate-500"
            />
          </div>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={isCreating}
              className="w-full h-full inline-flex items-center justify-center gap-1 rounded-xl bg-purple-600/90 hover:bg-purple-500 px-3 py-2 text-xs font-semibold text-white transition cursor-pointer disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add</span>
            </button>
          </div>
        </div>
        {error && <p className="text-[11px] text-rose-400 px-1">{error}</p>}
      </form>

      {/* Task List */}
      <div className="divide-y divide-white/8 max-h-[295px] overflow-y-auto scroller">
        {tasks.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No tasks match filter <strong className="text-slate-200">"{filter}"</strong>. Ask the
            agent in chat or use the form above to add one!
          </div>
        ) : (
          tasks.map((task) => (
            <div
              key={task.id}
              className="px-4 py-3 flex items-center justify-between gap-3 hover:bg-white/[0.02] transition"
            >
              <div className="flex items-start gap-3 min-w-0">
                <button
                  type="button"
                  onClick={() => onToggleTask(task)}
                  title={task.completed ? 'Mark as active' : 'Mark as completed'}
                  className="mt-0.5 text-slate-400 hover:text-purple-400 transition cursor-pointer shrink-0"
                >
                  {task.completed ? (
                    <CheckSquare className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <Square className="h-4 w-4" />
                  )}
                </button>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono-code text-[10px] rounded bg-white/8 border border-white/10 px-1.5 py-0.5 text-purple-300">
                      {task.id}
                    </span>
                    <span
                      className={`text-xs sm:text-sm font-medium break-words ${
                        task.completed ? 'line-through text-slate-500' : 'text-slate-100'
                      }`}
                    >
                      {task.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[11px] text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Calendar className="h-3 w-3 text-sky-400" />
                      {task.deadline}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 ${
                        task.completed ? 'text-emerald-400' : 'text-amber-300'
                      }`}
                    >
                      {task.completed ? (
                        <>
                          <CheckCircle2 className="h-3 w-3" /> Completed
                        </>
                      ) : (
                        <>
                          <Clock className="h-3 w-3" /> Active
                        </>
                      )}
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => onRequestDeleteTask(task)}
                title={`Delete task ${task.id}`}
                className="inline-flex items-center justify-center h-8 w-8 rounded-xl bg-rose-500/10 hover:bg-rose-500/25 border border-rose-500/25 text-rose-400 transition shrink-0 cursor-pointer"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
