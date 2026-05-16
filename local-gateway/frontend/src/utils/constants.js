export const DOWNLOAD_CATEGORIES = [
  { value: 'misc', label: '通用' },
  { value: 'paper', label: '文档' },
  { value: 'video', label: '媒体' },
  { value: 'code', label: '代码' },
];

export const HABIT_COLORS = ['#27ae60', '#0a84ff', '#ff9f0a', '#ff453a', '#af52de', '#5ac8fa', '#ff6b6b', '#30d158'];

export const WORKFLOW_TRIGGER_TYPES = ['schedule', 'task_completed', 'task_created', 'habit_checkin', 'download_completed', 'webhook', 'startup'];

export const PRIORITY_OPTIONS = [
  { value: 0, label: '紧急', tone: 'error', color: '#ff3b30' },
  { value: 1, label: '高', tone: 'warning', color: '#ff9500' },
  { value: 2, label: '中', tone: 'pending', color: '#0a84ff' },
  { value: 3, label: '低', tone: 'completed', color: '#8e8e93' },
];
