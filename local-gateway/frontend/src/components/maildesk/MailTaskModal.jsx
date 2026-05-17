import { PRIORITY_OPTIONS } from '../../utils/constants';

export default function MailTaskModal({
  open,
  onClose,
  onSubmit,
  thread,
  taskCreating,
  taskDraftForm,
  setTaskDraftForm,
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal atlas-paper-stack" style={{ width: 'min(720px, 92vw)', maxHeight: '88vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <div className="board-lane-header" style={{ marginBottom: 'var(--space-lg)' }}>
          <div>
            <div className="section-kicker">TASK FALLOUT</div>
            <h3 className="board-lane-title">把这封信压成任务</h3>
            <div className="board-lane-copy">
              邮件里的事情不该继续悬在纸页上。先写清任务名、时间和说明，再让它脱离书信流，真正进入执行面。
            </div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="command-form">
          <div className="mail-composer-state" style={{ marginBottom: 'var(--space-md)' }}>
            <span className="badge badge-ghost">{thread?.subject || '未命名来信'}</span>
            {thread?.risk_level && <span className="badge badge-warning">风险 {thread.risk_level}</span>}
          </div>

          <div className="form-group">
            <label>任务标题</label>
            <input
              value={taskDraftForm.task_name}
              onChange={(e) => setTaskDraftForm((prev) => ({ ...prev, task_name: e.target.value }))}
              placeholder="邮件跟进：确认交付时间"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
            <div className="form-group">
              <label>截止时间</label>
              <input
                type="datetime-local"
                value={taskDraftForm.due_time}
                onChange={(e) => setTaskDraftForm((prev) => ({ ...prev, due_time: e.target.value }))}
              />
            </div>
            <div className="form-group">
              <label>优先级</label>
              <select
                value={taskDraftForm.priority}
                onChange={(e) => setTaskDraftForm((prev) => ({ ...prev, priority: Number(e.target.value) }))}
              >
                {PRIORITY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>任务说明</label>
            <textarea
              value={taskDraftForm.description}
              onChange={(e) => setTaskDraftForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="把这封信里真正需要推进的事情写清楚。"
              style={{ minHeight: 180 }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={taskCreating}>先收起</button>
            <button type="submit" className="btn btn-primary" disabled={taskCreating}>
              {taskCreating ? '落任务中…' : '落成这项任务'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
