const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = data?.detail;
    const errorMessage =
      typeof detail === 'string'
        ? detail
        : detail?.message || data?.error || `Request failed with status ${response.status}`;
    const error = new Error(errorMessage);
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

export async function fetchActivity(limit = 25) {
  return request(`/activity?limit=${limit}`);
}

export async function fetchTasks(statusFilter = 'all') {
  return request(`/tasks?status=${encodeURIComponent(statusFilter)}`);
}

export async function createTask({ name, deadline }) {
  return request('/tasks', {
    method: 'POST',
    body: JSON.stringify({ name, deadline }),
  });
}

export async function updateTask(taskId, patch) {
  return request(`/tasks/${encodeURIComponent(taskId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function deleteTask(taskId, confirmed = true) {
  return request(`/tasks/${encodeURIComponent(taskId)}?confirmed=${confirmed ? 'true' : 'false'}`, {
    method: 'DELETE',
  });
}

export async function sendChatMessage({ message, history = [], confirmedDeleteIds = [] }) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      history,
      confirmed_delete_ids: confirmedDeleteIds,
    }),
  });
}
