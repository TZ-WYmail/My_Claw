import { useState, useEffect, useCallback } from 'react';
import { useApi, apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { frequencyLabel } from '../utils/format';
import { normalizeList } from '../utils/normalize';
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
      setHabits(normalizeList(res, ['habits', 'items']));
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

  const streakTotal = habits.reduce((sum, habit) => sum + (habit.streak || 0), 0);
  const reminderCount = habits.filter(habit => habit.reminder_time).length;

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 09 / Training Track</div>
          <h1 className="atlas-chapter-title">习惯页应该像训练轨迹板，先看单位、连击和提醒，再决定今天要推进哪条。</h1>
          <div className="atlas-chapter-copy">
            习惯不是一组静态说明卡，而是一组长期培养单元。你应该先看到哪些单位有连击、哪些带提醒、哪些还没有形成节奏，然后立即打卡或调整。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">养成顺序</div>
          <div className="atlas-chapter-note-copy">先定频率和目标，再确认提醒，最后用连续打卡维持节奏。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">TRAINING DECK</span>
            <h1 className="mission-title">把习惯区做成养成甲板，而不是几张静态说明卡。</h1>
            <div className="mission-copy">
              每个习惯都应该像一个可培养单位：有频率、有连续天数、有提醒窗口，也有马上执行的打卡动作。这里的重点是推进节奏，不是摆数据。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{habits.length} 个习惯</span>
              <span className="badge badge-completed">{reminderCount} 个带提醒</span>
              <span className="badge badge-warning">{streakTotal} 天累计连击</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">养成规则</div>
            <div className="mission-sidecard-copy">
              不追求面面俱到。优先让每个习惯有清晰目标、可见连续性和一键打卡的反馈回路。
            </div>
          </div>
        </div>
      </section>

      <div className="atlas-toolbar">
        <span className="atlas-toolbar-label">共 {habits.length} 个习惯</span>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-primary" onClick={() => setShowForm(f => !f)}>
          {showForm ? '取消' : '+ 新习惯'}
        </button>
      </div>

      {showForm && (
        <section className="board-lane atlas-ledger-lane">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">RECRUIT</div>
              <h3 className="board-lane-title">新建习惯</h3>
              <div className="board-lane-copy">把频率、目标次数、提醒和颜色一次配好，后面只需要持续推进。</div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="command-form">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              <div className="form-group">
                <label>习惯名称 *</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如 晨跑" />
              </div>
              <div className="form-group">
                <label>频率</label>
                <select value={form.frequency} onChange={e => setForm(f => ({ ...f, frequency: e.target.value }))}>
                  {['daily', 'weekly', 'monthly'].map((value) => <option key={value} value={value}>{frequencyLabel(value)}</option>)}
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
                <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="习惯描述（可选）" rows={3} />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>颜色</label>
                <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
                  {HABIT_COLORS.map(c => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setForm(f => ({ ...f, color: c }))}
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: '50%',
                        border: form.color === c ? '3px solid var(--text-primary)' : '2px solid var(--border)',
                        background: c,
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>取消</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>{loading ? '创建中...' : '创建习惯'}</button>
            </div>
          </form>
        </section>
      )}

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">训练单元</div>
          <div className="board-summary-value">{habits.length}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">提醒就绪</div>
          <div className="board-summary-value">{reminderCount}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">累计连击</div>
          <div className="board-summary-value">{streakTotal}</div>
        </div>
      </div>

      {loading && habits.length === 0 ? (
        <div className="board-card-grid">
          {[1, 2, 3].map(i => (
            <div className="dossier-card" key={i}>
              <div className="skeleton skeleton-text" style={{ width: '50%' }} />
              <div className="skeleton skeleton-text" style={{ width: '80%', height: 60 }} />
            </div>
          ))}
        </div>
      ) : habits.length === 0 ? (
        <section className="board-lane">
          <div className="empty-state">
            <div className="empty-state-icon">🎯</div>
            <div className="empty-state-text">暂无习惯</div>
            <div className="empty-state-hint">点击「+ 新习惯」开始养成好习惯</div>
          </div>
        </section>
      ) : (
        <section className="board-lane atlas-paper-stack">
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">UNITS</div>
              <h3 className="board-lane-title">养成甲板</h3>
              <div className="board-lane-copy">每个习惯是一张训练单位卡：说明目标、提醒、连击和立即打卡入口。</div>
            </div>
          </div>

          <div className="board-card-grid">
            {habits.map(habit => (
              <div
                className="dossier-card"
                key={habit.habit_id}
                style={{
                  borderTop: `5px solid ${habit.color || '#27ae60'}`,
                  transform: `rotate(${habit.streak > 0 ? '-0.8deg' : '0.8deg'})`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                  <div>
                    <div className="section-kicker">HABIT UNIT</div>
                    <h3 className="dossier-title">{habit.name}</h3>
                  </div>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(habit.habit_id)}>删除</button>
                </div>

                {habit.description && (
                  <div className="dossier-copy">{habit.description}</div>
                )}

                <div className="dossier-meta-grid">
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">频率</div>
                    <div>{frequencyLabel(habit.frequency)}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">目标</div>
                    <div>{habit.target_count > 1 ? `${habit.target_count} 次` : '1 次'}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">提醒</div>
                    <div>{habit.reminder_time || '未设置'}</div>
                  </div>
                  <div className="dossier-meta-box">
                    <div className="dossier-meta-label">连击</div>
                    <div>{habit.streak ?? 0} 天</div>
                  </div>
                </div>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  padding: 'var(--space-sm)',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(255,255,255,0.34)',
                }}>
                  <span style={{ fontSize: '1.3rem' }}>🔥</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '1.08rem', color: 'var(--warning)' }}>{habit.streak ?? 0}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>连续推进天数</div>
                  </div>
                </div>

                <div className="dossier-actions">
                  <button
                    className="btn btn-success"
                    style={{ width: '100%', justifyContent: 'center' }}
                    onClick={() => handleCheckin(habit.habit_id)}
                  >
                    打卡
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
