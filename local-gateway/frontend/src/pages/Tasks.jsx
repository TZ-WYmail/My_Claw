import { useState, useEffect, useCallback, useMemo } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { useApp } from '../contexts/AppContext';
import { formatTimeShort, RECURRENCE_MAP, badgeClass, statusLabel } from '../utils/format';

const PRIORITY_MAP = { 0: '紧急', 1: '高', 2: '中', 3: '低' };
const PRIORITY_COLORS = { 0: 'error', 1: 'warning', 2: 'pending', 3: 'completed' };
const TABS = [
  { key: 'week', label: '周视图' },
  { key: 'all', label: '全部任务' },
];

export default function Tasks({ quickAction, clearQuickAction, onCreateNoteFromTask }) {
  const [tab, setTab] = useState('week');
  const [focusedTask, setFocusedTask] = useState(null);

  useEffect(() => {
    if (quickAction?.type === 'create_task') {
      setTab('all');
    }
    if (quickAction?.type === 'focus_task' && quickAction?.task) {
      setTab('all');
      setFocusedTask(quickAction.task);
      clearQuickAction?.();
    }
  }, [quickAction, clearQuickAction]);

  return (
    <div>
      <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
      {TABS.map(t => (
          <button
            key={t.key}
            className={`btn ${tab === t.key ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'week' ? (
        <WeekView onCreateNoteFromTask={onCreateNoteFromTask} />
      ) : (
        <AllTasksView
          autoOpenCreate={quickAction?.type === 'create_task'}
          prefill={quickAction?.type === 'create_task' ? quickAction?.prefill : null}
          focusedTask={focusedTask}
          clearFocusedTask={() => setFocusedTask(null)}
          consumeCreateAction={() => {
            if (quickAction?.type === 'create_task') clearQuickAction?.();
          }}
          onCreateNoteFromTask={onCreateNoteFromTask}
        />
      )}
    </div>
  );
}

/* ── Week View ────────────────────────────────────────── */

function getWeekRange(offset) {
  const now = new Date();
  const day = now.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setDate(now.getDate() + mondayOffset + offset * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { monday: fmt(monday), sunday: fmt(sunday), mondayDate: monday, sundayDate: sunday };
}

function WeekView({ onCreateNoteFromTask }) {
  const { loading, request } = useApi();
  const toast = useToast();
  const [offset, setOffset] = useState(0);
  const [tasks, setTasks] = useState([]);
  const [popupTaskId, setPopupTaskId] = useState(null);

  const { monday, sunday, mondayDate, sundayDate } = getWeekRange(offset);

  const fetchWeek = useCallback(async () => {
    try {
      const res = await request(async () =>
        apiPost('/api/task', {
          action: 'get_weekly_plan',
          due_time: monday + 'T00:00:00',
          task_name: sunday + 'T23:59:59',
        })
      );
      if (res.status === 'error') throw new Error(res.message);
      setTasks(res.tasks || []);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, monday, sunday]);

  useEffect(() => { fetchWeek(); }, [fetchWeek]);

  const goPrev = () => { setOffset(o => o - 1); };
  const goNext = () => { setOffset(o => o + 1); };
  const goToday = () => { setOffset(0); };

  const weekLabel = `${mondayDate.getMonth() + 1}/${mondayDate.getDate()} - ${sundayDate.getMonth() + 1}/${sundayDate.getDate()}`;

  // Build 7 day columns
  const dayCols = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(mondayDate);
    d.setDate(d.getDate() + i);
    const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
    const fmtDate = `${d.getMonth() + 1}/${d.getDate()}`;
    const isoDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { date: d, isoDate, weekday: weekdays[i], label: fmtDate };
  });

  const START_HOUR = 6;
  const END_HOUR = 23;
  const TOTAL_HOURS = END_HOUR - START_HOUR; // 17
  const ROW_HEIGHT = 40;

  // Parse ISO time string to get hours and minutes
  const parseTime = (isoStr) => {
    if (!isoStr) return null;
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return null;
    return { hour: d.getHours(), minute: d.getMinutes() };
  };

  // Get the date portion of an ISO string
  const parseDate = (isoStr) => {
    if (!isoStr) return null;
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return null;
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  // Format HH:MM from an ISO string
  const fmtHM = (isoStr) => {
    const t = parseTime(isoStr);
    if (!t) return '';
    return `${String(t.hour).padStart(2, '0')}:${String(t.minute).padStart(2, '0')}`;
  };

  const PRIORITY_BG = { 0: '#ff3b30', 1: '#ff9500', 2: '#0a84ff', 3: '#8e8e93' };

  // Separate scheduled and unscheduled tasks
  const scheduled = tasks.filter(t => t.start_time);
  const unscheduled = tasks.filter(t => !t.start_time);

  // Group scheduled tasks by their day
  const tasksByDay = {};
  dayCols.forEach(col => { tasksByDay[col.isoDate] = []; });
  scheduled.forEach(t => {
    const dayKey = parseDate(t.start_time);
    if (dayKey && tasksByDay[dayKey]) {
      tasksByDay[dayKey].push(t);
    }
  });

  // Compute current time indicator
  const now = new Date();
  const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const isCurrentWeek = offset === 0;
  const nowHour = now.getHours();
  const nowMinute = now.getMinutes();
  const showNowLine = isCurrentWeek && nowHour >= START_HOUR && nowHour <= END_HOUR;
  const nowTopPx = ((nowHour - START_HOUR) + nowMinute / 60) * ROW_HEIGHT;

  // Complete / delete handlers
  const handleComplete = async (taskId) => {
    try {
      const res = await apiPost('/api/task', { action: 'complete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已完成', 'success');
      setPopupTaskId(null);
      fetchWeek();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleDelete = async (taskId) => {
    if (!confirm('确认删除此任务?')) return;
    try {
      const res = await apiPost('/api/task', { action: 'delete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已删除', 'success');
      setPopupTaskId(null);
      fetchWeek();
    } catch (e) { toast(e.message, 'error'); }
  };

  // Close popup when clicking outside
  useEffect(() => {
    if (popupTaskId === null) return;
    const handler = () => setPopupTaskId(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [popupTaskId]);

  return (
    <div>
      {/* Navigation bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <button className="btn btn-sm" onClick={goPrev}>&larr; 上一周</button>
        <button className="btn btn-sm btn-primary" onClick={goToday}>本周</button>
        <button className="btn btn-sm" onClick={goNext}>下一周 &rarr;</button>
        <span style={{ fontSize: '0.9rem', fontWeight: 500, marginLeft: 'var(--space-sm)' }}>{weekLabel}</span>
      </div>

      {loading ? (
        <div className="card">
          {[1, 2, 3].map(i => (
            <div className="skeleton skeleton-text" key={i} style={{ height: 60, marginBottom: 'var(--space-sm)' }} />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📅</div>
            <div className="empty-state-text">本周暂无任务</div>
          </div>
        </div>
      ) : (
        <>
          {/* Timeline grid */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {/* Column headers */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '60px repeat(7, 1fr)',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-card)',
            }}>
              <div style={{ padding: '8px 4px', fontSize: '0.75rem', color: 'var(--text-tertiary)', textAlign: 'center' }}></div>
              {dayCols.map(col => {
                const isToday = col.isoDate === todayIso;
                return (
                  <div key={col.isoDate} style={{
                    padding: '8px 4px',
                    textAlign: 'center',
                    fontSize: '0.78rem',
                    fontWeight: isToday ? 600 : 400,
                    color: isToday ? 'var(--accent)' : 'var(--text-primary)',
                    borderBottom: isToday ? '2px solid var(--accent)' : 'none',
                  }}>
                    <div>周{col.weekday}</div>
                    <div style={{ fontSize: '0.7rem', color: isToday ? 'var(--accent)' : 'var(--text-tertiary)' }}>{col.label}</div>
                  </div>
                );
              })}
            </div>

            {/* Scrollable timeline area */}
            <div style={{
              overflowY: 'auto',
              maxHeight: 500,
              position: 'relative',
            }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '60px repeat(7, 1fr)',
                position: 'relative',
              }}>
                {/* Time labels column */}
                <div style={{ position: 'relative' }}>
                  {Array.from({ length: TOTAL_HOURS + 1 }, (_, i) => {
                    const hour = START_HOUR + i;
                    return (
                      <div key={hour} style={{
                        height: ROW_HEIGHT,
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'center',
                        fontSize: '0.7rem',
                        color: 'var(--text-tertiary)',
                        paddingTop: 2,
                        borderTop: '1px solid var(--border)',
                      }}>
                        {`${String(hour).padStart(2, '0')}:00`}
                      </div>
                    );
                  })}
                </div>

                {/* 7 day columns with task blocks */}
                {dayCols.map(col => {
                  const dayTasks = tasksByDay[col.isoDate] || [];
                  const isToday = col.isoDate === todayIso;
                  return (
                    <div key={col.isoDate} style={{ position: 'relative' }}>
                      {/* Hour grid lines */}
                      {Array.from({ length: TOTAL_HOURS + 1 }, (_, i) => (
                        <div key={i} style={{
                          height: ROW_HEIGHT,
                          borderTop: '1px solid var(--border)',
                        }} />
                      ))}

                      {/* Task blocks */}
                      {dayTasks.map(t => {
                        const startTime = parseTime(t.start_time);
                        const endTime = parseTime(t.end_time);
                        if (!startTime) return null;

                        const startOffset = startTime.hour + startTime.minute / 60 - START_HOUR;
                        let duration;
                        if (endTime) {
                          duration = (endTime.hour + endTime.minute / 60) - (startTime.hour + startTime.minute / 60);
                        } else {
                          duration = 1; // default 1 hour if no end time
                        }
                        if (duration < 0.25) duration = 0.25; // minimum 15 min

                        const topPx = startOffset * ROW_HEIGHT;
                        const heightPx = duration * ROW_HEIGHT;
                        const bgColor = PRIORITY_BG[t.priority] ?? PRIORITY_BG[2];
                        const timeRange = endTime ? `${fmtHM(t.start_time)}-${fmtHM(t.end_time)}` : fmtHM(t.start_time);
                        const isPopupOpen = popupTaskId === t.task_id;

                        return (
                          <div key={t.task_id} style={{ position: 'absolute', top: topPx, left: 2, right: 2, height: Math.max(heightPx, 18), zIndex: 2 }}>
                            <div
                              onClick={(e) => { e.stopPropagation(); setPopupTaskId(isPopupOpen ? null : t.task_id); }}
                              style={{
                                backgroundColor: bgColor,
                                color: '#fff',
                                borderRadius: 4,
                                padding: '2px 4px',
                                fontSize: '0.7rem',
                                lineHeight: 1.3,
                                overflow: 'hidden',
                                cursor: 'pointer',
                                height: '100%',
                                boxSizing: 'border-box',
                                position: 'relative',
                              }}
                            >
                              <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>
                                {t.task_name}
                              </div>
                              {heightPx >= 30 && (
                                <div style={{ opacity: 0.85, fontSize: '0.65rem' }}>{timeRange}</div>
                              )}
                            </div>

                            {/* Popup */}
                            {isPopupOpen && (
                              <div
                                onClick={(e) => e.stopPropagation()}
                                style={{
                                  position: 'absolute',
                                  top: '100%',
                                  left: 0,
                                  zIndex: 50,
                                  minWidth: 180,
                                  background: 'var(--bg-card)',
                                  border: '1px solid var(--border)',
                                  borderRadius: 8,
                                  boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                                  padding: 'var(--space-sm)',
                                  marginTop: 4,
                                }}
                              >
                                <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4 }}>{t.task_name}</div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                                  {timeRange}
                                </div>
                                <div style={{ marginBottom: 8 }}>
                                  <span className={`badge badge-${PRIORITY_COLORS[t.priority] || 'pending'}`}>
                                    {PRIORITY_MAP[t.priority] || '中'}
                                  </span>
                                </div>
                                <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                                  <button className="btn btn-sm btn-ghost" onClick={() => onCreateNoteFromTask?.(t)}>笔记</button>
                                  {t.status === 'pending' && (
                                    <button className="btn btn-sm btn-success" onClick={() => handleComplete(t.task_id)}>完成</button>
                                  )}
                                  {t.status !== 'deleted' && (
                                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(t.task_id)}>删除</button>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}

                      {/* Current time indicator */}
                      {showNowLine && isToday && (
                        <div style={{
                          position: 'absolute',
                          left: 0,
                          right: 0,
                          top: nowTopPx,
                          height: 2,
                          backgroundColor: '#ff3b30',
                          zIndex: 5,
                          pointerEvents: 'none',
                        }}>
                          <div style={{
                            position: 'absolute',
                            left: -3,
                            top: -3,
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            backgroundColor: '#ff3b30',
                          }} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Unscheduled tasks */}
          {unscheduled.length > 0 && (
            <div className="card" style={{ marginTop: 'var(--space-md)' }}>
              <h4 style={{ fontSize: '0.85rem', marginBottom: 'var(--space-sm)', color: 'var(--text-secondary)' }}>未安排时间</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
                {unscheduled.map(t => (
                  <div
                    key={t.task_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-sm)',
                      padding: '6px 8px',
                      borderRadius: 6,
                      background: 'var(--bg-secondary)',
                      cursor: 'pointer',
                      position: 'relative',
                    }}
                    onClick={(e) => { e.stopPropagation(); setPopupTaskId(popupTaskId === t.task_id ? null : t.task_id); }}
                  >
                    <span className={`badge badge-${PRIORITY_COLORS[t.priority] || 'pending'}`}>
                      {PRIORITY_MAP[t.priority] || '中'}
                    </span>
                    <span style={{ fontSize: '0.82rem', fontWeight: 500 }}>{t.task_name}</span>
                    {t.due_time && (
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
                        截止 {fmtHM(t.due_time)}
                      </span>
                    )}

                    {/* Popup for unscheduled */}
                    {popupTaskId === t.task_id && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          position: 'absolute',
                          top: '100%',
                          left: 0,
                          zIndex: 50,
                          minWidth: 180,
                          background: 'var(--bg-card)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                          padding: 'var(--space-sm)',
                          marginTop: 2,
                        }}
                      >
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4 }}>{t.task_name}</div>
                        <div style={{ marginBottom: 8 }}>
                          <span className={`badge badge-${PRIORITY_COLORS[t.priority] || 'pending'}`}>
                            {PRIORITY_MAP[t.priority] || '中'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                          <button className="btn btn-sm btn-ghost" onClick={() => onCreateNoteFromTask?.(t)}>笔记</button>
                          {t.status === 'pending' && (
                            <button className="btn btn-sm btn-success" onClick={() => handleComplete(t.task_id)}>完成</button>
                          )}
                          {t.status !== 'deleted' && (
                            <button className="btn btn-sm btn-danger" onClick={() => handleDelete(t.task_id)}>删除</button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function getOverdueDays(dueTime) {
  if (!dueTime) return 0;
  const due = new Date(dueTime);
  const now = new Date();
  return Math.max(0, Math.floor((now - due) / (1000 * 60 * 60 * 24)));
}

/* ── All Tasks View ───────────────────────────────────── */

function AllTasksView({ autoOpenCreate = false, prefill = null, focusedTask = null, clearFocusedTask, consumeCreateAction, onCreateNoteFromTask }) {
  const { loading, request } = useApi();
  const toast = useToast();
  const { refreshToken, notifyDataChange } = useApp();
  const [tasks, setTasks] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [showForm, setShowForm] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [justCompleted, setJustCompleted] = useState(null);
  const [detailTask, setDetailTask] = useState(null);
  const [relatedNotes, setRelatedNotes] = useState([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [subtasks, setSubtasks] = useState([]);
  const [subtasksLoading, setSubtasksLoading] = useState(false);
  const [activePomodoro, setActivePomodoro] = useState(null);
  const [weekContext, setWeekContext] = useState([]);

  useEffect(() => {
    if (autoOpenCreate) {
      setShowForm(true);
      consumeCreateAction?.();
    }
  }, [autoOpenCreate, consumeCreateAction]);

  const fetchTasks = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page, keyword, status: statusFilter, page_size: 20 });
      const res = await request(async () => apiGet(`/api/tasks/all?${params}`));
      if (res.status === 'error') throw new Error(res.message);
      setTasks(res.tasks || []);
      setTotal(res.total || 0);
      setTotalPages(res.total_pages || 0);
      setSelectedIds(new Set());
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, page, keyword, statusFilter]);

  useEffect(() => { fetchTasks(); }, [fetchTasks, refreshToken]);

  const resolvedDetailTask = useMemo(() => {
    if (!detailTask) return null;
    return tasks.find(item => item.task_id === detailTask.task_id) || detailTask;
  }, [detailTask, tasks]);

  const fetchRelatedNotes = useCallback(async (task) => {
    if (!task?.task_id) {
      setRelatedNotes([]);
      return [];
    }
    const res = await apiGet('/api/notes?page_size=100');
    if (res.status === 'success') {
      const matched = (res.notes || []).filter(note => note.task_id === task.task_id);
      setRelatedNotes(matched);
      return matched;
    }
    setRelatedNotes([]);
    return [];
  }, []);

  const fetchSubtasks = useCallback(async (task) => {
    if (!task?.task_id) {
      setSubtasks([]);
      return [];
    }
    const res = await apiGet(`/api/advanced/tasks/${task.task_id}/subtasks`);
    if (res.status === 'success') {
      setSubtasks(res.subtasks || []);
      return res.subtasks || [];
    }
    setSubtasks([]);
    return [];
  }, []);

  const fetchPomodoroStatus = useCallback(async () => {
    try {
      const res = await apiGet('/api/advanced/pomodoro/status');
      if (res.status === 'success') setActivePomodoro(res.active_session || null);
    } catch {
      setActivePomodoro(null);
    }
  }, []);

  const fetchWeekContext = useCallback(async () => {
    try {
      const now = new Date();
      const day = now.getDay();
      const mondayOffset = day === 0 ? -6 : 1 - day;
      const monday = new Date(now);
      monday.setDate(now.getDate() + mondayOffset);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      const fmt = (d, suffix) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T${suffix}`;
      const res = await apiPost('/api/task', {
        action: 'get_weekly_plan',
        due_time: fmt(monday, '00:00:00'),
        task_name: fmt(sunday, '23:59:59'),
      });
      if (res.status === 'success') {
        setWeekContext(res.tasks || []);
        return res.tasks || [];
      }
    } catch {
      setWeekContext([]);
    }
    return [];
  }, []);

  const loadDetailBundle = useCallback(async (task) => {
    if (!task?.task_id) return;
    setNotesLoading(true);
    setSubtasksLoading(true);
    try {
      await Promise.all([
        fetchRelatedNotes(task),
        fetchSubtasks(task),
        fetchPomodoroStatus(),
        fetchWeekContext(),
      ]);
    } finally {
      setNotesLoading(false);
      setSubtasksLoading(false);
    }
  }, [fetchPomodoroStatus, fetchRelatedNotes, fetchSubtasks, fetchWeekContext]);

  const openDetail = useCallback((task) => {
    setDetailTask(task);
    loadDetailBundle(task);
  }, [loadDetailBundle]);

  useEffect(() => {
    if (!focusedTask?.task_id) return;
    openDetail(focusedTask);
    clearFocusedTask?.();
  }, [focusedTask, openDetail, clearFocusedTask]);

  const handleComplete = async (taskId) => {
    try {
      const res = await apiPost('/api/task', { action: 'complete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);

      // Show completion animation
      setJustCompleted(taskId);

      // Show progress toast
      const pendingRes = await apiPost('/api/task', { action: 'get_pending_tasks' });
      if (pendingRes.status === 'success') {
        const today = new Date().toISOString().slice(0, 10);
        const todayTasks = pendingRes.tasks.filter(t =>
          (t.start_time && t.start_time.startsWith(today)) ||
          (t.due_time && t.due_time.startsWith(today))
        );
        const todayCompleted = todayTasks.filter(t => t.status === 'completed').length;
        const todayTotal = todayTasks.length;
        if (todayTotal > 0 && todayCompleted === todayTotal) {
          toast('太棒了！今日任务全部完成 🎉', 'success');
        } else {
          toast(`已完成！今日进度 ${todayCompleted}/${todayTotal}`, 'success');
        }
      } else {
        toast('任务已完成', 'success');
      }

      // Wait for animation, then refresh
      setTimeout(() => {
        setJustCompleted(null);
        fetchTasks();
        notifyDataChange();
      }, 800);
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleDelete = async (taskId) => {
    if (!confirm('确认删除此任务?')) return;
    try {
      const res = await apiPost('/api/task', { action: 'delete_task', task_id: taskId });
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已删除', 'success');
      fetchTasks();
      notifyDataChange();
    } catch (e) { toast(e.message, 'error'); }
  };

  // Batch operations
  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === tasks.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(tasks.map(t => t.task_id)));
    }
  };

  const clearSelection = () => setSelectedIds(new Set());

  const handleBatchComplete = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    try {
      const res = await apiPost('/api/task', { action: 'batch_complete', task_ids: ids });
      if (res.status === 'error') throw new Error(res.message);
      toast(res.message || `已完成 ${ids.length} 项任务`, 'success');
      fetchTasks();
      notifyDataChange();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleBatchDelete = async () => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (!confirm(`确认删除 ${ids.length} 项任务？`)) return;
    try {
      const res = await apiPost('/api/task', { action: 'batch_delete', task_ids: ids });
      if (res.status === 'error') throw new Error(res.message);
      toast(res.message || `已删除 ${ids.length} 项任务`, 'success');
      fetchTasks();
      notifyDataChange();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleSearch = (e) => { setKeyword(e.target.value); setPage(1); };
  const handleStatusFilter = (e) => { setStatusFilter(e.target.value); setPage(1); };

  const allSelected = tasks.length > 0 && selectedIds.size === tasks.length;

  return (
    <div style={{ position: 'relative', paddingBottom: selectedIds.size > 0 ? 60 : 0 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="搜索任务..."
          value={keyword}
          onChange={handleSearch}
          style={{ maxWidth: 240 }}
        />
        <select value={statusFilter} onChange={handleStatusFilter} style={{ maxWidth: 140 }}>
          <option value="active">进行中</option>
          <option value="pending">待办</option>
          <option value="completed">已完成</option>
          <option value="deleted">已删除</option>
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>共 {total} 项</span>
        <button className="btn btn-primary" onClick={() => setShowForm(f => !f)}>
          {showForm ? '取消' : '+ 新任务'}
        </button>
      </div>

      {/* New Task Form */}
      {showForm && (
        <TaskForm
          onCreated={() => { setShowForm(false); fetchTasks(); }}
          toast={toast}
          prefill={prefill}
        />
      )}

      {/* Table */}
      {loading && tasks.length === 0 ? (
        <div className="card">
          {[1, 2, 3, 4, 5].map(i => (
            <div className="skeleton skeleton-text" key={i} style={{ height: 44, marginBottom: 'var(--space-xs)' }} />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-text">暂无任务</div>
            <div className="empty-state-hint">点击「+ 新任务」添加第一个任务</div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                </th>
                <th>任务</th>
                <th>截止时间</th>
                <th>优先级</th>
                <th>重复</th>
                <th>状态</th>
                <th style={{ width: 180 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => {
                const overdueDays = t.status === 'pending' ? getOverdueDays(t.due_time) : 0;
                let rowStyle = {};
                if (overdueDays >= 7) {
                  rowStyle = { borderLeft: '3px solid #ff3b30' };
                } else if (overdueDays >= 2) {
                  rowStyle = { borderLeft: '3px solid #ff9500' };
                } else if (overdueDays >= 1) {
                  rowStyle = { borderLeft: '3px solid #ffcc00' };
                }
                return (
                <tr key={t.task_id} style={{
                  background: selectedIds.has(t.task_id) ? 'rgba(10,132,255,0.06)' : undefined,
                  ...rowStyle,
                  ...(justCompleted === t.task_id ? {
                    opacity: 0.4,
                    textDecoration: 'line-through',
                    transition: 'opacity 0.5s ease, text-decoration 0.3s',
                  } : {}),
                }}>
                  <td>
                    <input type="checkbox" checked={selectedIds.has(t.task_id)} onChange={() => toggleSelect(t.task_id)} />
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>
                      {t.task_name}
                      {overdueDays >= 7 && (
                        <span style={{ background: '#ff3b30', color: '#fff', padding: '1px 6px', borderRadius: 4, fontSize: '0.65rem', marginLeft: 4 }}>
                          严重逾期
                        </span>
                      )}
                      {overdueDays >= 2 && overdueDays < 7 && (
                        <span style={{ color: '#ff9500', marginLeft: 4, fontSize: '0.75rem' }}>!</span>
                      )}
                    </div>
                    {t.description && (
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                        {t.description.length > 60 ? t.description.slice(0, 60) + '...' : t.description}
                      </div>
                    )}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>{formatTimeShort(t.due_time)}</td>
                  <td>
                    <span className={`badge badge-${PRIORITY_COLORS[t.priority] || 'pending'}`}>
                      {PRIORITY_MAP[t.priority] || '中'}
                    </span>
                  </td>
                  <td>{RECURRENCE_MAP[t.recurrence] || t.recurrence}</td>
                  <td>
                    <span className={`badge badge-${badgeClass(t.status)}`}>{statusLabel(t.status)}</span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                      <button className="btn btn-sm btn-ghost" onClick={() => openDetail(t)}>详情</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => onCreateNoteFromTask?.(t)}>记笔记</button>
                      {t.status === 'pending' && (
                        <button className="btn btn-sm btn-success" onClick={() => handleComplete(t.task_id)}>完成</button>
                      )}
                      {t.status !== 'deleted' && (
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(t.task_id)}>删除</button>
                      )}
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>&laquo;</button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter(p => Math.abs(p - page) < 4 || p === 1 || p === totalPages)
            .map((p, i, arr) => (
              <span key={p} style={{ display: 'inline-flex', alignItems: 'center' }}>
                {i > 0 && arr[i - 1] !== p - 1 && <span style={{ padding: '0 4px', color: 'var(--text-tertiary)' }}>...</span>}
                <button className={p === page ? 'active' : ''} onClick={() => setPage(p)}>{p}</button>
              </span>
            ))
          }
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>&raquo;</button>
        </div>
      )}

      {/* Floating batch action bar */}
      {selectedIds.size > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--space-sm)',
          padding: 'var(--space-sm) var(--space-lg)',
          background: 'var(--bg-card)', borderTop: '1px solid var(--border)',
          boxShadow: '0 -2px 12px rgba(0,0,0,0.12)',
        }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>已选 {selectedIds.size} 项</span>
          <button className="btn btn-sm btn-success" onClick={handleBatchComplete}>批量完成</button>
          <button className="btn btn-sm btn-danger" onClick={handleBatchDelete}>批量删除</button>
          <button className="btn btn-sm btn-ghost" onClick={clearSelection}>取消选择</button>
        </div>
      )}

      {resolvedDetailTask && (
        <TaskDetailDrawer
          task={resolvedDetailTask}
          relatedNotes={relatedNotes}
          notesLoading={notesLoading}
          onClose={() => setDetailTask(null)}
          onComplete={resolvedDetailTask.status === 'pending' ? async () => {
            await handleComplete(resolvedDetailTask.task_id);
            setDetailTask(null);
          } : null}
          onCreateNote={() => onCreateNoteFromTask?.(resolvedDetailTask)}
          onUpdated={async () => {
            await fetchTasks();
            await loadDetailBundle(resolvedDetailTask);
          }}
          subtasks={subtasks}
          subtasksLoading={subtasksLoading}
          onSubtasksUpdated={() => loadDetailBundle(resolvedDetailTask)}
          activePomodoro={activePomodoro}
          onPomodoroUpdated={fetchPomodoroStatus}
          weekContext={weekContext}
        />
      )}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '72px 1fr', gap: 'var(--space-sm)', fontSize: '0.84rem' }}>
      <div style={{ color: 'var(--text-tertiary)' }}>{label}</div>
      <div style={{ color: 'var(--text-primary)', minWidth: 0 }}>{value || '-'}</div>
    </div>
  );
}

function TaskDetailDrawer({
  task,
  relatedNotes,
  notesLoading,
  onClose,
  onComplete,
  onCreateNote,
  onUpdated,
  subtasks,
  subtasksLoading,
  onSubtasksUpdated,
  activePomodoro,
  onPomodoroUpdated,
  weekContext,
}) {
  const { loading, request } = useApi();
  const toast = useToast();
  const { notifyDataChange } = useApp();
  const [editMode, setEditMode] = useState(false);
  const [newSubtask, setNewSubtask] = useState('');
  const [form, setForm] = useState({
    task_name: task.task_name || '',
    due_time: task.due_time ? task.due_time.slice(0, 16) : '',
    start_time: task.start_time ? task.start_time.slice(0, 16) : '',
    end_time: task.end_time ? task.end_time.slice(0, 16) : '',
    description: task.description || '',
    estimated_minutes: task.estimated_minutes || '',
    tags: (task.tags || []).join(', '),
  });

  useEffect(() => {
    setForm({
      task_name: task.task_name || '',
      due_time: task.due_time ? task.due_time.slice(0, 16) : '',
      start_time: task.start_time ? task.start_time.slice(0, 16) : '',
      end_time: task.end_time ? task.end_time.slice(0, 16) : '',
      description: task.description || '',
      estimated_minutes: task.estimated_minutes || '',
      tags: (task.tags || []).join(', '),
    });
    setEditMode(false);
  }, [task]);

  const saveTask = async () => {
    try {
      const payload = {
        task_name: form.task_name.trim(),
        due_time: form.due_time ? new Date(form.due_time).toISOString() : undefined,
        start_time: form.start_time ? new Date(form.start_time).toISOString() : undefined,
        end_time: form.end_time ? new Date(form.end_time).toISOString() : undefined,
        description: form.description,
        estimated_minutes: form.estimated_minutes ? Number(form.estimated_minutes) : undefined,
        tags: form.tags ? form.tags.split(',').map(item => item.trim()).filter(Boolean) : [],
      };
      const res = await request(async () => fetch(`/api/task/${task.task_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message);
      toast('任务已更新', 'success');
      setEditMode(false);
      await onUpdated?.();
      await onPomodoroUpdated?.();
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const createSubtask = async () => {
    if (!newSubtask.trim()) return;
    try {
      const res = await request(async () => fetch('/api/advanced/subtasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: task.task_id, name: newSubtask.trim() }),
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '创建子任务失败');
      setNewSubtask('');
      await onSubtasksUpdated?.();
      await onUpdated?.();
      toast('子任务已添加', 'success');
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const toggleSubtask = async (subtask) => {
    try {
      const nextStatus = subtask.status === 'completed' ? 'pending' : 'completed';
      const res = await request(async () => fetch(`/api/advanced/subtasks/${subtask.subtask_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subtask_id: subtask.subtask_id, status: nextStatus }),
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '更新子任务失败');
      await onSubtasksUpdated?.();
      await onUpdated?.();
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const startPomodoro = async (durationMinutes = 25) => {
    try {
      const res = await request(async () => fetch('/api/advanced/pomodoro/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: task.task_id, duration_minutes: durationMinutes }),
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '启动番茄钟失败');
      await onPomodoroUpdated?.();
      toast('番茄钟已开始', 'success');
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const completePomodoro = async () => {
    try {
      const res = await request(async () => fetch('/api/advanced/pomodoro/complete', {
        method: 'POST',
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '完成番茄钟失败');
      await onPomodoroUpdated?.();
      toast('番茄钟已完成', 'success');
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const interruptPomodoro = async () => {
    try {
      const res = await request(async () => fetch('/api/advanced/pomodoro/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activePomodoro?.session_id || '', reason: 'manual_stop' }),
      }).then(r => r.json()));
      if (res.status === 'error') throw new Error(res.message || '中断番茄钟失败');
      await onPomodoroUpdated?.();
      toast('番茄钟已中断', 'success');
      notifyDataChange();
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const weeklyNeighbors = (weekContext || []).filter(item => item.task_id !== task.task_id).slice(0, 5);
  const pomodoroBoundToCurrent = activePomodoro?.task_id === task.task_id;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        style={{ width: 520, maxWidth: '92vw', maxHeight: '84vh', overflow: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>任务详情</div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{task.task_name}</h2>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose}>✕</button>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-xs)', flexWrap: 'wrap', marginBottom: 'var(--space-md)' }}>
          <span className={`badge badge-${badgeClass(task.status)}`}>{statusLabel(task.status)}</span>
          <span className={`badge badge-${PRIORITY_COLORS[task.priority] || 'pending'}`}>{PRIORITY_MAP[task.priority] || '中'}</span>
          <span className="badge badge-pending">{RECURRENCE_MAP[task.recurrence] || task.recurrence}</span>
        </div>

        <div className="card" style={{ marginBottom: 'var(--space-md)', background: 'var(--bg-secondary)' }}>
          {editMode ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              <input value={form.task_name} onChange={e => setForm(f => ({ ...f, task_name: e.target.value }))} />
              <input type="datetime-local" value={form.start_time} onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))} />
              <input type="datetime-local" value={form.end_time} onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))} />
              <input type="datetime-local" value={form.due_time} onChange={e => setForm(f => ({ ...f, due_time: e.target.value }))} />
              <input
                type="number"
                min="1"
                value={form.estimated_minutes}
                onChange={e => setForm(f => ({ ...f, estimated_minutes: e.target.value }))}
                placeholder="预估分钟"
              />
              <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="标签，逗号分隔" />
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={4} />
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              <InfoRow label="开始" value={task.start_time ? formatTimeShort(task.start_time) : '未安排'} />
              <InfoRow label="截止" value={task.due_time ? formatTimeShort(task.due_time) : '未设置'} />
              <InfoRow label="结束" value={task.end_time ? formatTimeShort(task.end_time) : '未设置'} />
              <InfoRow label="预估" value={task.estimated_minutes ? `${task.estimated_minutes} 分钟` : '未设置'} />
              <InfoRow label="标签" value={task.tags?.length ? task.tags.join(' / ') : '无'} />
            </div>
          )}
        </div>

        <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)', marginBottom: 'var(--space-sm)' }}>任务说明</div>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            {task.description || '暂无描述'}
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)' }}>关联笔记</div>
            <button className="btn btn-sm btn-ghost" onClick={onCreateNote}>+ 新建记录</button>
          </div>
          {notesLoading ? (
            <div className="skeleton skeleton-text" style={{ height: 48 }} />
          ) : relatedNotes.length === 0 ? (
            <div style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)' }}>暂无关联笔记</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {relatedNotes.map(note => (
                <div key={note.note_id} style={{ padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)' }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{note.title}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {note.content ? `${note.content.slice(0, 120)}${note.content.length > 120 ? '...' : ''}` : '(空)'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ marginTop: 'var(--space-md)' }}>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)', marginBottom: 'var(--space-sm)' }}>子任务</div>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
            <input
              value={newSubtask}
              onChange={e => setNewSubtask(e.target.value)}
              placeholder="添加一个可执行步骤"
            />
            <button className="btn btn-sm btn-primary" onClick={createSubtask} disabled={loading}>添加</button>
          </div>
          {subtasksLoading ? (
            <div className="skeleton skeleton-text" style={{ height: 48 }} />
          ) : subtasks.length === 0 ? (
            <div style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)' }}>暂无子任务</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
              {subtasks.map(subtask => (
                <label key={subtask.subtask_id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', padding: 'var(--space-xs) 0' }}>
                  <input
                    type="checkbox"
                    checked={subtask.status === 'completed'}
                    onChange={() => toggleSubtask(subtask)}
                  />
                  <span style={{
                    fontSize: '0.84rem',
                    textDecoration: subtask.status === 'completed' ? 'line-through' : 'none',
                    color: subtask.status === 'completed' ? 'var(--text-tertiary)' : 'var(--text-primary)',
                  }}>
                    {subtask.name}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ marginTop: 'var(--space-md)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)' }}>番茄钟</div>
            {activePomodoro ? (
              <span className={`badge badge-${pomodoroBoundToCurrent ? 'completed' : 'pending'}`}>
                {pomodoroBoundToCurrent ? '当前任务进行中' : '其他任务进行中'}
              </span>
            ) : (
              <span className="badge badge-pending">空闲</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
            {!activePomodoro && (
              <>
                <button className="btn btn-sm btn-primary" onClick={() => startPomodoro(25)}>25 分钟</button>
                <button className="btn btn-sm btn-ghost" onClick={() => startPomodoro(50)}>50 分钟</button>
              </>
            )}
            {activePomodoro && pomodoroBoundToCurrent && (
              <>
                <button className="btn btn-sm btn-primary" onClick={completePomodoro}>完成专注</button>
                <button className="btn btn-sm btn-ghost" onClick={interruptPomodoro}>中断</button>
              </>
            )}
          </div>
        </div>

        <div className="card" style={{ marginTop: 'var(--space-md)' }}>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)', marginBottom: 'var(--space-sm)' }}>本周上下文</div>
          {weeklyNeighbors.length === 0 ? (
            <div style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)' }}>本周没有其他任务</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {weeklyNeighbors.map(item => (
                <div key={item.task_id} style={{ padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)' }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.task_name}</div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                        {item.start_time ? formatTimeShort(item.start_time) : formatTimeShort(item.due_time)}
                      </div>
                    </div>
                    <span className={`badge badge-${badgeClass(item.status)}`}>{statusLabel(item.status)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          <button className="btn btn-ghost" onClick={() => setEditMode(v => !v)}>{editMode ? '取消编辑' : '编辑'}</button>
          <button className="btn btn-ghost" onClick={onCreateNote}>记笔记</button>
          {editMode ? (
            <button className="btn btn-primary" disabled={loading} onClick={saveTask}>{loading ? '保存中...' : '保存'}</button>
          ) : (
            onComplete && <button className="btn btn-primary" onClick={onComplete}>完成任务</button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Task Form ────────────────────────────────────────── */

function TaskForm({ onCreated, toast, prefill = null }) {
  const { loading, request } = useApi();
  const { notifyDataChange } = useApp();
  const [form, setForm] = useState({
    task_name: '', due_time: '', start_time: '', end_time: '',
    recurrence: 'once', priority: 2, description: '',
    estimated_minutes: '', tags: '',
  });

  useEffect(() => {
    if (!prefill?.date) return;
    const due = `${prefill.date}T18:00`;
    const start = `${prefill.date}T09:00`;
    setForm(f => ({
      ...f,
      due_time: f.due_time || due,
      start_time: f.start_time || start,
    }));
  }, [prefill]);

  const update = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.task_name.trim()) { toast('请输入任务名称', 'error'); return; }
    let dueTime = form.due_time ? new Date(form.due_time).toISOString() :
                  form.end_time ? new Date(form.end_time).toISOString() : null;
    if (!dueTime) { toast('请选择截止时间', 'error'); return; }
    try {
      const res = await request(async () => apiPost('/api/task', {
        action: 'add_task',
        task_name: form.task_name.trim(),
        due_time: dueTime,
        start_time: form.start_time ? new Date(form.start_time).toISOString() : undefined,
        end_time: form.end_time ? new Date(form.end_time).toISOString() : undefined,
        recurrence: form.recurrence,
        priority: Number(form.priority),
        description: form.description || undefined,
        estimated_minutes: form.estimated_minutes ? Number(form.estimated_minutes) : undefined,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
      }));
      if (res.status === 'error') throw new Error(res.message);
      toast('任务创建成功', 'success');
      notifyDataChange();
      onCreated();
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
      <h3 style={{ marginBottom: 'var(--space-md)', fontSize: '0.95rem' }}>新建任务</h3>
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
          <div className="form-group">
            <label>任务名称 *</label>
            <input value={form.task_name} onChange={e => update('task_name', e.target.value)} placeholder="输入任务名称" />
          </div>
          <div className="form-group">
            <label>截止时间 *</label>
            <input type="datetime-local" value={form.due_time} onChange={e => update('due_time', e.target.value)} />
          </div>
          <div className="form-group">
            <label>开始时间</label>
            <input type="datetime-local" value={form.start_time} onChange={e => update('start_time', e.target.value)} />
          </div>
          <div className="form-group">
            <label>结束时间</label>
            <input type="datetime-local" value={form.end_time} onChange={e => update('end_time', e.target.value)} />
          </div>
          <div className="form-group">
            <label>重复</label>
            <select value={form.recurrence} onChange={e => update('recurrence', e.target.value)}>
              {Object.entries(RECURRENCE_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>优先级</label>
            <select value={form.priority} onChange={e => update('priority', e.target.value)}>
              {Object.entries(PRIORITY_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ gridColumn: '1 / -1' }}>
            <label>描述</label>
            <textarea value={form.description} onChange={e => update('description', e.target.value)} placeholder="任务描述（可选）" rows={2} />
          </div>
          <div className="form-group">
            <label>预估时间（分钟）</label>
            <input type="number" min="1" value={form.estimated_minutes} onChange={e => update('estimated_minutes', e.target.value)} placeholder="如 30" />
          </div>
          <div className="form-group">
            <label>标签（逗号分隔）</label>
            <input value={form.tags} onChange={e => update('tags', e.target.value)} placeholder="如 学习, 工作" />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? '创建中...' : '创建任务'}</button>
        </div>
      </form>
    </div>
  );
}
