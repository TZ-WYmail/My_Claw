import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { formatTimeShort } from '../utils/format';

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

export default function Calendar() {
  const { loading, request } = useApi();
  const toast = useToast();

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-based
  const [days, setDays] = useState([]);
  const [modalDay, setModalDay] = useState(null); // { date, events, tasks }
  const [showAddEvent, setShowAddEvent] = useState(false);
  const [eventForm, setEventForm] = useState({
    title: '', description: '', start_time: '', end_time: '', event_type: 'personal', color: '#0a84ff',
  });

  const fetchCalendar = useCallback(async () => {
    try {
      const res = await request(async () => apiGet(`/api/advanced/calendar/view?year=${year}&month=${month}`));
      if (res.status === 'error') throw new Error(res.message);
      setDays(res.days || []);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast, year, month]);

  const fetchEventsForDay = useCallback(async (dateStr) => {
    try {
      const res = await apiGet(`/api/advanced/calendar/events?start_date=${dateStr}&end_date=${dateStr}`);
      return res.events || [];
    } catch {
      return [];
    }
  }, []);

  useEffect(() => { fetchCalendar(); }, [fetchCalendar]);

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
    } catch (e) { toast(e.message, 'error'); }
  };

  // Build grid: pad first week so Monday=0 alignment
  const firstDayWeekday = days.length > 0 ? days[0].weekday : 0;
  const padStart = Array.from({ length: firstDayWeekday }, () => null);
  const gridDays = [...padStart, ...days];

  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  return (
    <div>
      {/* Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <button className="btn btn-sm" onClick={prevMonth}>&larr;</button>
        <button className="btn btn-sm btn-primary" onClick={goToday}>今天</button>
        <button className="btn btn-sm" onClick={nextMonth}>&rarr;</button>
        <span style={{ fontSize: '1.1rem', fontWeight: 600, marginLeft: 'var(--space-sm)' }}>
          {year}年{month}月
        </span>
      </div>

      {/* Calendar Grid */}
      <div className="card" style={{ padding: 'var(--space-md)' }}>
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
                      minHeight: 80, padding: 6, borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer', position: 'relative',
                      background: isToday ? 'rgba(10,132,255,0.08)' : 'transparent',
                      border: isToday ? '1px solid var(--accent)' : '1px solid transparent',
                      opacity: day.is_current_month ? 1 : 0.35,
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (!isToday) e.currentTarget.style.background = 'var(--bg-tertiary)'; }}
                    onMouseLeave={e => { if (!isToday) e.currentTarget.style.background = 'transparent'; }}
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
      </div>

      {/* Day Modal */}
      {modalDay && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" style={{ minWidth: 400, maxWidth: 520, maxHeight: '80vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-md)' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{modalDay.date}</h2>
              <button className="btn btn-sm btn-ghost" onClick={closeModal}>✕</button>
            </div>

            {/* Tasks in this day */}
            {modalDay.tasks && modalDay.tasks.length > 0 && (
              <div style={{ marginBottom: 'var(--space-md)' }}>
                <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>📋 任务</h3>
                {modalDay.tasks.map(t => (
                  <div key={t.task_id} style={{
                    padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-tertiary)', marginBottom: 4,
                    fontSize: '0.85rem',
                  }}>
                    {t.task_name}
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginLeft: 8 }}>
                      {formatTimeShort(t.due_time)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Events in this day */}
            <div style={{ marginBottom: 'var(--space-md)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                <h3 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>📅 事件</h3>
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
