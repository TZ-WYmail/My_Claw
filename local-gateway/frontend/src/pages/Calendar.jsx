import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { useApp } from '../contexts/AppContext';
import { formatTimeShort } from '../utils/format';
import { normalizeList } from '../utils/normalize';

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

export default function Calendar({ onCreateTaskForDate, onCreateNoteFromTask, onOpenTasks }) {
  const { loading, request } = useApi();
  const toast = useToast();
  const { refreshToken, notifyDataChange } = useApp();

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-based
  const [days, setDays] = useState([]);
  const [modalDay, setModalDay] = useState(null); // { date, events, tasks }
  const [showAddEvent, setShowAddEvent] = useState(false);
  const [activePomodoro, setActivePomodoro] = useState(null);
  const [eventForm, setEventForm] = useState({
    title: '', description: '', start_time: '', end_time: '', event_type: 'personal', color: '#0a84ff',
  });

  const fetchCalendar = useCallback(async () => {
    try {
      const res = await request(async () => apiGet(`/api/advanced/calendar/view?year=${year}&month=${month}`));
      if (res.status === 'error') throw new Error(res.message);
      setDays(normalizeList(res, ['days', 'items']));
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, year, month]);

  const fetchEventsForDay = useCallback(async (dateStr) => {
    try {
      const res = await apiGet(`/api/advanced/calendar/events?start_date=${dateStr}&end_date=${dateStr}`);
      return normalizeList(res, ['events', 'items']);
    } catch {
      return [];
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

  useEffect(() => {
    fetchCalendar();
    fetchPomodoroStatus();
  }, [fetchCalendar, fetchPomodoroStatus, refreshToken]);

  const prevMonth = () => {
    if (month === 1) { setYear(y => y - 1); setMonth(12); }
    else { setMonth(m => m - 1); }
  };

  const nextMonth = () => {
    if (month === 12) { setYear(y => y + 1); setMonth(1); }
    else { setMonth(m => m + 1); }
  };

  const goToday = () => {
    const n = new Date();
    setYear(n.getFullYear());
    setMonth(n.getMonth() + 1);
  };

  const openDay = async (day) => {
    const events = day.events && day.events.length > 0
      ? day.events
      : await fetchEventsForDay(day.date);
    setModalDay({ ...day, events });
    setShowAddEvent(false);
  };

  const closeModal = () => { setModalDay(null); setShowAddEvent(false); };

  const handleAddEvent = async (e) => {
    e.preventDefault();
    if (!eventForm.title.trim()) { toast('请输入事件标题', 'error'); return; }
    if (!eventForm.start_time || !eventForm.end_time) { toast('请设置起止时间', 'error'); return; }
    try {
      const res = await request(async () =>
        apiPost('/api/advanced/calendar/events', {
          title: eventForm.title.trim(),
          description: eventForm.description,
          start_time: new Date(eventForm.start_time).toISOString(),
          end_time: new Date(eventForm.end_time).toISOString(),
          event_type: eventForm.event_type,
          color: eventForm.color,
        })
      );
      if (res.status === 'error') throw new Error(res.message);
      toast('事件已创建', 'success');
      setEventForm({ title: '', description: '', start_time: '', end_time: '', event_type: 'personal', color: '#0a84ff' });
      setShowAddEvent(false);
      fetchCalendar();
      if (modalDay) {
        const events = await fetchEventsForDay(modalDay.date);
        setModalDay(d => ({ ...d, events }));
      }
      notifyDataChange();
    } catch (err) { toast(err.message, 'error'); }
  };

  const handleDeleteEvent = async (eventId) => {
    if (!confirm('确认删除此事件?')) return;
    try {
      const res = await fetch(`/api/advanced/calendar/events/${eventId}`, { method: 'DELETE' }).then(r => r.json());
      if (res.status === 'error') throw new Error(res.message);
      toast('事件已删除', 'success');
      fetchCalendar();
      if (modalDay) {
        const events = await fetchEventsForDay(modalDay.date);
        setModalDay(d => ({ ...d, events }));
      }
      notifyDataChange();
    } catch (e) { toast(e.message, 'error'); }
  };

  const startPomodoroForTask = async (task, durationMinutes = 25) => {
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
  };

  // Build grid: pad first week so Monday=0 alignment
  const firstDayWeekday = days.length > 0 ? days[0].weekday : 0;
  const padStart = Array.from({ length: firstDayWeekday }, () => null);
  const gridDays = [...padStart, ...days];

  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 03 / Monthly Map</div>
          <h1 className="atlas-chapter-title">日历页应该像一张月度地图，先看哪块地带拥挤，再决定去哪里落点。</h1>
          <div className="atlas-chapter-copy">
            日期格不是抽象格子，而是每天的任务地块。事件、任务、专注记录应该在地图上留下不同密度的标记，帮助你先判断压力，再打开单日档案。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">地图阅读法</div>
          <div className="atlas-chapter-note-copy">先看月份密度，再点单日卷宗，再补事件或安排同日任务。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">FIELD MAP</span>
            <h1 className="mission-title">日历页该像作战地图，而不是单纯月格。</h1>
            <div className="mission-copy">
              重点不是每一天画得多工整，而是让你迅速看出哪天有任务、哪天有事件、哪天正在专注，然后立刻落到当天处理。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{year}年{month}月</span>
              {activePomodoro && (
                <span className="badge badge-completed">{activePomodoro.duration_minutes} 分钟进行中</span>
              )}
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">导航提示</div>
            <div className="mission-sidecard-copy">
              先用月份导航确定战区，再点开具体日期查看任务、事件和专注动作。
            </div>
          </div>
        </div>
      </section>

      <div className="atlas-toolbar">
        <button className="btn btn-sm" onClick={prevMonth}>&larr;</button>
        <button className="btn btn-sm btn-primary" onClick={goToday}>今天</button>
        <button className="btn btn-sm" onClick={nextMonth}>&rarr;</button>
        <span className="atlas-toolbar-label" style={{ fontSize: '1.02rem', fontWeight: 600, marginLeft: 'var(--space-sm)' }}>
          {year}年{month}月
        </span>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-sm btn-ghost" onClick={() => onOpenTasks?.()}>看全部任务</button>
      </div>

      <section className="board-lane atlas-ledger-lane calendar-map-lane" style={{ padding: 'var(--space-md)' }}>
        {loading ? (
          <div className="skeleton" style={{ height: 400 }} />
        ) : (
          <>
            {/* Weekday headers */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, marginBottom: 4 }}>
              {WEEKDAYS.map(d => (
                <div key={d} style={{
                  textAlign: 'center', fontSize: '0.8rem', fontWeight: 600,
                  color: 'var(--text-tertiary)', padding: 'var(--space-xs)',
                }}>
                  {d}
                </div>
              ))}
            </div>
            {/* Day cells */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
              {gridDays.map((day, i) => {
                if (!day) return <div key={`pad-${i}`} style={{ minHeight: 80 }} />;
                const isToday = day.date === todayStr;
                const hasTasks = day.tasks && day.tasks.length > 0;
                const hasEvents = day.events && day.events.length > 0;
                const hasPomodoro = day.pomodoro_count > 0;

                return (
                  <div
                    key={day.date}
                    onClick={() => openDay(day)}
                    style={{
                      minHeight: 96, padding: 8, borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer', position: 'relative',
                      background: isToday ? 'rgba(198,83,61,0.1)' : 'rgba(255,255,255,0.18)',
                      border: isToday ? '1px solid var(--accent)' : '1px solid rgba(67, 42, 28, 0.08)',
                      opacity: day.is_current_month ? 1 : 0.35,
                      transition: 'background 0.15s, transform 0.15s',
                      boxShadow: isToday ? 'var(--shadow-sm)' : 'none',
                      transform: isToday ? 'rotate(-0.8deg)' : 'rotate(0.35deg)',
                    }}
                    onMouseEnter={e => {
                      if (!isToday) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.3)';
                        e.currentTarget.style.transform = 'translateY(-2px) rotate(-0.4deg)';
                      }
                    }}
                    onMouseLeave={e => {
                      if (!isToday) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.18)';
                        e.currentTarget.style.transform = 'rotate(0.35deg)';
                      }
                    }}
                  >
                    <div style={{
                      fontSize: '0.85rem', fontWeight: isToday ? 700 : 400,
                      color: isToday ? 'var(--accent)' : 'var(--text-primary)',
                      marginBottom: 2,
                    }}>
                      {day.date.split('-').pop()}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {hasTasks && (
                        <span style={{ fontSize: '0.65rem', color: 'var(--warning)' }}>
                          📋{day.tasks.length}
                        </span>
                      )}
                      {hasEvents && day.events.slice(0, 2).map(ev => (
                        <div key={ev.event_id} style={{
                          fontSize: '0.6rem', padding: '1px 4px', borderRadius: 2,
                          background: ev.color || 'var(--accent)', color: '#fff',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {ev.title}
                        </div>
                      ))}
                      {hasPomodoro && (
                        <span style={{ fontSize: '0.6rem', color: 'var(--success)' }}>
                          🍅{day.pomodoro_count}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </section>

      {modalDay && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" style={{ minWidth: 400, maxWidth: 560, maxHeight: '84vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-md)' }}>
              <div>
                <div className="section-kicker">DAY DOSSIER</div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{modalDay.date}</h2>
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => onCreateTaskForDate?.(modalDay.date)}
                >
                  + 任务
                </button>
                <button className="btn btn-sm btn-ghost" onClick={closeModal}>✕</button>
              </div>
            </div>

            {modalDay.tasks && modalDay.tasks.length > 0 && (
              <div className="board-lane" style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-md)' }}>
                <h3 className="board-lane-title" style={{ fontSize: '0.95rem', marginBottom: 'var(--space-sm)' }}>当日任务</h3>
                {modalDay.tasks.map(t => (
                  <div key={t.task_id} style={{
                    padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)',
                    background: 'rgba(255,255,255,0.28)', marginBottom: 6,
                    fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)',
                    alignItems: 'flex-start',
                  }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{t.task_name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                        开始：{t.start_time ? formatTimeShort(t.start_time) : '未安排'} · 截止：{t.due_time ? formatTimeShort(t.due_time) : '未设置'}
                      </div>
                      {t.description && (
                        <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                          {t.description.length > 90 ? `${t.description.slice(0, 90)}...` : t.description}
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-xs)', flexShrink: 0 }}>
                      <button className="btn btn-sm btn-ghost" onClick={() => startPomodoroForTask(t)}>专注</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => onCreateNoteFromTask?.(t)}>笔记</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => onCreateTaskForDate?.(modalDay.date)}>同日新建</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="board-lane" style={{ marginBottom: 'var(--space-md)', padding: 'var(--space-md)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                <h3 className="board-lane-title" style={{ fontSize: '0.95rem' }}>当日事件</h3>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => setShowAddEvent(s => !s)}
                >
                  {showAddEvent ? '取消' : '+ 添加'}
                </button>
              </div>

              {showAddEvent && (
                <form onSubmit={handleAddEvent} style={{ marginBottom: 'var(--space-sm)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                    <input
                      value={eventForm.title}
                      onChange={e => setEventForm(f => ({ ...f, title: e.target.value }))}
                      placeholder="事件标题"
                    />
                    <textarea
                      value={eventForm.description}
                      onChange={e => setEventForm(f => ({ ...f, description: e.target.value }))}
                      placeholder="描述（可选）"
                      rows={2}
                    />
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-sm)' }}>
                      <div className="form-group">
                        <label>开始</label>
                        <input
                          type="datetime-local"
                          value={eventForm.start_time}
                          onChange={e => setEventForm(f => ({ ...f, start_time: e.target.value }))}
                        />
                      </div>
                      <div className="form-group">
                        <label>结束</label>
                        <input
                          type="datetime-local"
                          value={eventForm.end_time}
                          onChange={e => setEventForm(f => ({ ...f, end_time: e.target.value }))}
                        />
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                      <select
                        value={eventForm.event_type}
                        onChange={e => setEventForm(f => ({ ...f, event_type: e.target.value }))}
                        style={{ flex: 1 }}
                      >
                        <option value="personal">个人</option>
                        <option value="work">工作</option>
                        <option value="study">学习</option>
                      </select>
                      <input
                        type="color"
                        value={eventForm.color}
                        onChange={e => setEventForm(f => ({ ...f, color: e.target.value }))}
                        style={{ width: 44, padding: 2, cursor: 'pointer' }}
                      />
                    </div>
                    <button type="submit" className="btn btn-primary btn-sm">创建事件</button>
                  </div>
                </form>
              )}

              {modalDay.events && modalDay.events.length > 0 ? (
                modalDay.events.map(ev => (
                  <div key={ev.event_id} style={{
                    display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                    padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-tertiary)', marginBottom: 4,
                  }}>
                    <div style={{
                      width: 6, height: 36, borderRadius: 3, flexShrink: 0,
                      background: ev.color || 'var(--accent)',
                    }} />
                    <div style={{ flex: 1, overflow: 'hidden' }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>{ev.title}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        {formatTimeShort(ev.start_time)} - {formatTimeShort(ev.end_time)}
                      </div>
                    </div>
                    <button className="btn btn-sm btn-ghost" onClick={() => handleDeleteEvent(ev.event_id)} title="删除">🗑️</button>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)', textAlign: 'center', padding: 'var(--space-md)' }}>
                  暂无事件
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
