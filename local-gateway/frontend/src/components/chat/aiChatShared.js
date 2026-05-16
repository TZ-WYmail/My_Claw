export const PLANNING_TEMPLATE = `收集数据 | 2026-05-18 | 2026-05-16 |
写周报 | 2026-05-19 | 2026-05-18 | 收集数据
准备汇报 | 2026-05-20 | | 写周报`;

export const REASON_LABELS = {
  all: '全部原因',
  capacity_conflict: '容量冲突',
  dependency_conflict: '依赖冲突',
  calendar_conflict: '日历冲突',
  time_window_conflict: '时间窗口',
  optimization: '优化建议',
};

export function parsePlanningDraft(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [name, due, earliestStart, dependencies] = line.split('|').map((item) => (item || '').trim());
      return {
        key: `${name || 'task'}-${index}`,
        task_name: name,
        due_time: due || '',
        earliest_start: earliestStart || '',
        depends_on: dependencies ? dependencies.split(',').map((item) => item.trim()).filter(Boolean) : [],
      };
    })
    .filter((task) => task.task_name);
}

export function createPlanningTask(seed = {}, index = 0) {
  return {
    id: seed.id || `draft-${Date.now()}-${index}`,
    key: seed.key || seed.id || `draft-${Date.now()}-${index}`,
    task_name: seed.task_name || '',
    due_time: seed.due_time || '',
    earliest_start: seed.earliest_start || '',
    depends_on: Array.isArray(seed.depends_on) ? seed.depends_on : [],
  };
}

export function serializePlanningDraft(tasks) {
  return (tasks || [])
    .filter((task) => task.task_name?.trim())
    .map((task) => [
      task.task_name?.trim() || '',
      task.due_time?.trim() || '',
      task.earliest_start?.trim() || '',
      (task.depends_on || []).join(', '),
    ].join(' | '))
    .join('\n');
}

export function formatPlanningDate(value) {
  if (!value) return '未设置';
  const normalized = value.includes('T') ? value : (value.length === 10 ? `${value}T00:00:00` : value);
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

export function buildScheduleLookup(view) {
  const lookup = {};
  Object.entries(view?.daily_plan || {}).forEach(([day, info]) => {
    (info.tasks || []).forEach((task) => {
      if (!lookup[task.task_name]) lookup[task.task_name] = [];
      lookup[task.task_name].push({
        day,
        hours: task.hours,
        time_slot: task.time_slot,
        energy_type: task.energy_type,
      });
    });
  });
  return lookup;
}

export function sumPlannedHours(view) {
  return Object.values(view?.daily_plan || {}).reduce((total, info) => total + (info.total_hours || 0), 0);
}

export function getRiskTone(level) {
  if (level === 'high') return { label: '高风险', color: 'var(--error)', background: 'rgba(206,58,44,0.12)' };
  if (level === 'medium') return { label: '中风险', color: 'var(--warning)', background: 'rgba(207,160,61,0.16)' };
  return { label: '低风险', color: 'var(--success)', background: 'rgba(52,93,76,0.12)' };
}

export function summarizeText(text, limit = 140) {
  const normalized = (text || '')
    .replace(/[`#>*_\-\[\]]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!normalized) return '暂无新内容';
  return normalized.length > limit ? `${normalized.slice(0, limit)}...` : normalized;
}

export function formatMessageStamp(value) {
  if (!value) return '实时';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${month}/${day} ${hour}:${minute}`;
}

export function buildConversationRounds(messages) {
  const rounds = [];
  let pendingRound = null;

  messages.forEach((message) => {
    if (message.role === 'user') {
      pendingRound = {
        id: `round-${message.id}`,
        user: message,
        assistant: null,
      };
      rounds.push(pendingRound);
      return;
    }

    if (!pendingRound || pendingRound.assistant) {
      rounds.push({
        id: `round-${message.id}`,
        user: null,
        assistant: message,
      });
      pendingRound = null;
      return;
    }

    pendingRound.assistant = message;
  });

  return rounds.map((round, index) => ({
    ...round,
    index: index + 1,
  }));
}
