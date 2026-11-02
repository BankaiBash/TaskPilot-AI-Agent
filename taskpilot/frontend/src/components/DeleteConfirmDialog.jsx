import React, { useEffect, useRef } from 'react';
import { AlertTriangle, Trash2, X } from 'lucide-react';

export default function DeleteConfirmDialog({ task, onConfirm, onCancel }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (task && !dialog.open) {
      dialog.showModal();
    } else if (!task && dialog.open) {
      dialog.close();
    }
  }, [task]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleClose = () => {
      const choice = dialog.returnValue;
      // Reset returnValue immediately so stale values never leak on subsequent Esc closes
      dialog.returnValue = '';
      if (choice === 'delete' && task) {
        onConfirm(task);
      } else {
        onCancel();
      }
    };

    dialog.addEventListener('close', handleClose);
    return () => dialog.removeEventListener('close', handleClose);
  }, [task, onConfirm, onCancel]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="delete-confirm-title"
      className="m-auto w-full max-w-md rounded-2xl bg-[#0e111d] border border-rose-500/40 p-6 text-slate-100 shadow-[0_25px_70px_rgba(0,0,0,0.85)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <h2 id="delete-confirm-title" className="font-display text-lg font-semibold text-white">
              Confirm Task Deletion
            </h2>
            <p className="text-xs text-rose-300/80">
              Human-in-the-Loop Safety Gate · Destructive Operation
            </p>
          </div>
        </div>
      </div>

      {task && (
        <div className="mt-4 rounded-xl bg-[#151828] border border-white/10 p-3.5 text-sm">
          <div className="flex items-center justify-between text-xs font-mono-code text-slate-400 mb-1">
            <span>TASK ID: {task.id}</span>
            <span>{task.completed ? 'Completed' : 'Active'}</span>
          </div>
          <div className="font-medium text-white break-words">{task.name}</div>
          <div className="text-xs text-slate-400 mt-1">Deadline: {task.deadline}</div>
        </div>
      )}

      <p className="mt-4 text-xs sm:text-sm text-slate-300 leading-relaxed">
        Are you sure you want to permanently remove this task from persistent storage (
        <code className="font-mono-code text-purple-300">data/tasks.json</code>)? This action cannot
        be undone.
      </p>

      <form method="dialog" className="mt-6 flex items-center justify-end gap-3">
        <button
          type="submit"
          value="cancel"
          autoFocus
          className="inline-flex items-center gap-1.5 rounded-xl bg-[#181c2e] border border-white/10 px-4 py-2 text-xs sm:text-sm font-medium text-slate-200 hover:bg-[#222740] transition cursor-pointer"
        >
          <X className="h-4 w-4" />
          Cancel
        </button>
        <button
          type="submit"
          value="delete"
          className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 px-4 py-2 text-xs sm:text-sm font-semibold text-white shadow-[0_0_20px_rgba(225,29,72,0.4)] transition cursor-pointer"
        >
          <Trash2 className="h-4 w-4" />
          Confirm Delete
        </button>
      </form>
    </dialog>
  );
}
