export function formatTime(iso) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    const w = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ` +
           `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} (${w[d.getDay()]})`;
  } catch { return iso; }
}

export function formatTimeShort(iso) {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

export function escapeHtml(str) {
  if (str == null) return '';
  const d = document.createElement('div');
  d.textContent = String(str);
  return d.innerHTML;
}

export const RECURRENCE_MAP = { once: '一次', daily: '每天', weekly: '每周', monthly: '每月' };

export function badgeClass(status) {
  if (status === '已完成') return 'completed';
  if (status === '已删除') return 'error';
  return 'pending';
}

export function operationIcon(op) {
  const map = { add_task: '📋', complete_task: '✅', delete_task: '🗑️', download: '📥', sandbox: '🔧' };
  return map[op] || '📌';
}
