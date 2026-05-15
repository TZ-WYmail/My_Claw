import { useEffect, useMemo, useState, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { useApp } from '../contexts/AppContext';
import { formatTimeShort, operationIcon } from '../utils/format';

function overdueDays(dueTime) {
  if (!dueTime) return 0;
  const due = new Date(dueTime);
  const now = new Date();
  return Math.max(0, Math.floor((now - due) / (1000 * 60 * 60 * 24)));
}

function TodayCard({ title, children, action }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function Dashboard({ onCreateTask, onCreateNote, onOpenAi, onOpenTasks, onOpenCalendar, onOpenNotes, onCreateTaskNote, onOpenTaskDetail }) {
  const { loading, error, request } = useApi();
  const toast = useToast();
  const { refreshToken, notifyDataChange } = useApp();
  const [data, setData] = useState(null);
  const [streak, setStreak] = useState({ current_streak: 0, longest_streak: 0, weekly_rate: 0, today_total: 0, today_completed: 0 });
  const [pendingTasks, setPendingTasks] = useState([]);
  const [overdueTasks, setOverdueTasks] = useState([]);
  const [activePomodoro, setActivePomodoro] = useState(null);
  const [subtaskProgressMap, setSubtaskProgressMap] = useState({});

  const fetchToday = useCallback(() => {
    request(async () => {
      const res = await apiGet('/api/dashboard');
      if (res.status === 'error') throw new Error(res.message || '加载失败');
      setData(res);
      return res;
    }).catch(e => toast(e.message, 'error'));
  }, [request, toast]);

  const fetchStreak = useCallback(async () => {
    try {
      const res = await apiGet('/api/streak');
      if (res.status === 'success') setStreak(res);
    } catch {
      // silent
    }
  }, []);

  const fetchOverdueTasks = useCallback(async () => {
    try {
      const res = await apiPost('/api/task', { action: 'get_pending_tasks' });
      if (res.status === 'success' && res.tasks) {
        setPendingTasks(res.tasks || []);
        setOverdueTasks(res.tasks.filter(t => t.overdue).slice(0, 5));
      }
    } catch {
      // silent
    }
  }, []);

  const fetchPomodoroStatus = useCallback(async () => {
    try {
      const res = await apiGet('/api/advanced/pomodoro/status');
      if (res.status === 'success') setActivePomodoro(res.active_session || null);
    } catch {
      setActivePomodoro(null);
    }
  }, []);

  const fetchSubtaskProgress = useCallback(async (tasks) => {
    const slice = (tasks || []).slice(0, 6);
    if (slice.length === 0) {
      setSubtaskProgressMap({});
      return;
    }
    const entries = await Promise.all(slice.map(async (task) => {
      try {
        const res = await apiGet(`/api/advanced/tasks/${task.task_id}/subtasks`);
        const subtasks = res.status === 'success' ? (res.subtasks || []) : [];
        const total = subtasks.length;
        const completed = subtasks.filter(item => item.status === 'completed').length;
        return [task.task_id, { total, completed }];
      } catch {
        return [task.task_id, { total: 0, completed: 0 }];
      }
    }));
    setSubtaskProgressMap(Object.fromEntries(entries));
  }, []);

  const handleCompleteTask = useCallback(async (taskId) => {
    try {
      const res = await apiPost('/api/task', { action: 'complete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已完成', 'success');
      fetchToday();
      fetchStreak();
      fetchOverdueTasks();
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [fetchOverdueTasks, fetchStreak, fetchToday, notifyDataChange, toast]);

  const handlePushTask = useCallback(async (task, targetHour) => {
    if (!task?.task_id) return;
    const base = new Date();
    const date = new Date(base.getFullYear(), base.getMonth(), base.getDate(), targetHour, 0, 0, 0);
    try {
      const res = await apiPost(`/api/task/${task.task_id}`, {
        task_name: task.task_name,
        due_time: new Date(date.getTime() + 2 * 60 * 60 * 1000).toISOString(),
        start_time: date.toISOString(),
        end_time: new Date(date.getTime() + 60 * 60 * 1000).toISOString(),
        description: task.description,
        estimated_minutes: task.estimated_minutes,
        tags: task.tags || [],
      });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已改期', 'success');
      fetchToday();
      fetchOverdueTasks();
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [fetchOverdueTasks, fetchToday, notifyDataChange, toast]);

  useEffect(() => {
    fetchToday();
    fetchStreak();
    fetchOverdueTasks();
    fetchPomodoroStatus();
  }, [fetchToday, fetchStreak, fetchOverdueTasks, fetchPomodoroStatus, refreshToken]);

  useEffect(() => {
    fetchSubtaskProgress(pendingTasks);
  }, [fetchSubtaskProgress, pendingTasks]);

  const todayTasks = useMemo(() => {
    const list = pendingTasks.filter(task => {
      const today = new Date().toISOString().slice(0, 10);
      return (task.start_time && task.start_time.startsWith(today)) ||
        (task.due_time && task.due_time.startsWith(today)) ||
        task.overdue;
    });
    return Array.isArray(list) ? list.slice(0, 5) : [];
  }, [pendingTasks]);

  const recentNotes = useMemo(() => {
    const list = data?.recent_notes || [];
    return Array.isArray(list) ? list.slice(0, 5) : [];
  }, [data]);

  const recentLogs = useMemo(() => {
    const list = data?.recent_logs || [];
    return Array.isArray(list) ? list.slice(0, 5) : [];
  }, [data]);

  const noteReadyTasks = useMemo(() => {
    return pendingTasks
      .filter(task => task.start_time || task.due_time || task.description)
      .slice(0, 4);
  }, [pendingTasks]);

  const nextSuggestedTask = useMemo(() => {
    return todayTasks.find(task => task.task_id !== activePomodoro?.task_id) || overdueTasks[0] || todayTasks[0] || null;
  }, [activePomodoro?.task_id, overdueTasks, todayTasks]);

  const startPomodoroForTask = useCallback(async (task, durationMinutes = 25) => {
    if (!task?.task_id) return;
    try {
      const res = await request(async () => fetch('/api/advanced/pomodoro/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: task.task_id, duration_minutes: durationMinutes }),
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '启动番茄钟失败');
      toast('已开始专注', 'success');
      fetchPomodoroStatus();
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [fetchPomodoroStatus, notifyDataChange, request, toast]);

  const completePomodoro = useCallback(async () => {
    try {
      const res = await request(async () => fetch('/api/advanced/pomodoro/complete', { method: 'POST' }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '完成番茄钟失败');
      toast('专注已完成', 'success');
      fetchPomodoroStatus();
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [fetchPomodoroStatus, notifyDataChange, request, toast]);

  if (loading && !data) return <DashboardSkeleton />;
  if (error && !data) return <DashboardError error={error} onRetry={fetchToday} />;
  if (!data) return null;

  const progress = streak.today_total > 0 ? Math.round((streak.today_completed / streak.today_total) * 100) : 0;
  const focusTask = todayTasks[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{
        background: 'linear-gradient(135deg, rgba(10,132,255,0.18), rgba(48,209,88,0.08))',
        border: '1px solid rgba(10,132,255,0.18)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginBottom: 6 }}>今天工作台</div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 8 }}>
              {focusTask ? `先处理：${focusTask.task_name}` : '今天先开始一件最重要的事'}
            </h1>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              {focusTask
                ? '把今天的重点、时间和记录放在同一个地方。'
                : '创建今天的第一项任务，然后安排时间。'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={onCreateTask}>+ 新任务</button>
            <button className="btn btn-ghost" onClick={onCreateNote}>+ 新笔记</button>
            <button className="btn btn-ghost" onClick={onOpenAi}>AI 安排</button>
          </div>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📋</div>
          <div>
            <div className="stat-value">{todayTasks.length}</div>
            <div className="stat-label">今日任务</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">⏱️</div>
          <div>
            <div className="stat-value">{progress}%</div>
            <div className="stat-label">今日进度</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🔥</div>
          <div>
            <div className="stat-value">{streak.current_streak}</div>
            <div className="stat-label">连续天数</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">⚠️</div>
          <div>
            <div className="stat-value">{overdueTasks.length}</div>
            <div className="stat-label">逾期任务</div>
          </div>
        </div>
      </div>

      <TodayCard
        title="当前专注"
        action={activePomodoro ? <button className="btn btn-sm btn-primary" onClick={completePomodoro}>完成专注</button> : null}
      >
        {activePomodoro ? (
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 600 }}>{activePomodoro.task_id === focusTask?.task_id ? focusTask?.task_name || '当前任务' : '专注进行中'}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                已启动 {activePomodoro.duration_minutes} 分钟 · 开始于 {formatTimeShort(activePomodoro.start_time)}
              </div>
            </div>
            <span className="badge badge-completed">进行中</span>
          </div>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 600 }}>{nextSuggestedTask ? `下一步：${nextSuggestedTask.task_name}` : '暂无可专注任务'}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                {nextSuggestedTask ? '先开一个 25 分钟番茄钟，把当前阻塞项推进一格。' : '先创建或安排今天的任务。'}
              </div>
            </div>
            {nextSuggestedTask && <button className="btn btn-sm btn-primary" onClick={() => startPomodoroForTask(nextSuggestedTask)}>开始 25 分钟</button>}
          </div>
        )}
      </TodayCard>

      <div className="content-grid-2">
        <TodayCard
          title="今日重点任务"
          action={<button className="btn btn-sm btn-ghost" onClick={onOpenTasks}>全部任务</button>}
        >
          {todayTasks.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
              <div className="empty-state-icon">✨</div>
              <div className="empty-state-text">今天还没有重点任务</div>
              <div className="empty-state-hint">先创建一项任务，系统会帮你安排时间</div>
            </div>
          ) : (
            todayTasks.map(task => (
              <div key={task.task_id} style={{
                padding: 'var(--space-sm)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-tertiary)',
              }} className="task-row-compact">
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {task.task_name}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {task.start_time ? formatTimeShort(task.start_time) : '未安排时间'}
                  </div>
                  {subtaskProgressMap[task.task_id]?.total > 0 && (
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                      子任务 {subtaskProgressMap[task.task_id].completed}/{subtaskProgressMap[task.task_id].total}
                    </div>
                  )}
                </div>
                  <div className="inline-actions" style={{ flexShrink: 0, justifyContent: 'flex-end' }}>
                    <button className="btn btn-sm btn-ghost" onClick={() => startPomodoroForTask(task)}>专注</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(task)}>详情</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => handlePushTask(task, 20)}>今晚</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => handlePushTask(task, 9)}>明早</button>
                    {task.status === 'pending' && <button className="btn btn-sm btn-primary" onClick={() => handleCompleteTask(task.task_id)}>完成</button>}
                  </div>
                </div>
            ))
          )}
        </TodayCard>

        <TodayCard title="今日日程摘要" action={<button className="btn btn-sm btn-ghost" onClick={onOpenCalendar}>打开日历</button>}>
          <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            今日完成 <strong style={{ color: 'var(--text-primary)' }}>{streak.today_completed}</strong> / {streak.today_total || 0}
          </div>
          <div style={{
            height: 8,
            borderRadius: 999,
            background: 'var(--bg-tertiary)',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${progress}%`,
              background: progress >= 100 ? 'var(--success)' : 'var(--accent)',
            }} />
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
            {progress >= 100 ? '今日任务已完成' : '先处理最高优先级任务，再回到低优先级事项'}
          </div>
        </TodayCard>

        <TodayCard title="逾期提醒">
          {overdueTasks.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
              <div className="empty-state-icon">✅</div>
              <div className="empty-state-text">暂无逾期任务</div>
              <div className="empty-state-hint">保持今天的节奏即可</div>
            </div>
          ) : overdueTasks.map(task => (
            <div key={task.task_id} style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 'var(--space-sm)',
              padding: 'var(--space-sm)',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(255,59,48,0.06)',
              borderLeft: '3px solid var(--error)',
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>{task.task_name}</div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>
                  逾期 {overdueDays(task.due_time)} 天
                </div>
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-xs)', flexShrink: 0 }}>
                <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(task)}>详情</button>
                <span className="badge badge-error">风险</span>
              </div>
            </div>
          ))}
        </TodayCard>

        <TodayCard title="最近笔记" action={<button className="btn btn-sm btn-ghost" onClick={onOpenNotes}>全部笔记</button>}>
          {recentNotes.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
              <div className="empty-state-icon">📝</div>
              <div className="empty-state-text">暂无最近笔记</div>
              <div className="empty-state-hint">执行任务时顺手记录上下文</div>
            </div>
          ) : recentNotes.map(note => (
            <div key={note.note_id} style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 'var(--space-sm)',
              padding: 'var(--space-sm)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-tertiary)',
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {note.title}
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>
                  {formatTimeShort(note.updated_at || note.created_at)}
                </div>
              </div>
              <span className="badge badge-pending">笔记</span>
            </div>
          ))}
        </TodayCard>
      </div>

      <div className="content-grid-2">
        <TodayCard title="下一步建议">
          {nextSuggestedTask ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'center' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{nextSuggestedTask.task_name}</div>
              <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                  {nextSuggestedTask.overdue ? '先止损：这是逾期项，优先清掉。' : nextSuggestedTask.start_time ? `按计划开始于 ${formatTimeShort(nextSuggestedTask.start_time)}` : '先把它推进到一个可见结果，再切下一项。'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-xs)', flexShrink: 0 }}>
                <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(nextSuggestedTask)}>详情</button>
                <button className="btn btn-sm btn-primary" onClick={() => startPomodoroForTask(nextSuggestedTask)}>开始</button>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)' }}>暂无建议，先创建今天的第一项任务。</div>
          )}
        </TodayCard>

        <TodayCard title="可记录任务">
          {noteReadyTasks.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
              <div className="empty-state-icon">🗒️</div>
              <div className="empty-state-text">暂无可记录任务</div>
              <div className="empty-state-hint">先安排今天任务，再补执行记录</div>
            </div>
          ) : noteReadyTasks.map(task => (
            <div key={task.task_id} style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 'var(--space-sm)',
              padding: 'var(--space-sm)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-tertiary)',
              alignItems: 'center',
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {task.task_name}
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                  {task.start_time ? `开始 ${formatTimeShort(task.start_time)}` : task.due_time ? `截止 ${formatTimeShort(task.due_time)}` : '无时间信息'}
                </div>
              </div>
              <button className="btn btn-sm btn-ghost" onClick={() => onCreateTaskNote?.(task)}>记笔记</button>
            </div>
          ))}
        </TodayCard>

        <TodayCard title="最近操作">
          {recentLogs.length === 0 ? (
            <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
              <div className="empty-state-icon">📋</div>
              <div className="empty-state-text">暂无操作记录</div>
            </div>
          ) : recentLogs.map(log => (
            <div key={log.id || log.created_at} style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 'var(--space-sm)',
              padding: 'var(--space-sm)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-tertiary)',
            }}>
              <div style={{ minWidth: 0, display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                <span>{operationIcon(log.operation)}</span>
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {log.detail || log.operation}
                </span>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', flexShrink: 0 }}>
                {formatTimeShort(log.created_at)}
              </span>
            </div>
          ))}
        </TodayCard>

        <TodayCard title="AI 建议">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <button className="btn btn-ghost" onClick={onOpenAi}>安排今天</button>
            <button className="btn btn-ghost" onClick={onOpenAi}>拆解任务</button>
            <button className="btn btn-ghost" onClick={onOpenAi}>整理笔记</button>
          </div>
        </TodayCard>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div className="card" style={{ minHeight: 120 }}>
        <div className="skeleton skeleton-text" style={{ width: 120, marginBottom: 'var(--space-sm)' }} />
        <div className="skeleton skeleton-text" style={{ width: '60%' }} />
      </div>
      <div className="stats-grid">
        {[1, 2, 3, 4].map(i => (
          <div className="stat-card" key={i}>
            <div className="skeleton" style={{ width: 36, height: 36, borderRadius: '50%' }} />
            <div style={{ flex: 1 }}>
              <div className="skeleton skeleton-text" style={{ width: 60 }} />
              <div className="skeleton skeleton-text" style={{ width: 90 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardError({ error, onRetry }) {
  return (
    <div className="empty-state" style={{ minHeight: 300 }}>
      <div className="empty-state-icon">⚠️</div>
      <div className="empty-state-text">加载今天工作台失败</div>
      <div className="empty-state-hint">{error}</div>
      <button className="btn btn-primary" onClick={onRetry}>重试</button>
    </div>
  );
}
