function toValidDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatTime(iso) {
  const d = toValidDate(iso);
  if (!d) return '-';
  const w = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ` +
         `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} (${w[d.getDay()]})`;
}

export function formatTimeShort(iso) {
  const d = toValidDate(iso);
  if (!d) return '-';
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

export function escapeHtml(str) {
  if (str == null) return '';
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

export const RECURRENCE_MAP = { once: '一次', daily: '每天', weekly: '每周', monthly: '每月' };

export function recurrenceLabel(value) {
  return RECURRENCE_MAP[value] || value || '未设置';
}

const STATUS_LABELS = {
  pending: '待执行', completed: '已完成', deleted: '已删除',
  '待执行': '待执行', '已完成': '已完成', '已删除': '已删除',
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || status || '未设置';
}

export function badgeClass(status) {
  if (status === 'completed' || status === '已完成') return 'completed';
  if (status === 'deleted' || status === '已删除') return 'error';
  return 'pending';
}

export function operationIcon(op) {
  const map = { add_task: '📋', complete_task: '✅', delete_task: '🗑️', download: '📥', sandbox: '🔧' };
  return map[op] || '📌';
}
