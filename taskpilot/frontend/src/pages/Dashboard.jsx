import React, { useState, useEffect, useCallback } from 'react';
import Header from '../components/Header';
import ChatPanel from '../components/ChatPanel';
import TaskManager from '../components/TaskManager';
import ActivityTimeline from '../components/ActivityTimeline';
import LearningModePanel from '../components/LearningModePanel';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import {
  fetchActivity,
  fetchTasks,
  createTask,
  updateTask,
  deleteTask,
  sendChatMessage,
} from '../services/api';

const INITIAL_MESSAGES = [
  {
    id: 'msg-welcome',
    role: 'agent',
    model: 'TaskPilot Core',
    content:
      'Welcome to **TaskPilot**! I am an action-oriented AI Agent powered by Google Gemini Function Calling.\n\n' +
      'I have 5 real backend tools connected to Python:\n' +
      '• `calculator` — Safe AST-based math evaluation\n' +
      '• `add_task` — Save new tasks with deadlines to persistent JSON storage\n' +
      '• `view_tasks` — Filter and inspect saved tasks\n' +
      '• `delete_task` — Remove a task by ID (with human-in-the-loop confirmation)\n' +
      '• `get_current_datetime` — Read the real system date, time, and timezone\n\n' +
      'Toggle **LEARNING MODE** in the top bar anytime to inspect how Gemini analyzes your prompt, selects tools, passes arguments, and interprets Python outputs!',
    toolCalls: [],
    pendingConfirmations: [],
  },
];

export default function Dashboard() {
  const [agentStatus, setAgentStatus] = useState(null);
  const [metrics, setMetrics] = useState({
    active_tasks: 0,
    completed_tasks: 0,
    total_tasks: 0,
    total_activities: 0,
  });
  const [tasks, setTasks] = useState([]);
  const [taskFilter, setTaskFilter] = useState('all');
  const [activities, setActivities] = useState([]);
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [learningMode, setLearningMode] = useState(true);
  const [latestLearningData, setLatestLearningData] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [thinkingStage, setThinkingStage] = useState('Gemini is analyzing your request...');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState(null);
  const [bannerError, setBannerError] = useState('');

  const syncDashboard = useCallback(
    async (currentFilter = taskFilter) => {
      setIsRefreshing(true);
      try {
        const [actData, taskData] = await Promise.all([
          fetchActivity(25),
          fetchTasks(currentFilter),
        ]);
        if (actData) {
          setAgentStatus(actData.agent);
          setMetrics(actData.metrics || {});
          setActivities(actData.activities || []);
        }
        if (taskData) {
          setTasks(taskData.tasks || []);
        }
        setBannerError('');
      } catch (err) {
        setBannerError(
          `Backend connection notice: ${err.message}. Make sure FastAPI is running on http://127.0.0.1:8000.`
        );
      } finally {
        setIsRefreshing(false);
      }
    },
    [taskFilter]
  );

  useEffect(() => {
    syncDashboard(taskFilter);
  }, [syncDashboard, taskFilter]);

  const handleFilterChange = async (newFilter) => {
    setTaskFilter(newFilter);
    try {
      const taskData = await fetchTasks(newFilter);
      setTasks(taskData.tasks || []);
    } catch (err) {
      setBannerError(err.message);
    }
  };

  const handleCreateTask = async ({ name, deadline }) => {
    await createTask({ name, deadline });
    await syncDashboard(taskFilter);
  };

  const handleToggleTask = async (task) => {
    try {
      await updateTask(task.id, { completed: !task.completed });
      await syncDashboard(taskFilter);
    } catch (err) {
      setBannerError(err.message);
    }
  };

  const handleConfirmModalDelete = async (task) => {
    setTaskToDelete(null);
    try {
      await deleteTask(task.id, true);
      await syncDashboard(taskFilter);
    } catch (err) {
      setBannerError(err.message);
    }
  };

  const handleSendMessage = async (text, confirmedDeleteIds = []) => {
    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    };

    const historyForApi = messages
      .filter((m) => m.id !== 'msg-welcome')
      .slice(-8)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }));

    setMessages((prev) => [...prev, userMsg]);
    setIsSending(true);
    setThinkingStage('Gemini is analyzing intent & checking tool declarations...');

    const stageTimer = setTimeout(() => {
      setThinkingStage('Executing selected Python tools & validating outputs...');
    }, 950);

    try {
      const res = await sendChatMessage({
        message: text,
        history: historyForApi,
        confirmedDeleteIds,
      });

      const agentMsg = {
        id: res.request_id || `agent-${Date.now()}`,
        role: 'agent',
        model: res.model,
        content: res.response,
        toolCalls: res.tool_calls || [],
        pendingConfirmations: res.pending_confirmations || [],
        learningMode: res.learning_mode || null,
        durationMs: res.duration_ms,
      };

      setMessages((prev) => [...prev, agentMsg]);
      if (res.learning_mode) {
        setLatestLearningData(res.learning_mode);
      }
      await syncDashboard(taskFilter);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'agent',
          model: 'System Error',
          content: `⚠️ Failed to reach TaskPilot backend: ${err.message}`,
          toolCalls: [],
          pendingConfirmations: [],
        },
      ]);
    } finally {
      clearTimeout(stageTimer);
      setIsSending(false);
    }
  };

  const handleConfirmAgentDeletion = async (messageId, pendingTask) => {
    // Clear the pending confirmation card on that message and send confirmed deletion through the agent
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              pendingConfirmations: (m.pendingConfirmations || []).filter(
                (t) => t.id !== pendingTask.id
              ),
            }
          : m
      )
    );
    await handleSendMessage(
      `I confirm deleting task ${pendingTask.id} ("${pendingTask.name}").`,
      [pendingTask.id]
    );
  };

  const handleCancelAgentDeletion = (messageId, pendingTask) => {
    setMessages((prev) => [
      ...prev.map((m) =>
        m.id === messageId
          ? {
              ...m,
              pendingConfirmations: (m.pendingConfirmations || []).filter(
                (t) => t.id !== pendingTask.id
              ),
            }
          : m
      ),
      {
        id: `cancel-${Date.now()}`,
        role: 'agent',
        model: 'Human Safety Gate',
        content: `Deletion of task **${pendingTask.name}** (\`${pendingTask.id}\`) was cancelled. Your task remains safely stored.`,
        toolCalls: [],
        pendingConfirmations: [],
      },
    ]);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        agentStatus={agentStatus}
        metrics={metrics}
        learningMode={learningMode}
        onToggleLearningMode={setLearningMode}
        onRefresh={() => syncDashboard(taskFilter)}
        isRefreshing={isRefreshing}
      />

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 sm:px-6 py-5 space-y-5">
        {bannerError && (
          <div className="rounded-xl bg-rose-950/40 border border-rose-500/40 px-4 py-3 text-xs text-rose-200 flex items-center justify-between">
            <span>{bannerError}</span>
            <button
              type="button"
              onClick={() => syncDashboard(taskFilter)}
              className="underline font-semibold ml-4 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Educational Mode Panel (visible when LEARNING MODE switch is ON) */}
        {learningMode && (
          <LearningModePanel
            learningData={latestLearningData}
            modelName={agentStatus?.model}
          />
        )}

        {/* Main 12-Column Mission Control Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left 7 Columns: Agent Chat Interface */}
          <div className="lg:col-span-7">
            <ChatPanel
              messages={messages}
              isSending={isSending}
              thinkingStage={thinkingStage}
              learningMode={learningMode}
              onSendMessage={(prompt) => handleSendMessage(prompt)}
              onConfirmAgentDeletion={handleConfirmAgentDeletion}
              onCancelAgentDeletion={handleCancelAgentDeletion}
            />
          </div>

          {/* Right 5 Columns: Task Manager + Agent Activity Timeline */}
          <div className="lg:col-span-5 space-y-5">
            <TaskManager
              tasks={tasks}
              filter={taskFilter}
              onFilterChange={handleFilterChange}
              onCreateTask={handleCreateTask}
              onToggleTask={handleToggleTask}
              onRequestDeleteTask={(task) => setTaskToDelete(task)}
            />

            <ActivityTimeline activities={activities} />
          </div>
        </div>
      </main>

      {/* Native HTML Modal Dialog for Task Deletion Confirmation */}
      <DeleteConfirmDialog
        task={taskToDelete}
        onConfirm={handleConfirmModalDelete}
        onCancel={() => setTaskToDelete(null)}
      />
    </div>
  );
}
