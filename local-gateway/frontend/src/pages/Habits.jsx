import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';

const FREQUENCY_MAP = { daily: '每天', weekly: '每周', monthly: '每月' };
const HABIT_COLORS = ['#27ae60', '#0a84ff', '#ff9f0a', '#ff453a', '#af52de', '#5ac8fa', '#ff6b6b', '#30d158'];

export default function Habits() {
  const { loading, request } = useApi();
  const toast = useToast();
  const [habits, setHabits] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '', description: '', frequency: 'daily', target_count: 1, reminder_time: '', color: '#27ae60',
  });

  const fetchHabits = useCallback(async () => {
    try {
      const res = await request(async () => apiGet('/api/habits'));
      if (res.status === 'error') throw new Error(res.message);
      setHabits(res.habits || []);
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [request, toast]);

  useEffect(() => { fetchHabits(); }, [fetchHabits]);

  const resetForm = () => {
    setForm({ name: '', description: '', frequency: 'daily', target_count: 1, reminder_time: '', color: '#27ae60' });
    setShowForm(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast('请输入习惯名称', 'error'); return; }
    try {
      const res = await request(async () =>
        apiPost('/api/habits', {
          name: form.name.trim(),
          description: form.description,
          frequency: form.frequency,
          target_count: Number(form.target_count),
          reminder_time: form.reminder_time || null,
          color: form.color,
        })
      );
      if (res.status === 'error') throw new Error(res.message);
      toast('习惯已创建', 'success');
      resetForm();
      fetchHabits();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleCheckin = async (habitId) => {
    try {
      const res = await apiPost(`/api/habits/${habitId}/checkin`, { count: 1, note: '' });
      if (res.status === 'error') throw new Error(res.message);
      toast('打卡成功!', 'success');
      fetchHabits();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleDelete = async (habitId) => {
    if (!confirm('确认删除此习惯?')) return;
    try {
      const res = await fetch(`/api/habits/${habitId}`, { method: 'DELETE' }).then(r => r.json());
      if (res.status === 'error') throw new Error(res.message);
      toast('习惯已删除', 'success');
      fetchHabits();
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)' }}>
        <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          共 {habits.length} 个习惯
        </span>
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={() => setShowForm(f => !f)}>
          {showForm ? '取消' : '+ 新习惯'}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 'var(--space-md)' }}>
          <h3 style={{ marginBottom: 'var(--space-md)', fontSize: '0.95rem' }}>新建习惯</h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              <div className="form-group">
                <label>习惯名称 *</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如 晨跑" />
              </div>
              <div className="form-group">
                <label>频率</label>
                <select value={form.frequency} onChange={e => setForm(f => ({ ...f, frequency: e.target.value }))}>
                  {Object.entries(FREQUENCY_MAP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>目标次数</label>
                <input type="number" min="1" value={form.target_count} onChange={e => setForm(f => ({ ...f, target_count: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>提醒时间</label>
                <input type="time" value={form.reminder_time} onChange={e => setForm(f => ({ ...f, reminder_time: e.target.value }))} />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>描述</label>
                <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="习惯描述（可选）" rows={2} />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>颜色</label>
                <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
                  {HABIT_COLORS.map(c => (
                    <button
                      key={c} type="button"
                      onClick={() => setForm(f => ({ ...f, color: c }))}
                      style={{
                        width: 32, height: 32, borderRadius: '50%', border: form.color === c ? '3px solid var(--text-primary)' : '2px solid var(--border)',
                        background: c, cursor: 'pointer', transition: 'all 0.15s',
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? '创建中...' : '创建习惯'}</button>
            </div>
          </form>
        </div>
      )}

      {/* Habit Cards */}
      {loading && habits.length === 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 'var(--space-md)' }}>
          {[1, 2, 3].map(i => (
            <div className="card" key={i}>
              <div className="skeleton skeleton-text" style={{ width: '50%' }} />
              <div className="skeleton skeleton-text" style={{ width: '80%', height: 60 }} />
            </div>
          ))}
        </div>
      ) : habits.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">🎯</div>
            <div className="empty-state-text">暂无习惯</div>
            <div className="empty-state-hint">点击「+ 新习惯」开始养成好习惯</div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 'var(--space-md)' }}>
          {habits.map(habit => (
            <div className="card" key={habit.habit_id} style={{ borderLeft: `4px solid ${habit.color || '#27ae60'}` }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{habit.name}</h3>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                    {FREQUENCY_MAP[habit.frequency] || habit.frequency}
                    {habit.target_count > 1 ? ` ${habit.target_count}次` : ''}
                  </span>
                </div>
                <button className="btn btn-sm btn-danger" onClick={() => handleDelete(habit.habit_id)} title="删除">🗑️</button>
              </div>

              {habit.description && (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>
                  {habit.description}
                </div>
              )}

              {/* Streak */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                padding: 'var(--space-sm)', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-tertiary)', marginBottom: 'var(--space-sm)',
              }}>
                <span style={{ fontSize: '1.3rem' }}>🔥</span>
                <div>
                  <span style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--warning)' }}>
                    {habit.streak ?? 0}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginLeft: 4 }}>天连续</span>
                </div>
              </div>

              {/* Check-in */}
              <button
                className="btn btn-success"
                style={{ width: '100%' }}
                onClick={() => handleCheckin(habit.habit_id)}
              >
                ✅ 打卡
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
