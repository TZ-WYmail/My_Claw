import { useEffect, useMemo, useState, useCallback } from 'react';
import { useApi, apiGet, apiPost, apiPut } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { useApp } from '../contexts/AppContext';
import { formatTimeShort, operationIcon } from '../utils/format';
import { normalizeList } from '../utils/normalize';

function overdueDays(dueTime) {
  if (!dueTime) return 0;
  const due = new Date(dueTime);
  const now = new Date();
  return Math.max(0, Math.floor((now - due) / (1000 * 60 * 60 * 24)));
}

function isTaskToday(task, isoDate) {
  return (
    (task.start_time && task.start_time.startsWith(isoDate)) ||
    (task.due_time && task.due_time.startsWith(isoDate))
  );
}

function taskWindow(task) {
  if (task.start_time && task.end_time) {
    return `${formatTimeShort(task.start_time)} - ${formatTimeShort(task.end_time)}`;
  }
  if (task.start_time) return `开始 ${formatTimeShort(task.start_time)}`;
  if (task.due_time) return `截止 ${formatTimeShort(task.due_time)}`;
  return '未安排时间';
}

function progressText(progress) {
  if (progress >= 100) return '今日主线已清空，可以收尾或继续扩张。';
  if (progress >= 60) return '节奏已起来，优先把主线推到闭环。';
  if (progress >= 20) return '已经开局，但还有明显主线没有拿下。';
  return '今天还没真正进入推进状态，先拿下一项主线。';
}

function BattleHero({
  focusTask,
  nextSuggestedTask,
  activePomodoro,
  progress,
  streak,
  onCreateTask,
  onCreateNote,
  onOpenAi,
  onStartFocus,
  onCompleteFocus,
  onOpenTaskDetail,
}) {
  const heroTask = activePomodoro?.task_id === focusTask?.task_id ? focusTask : (nextSuggestedTask || focusTask);
  const risk = heroTask?.overdue ? `逾期 ${overdueDays(heroTask.due_time)} 天` : heroTask?.start_time ? '已在今日战线' : '尚未排时段';

  return (
    <section className="mission-masthead war-room-hero atlas-leaf">
      <div className="mission-masthead-grid">
        <div>
          <span className="section-kicker">TODAY WAR ROOM</span>
          <h1 className="mission-title">
            {heroTask ? `今天先拿下：${heroTask.task_name}` : '今天这一局，还没有主线任务'}
          </h1>
          <div className="mission-copy">
            {heroTask
              ? `当前主线时间窗：${taskWindow(heroTask)}。${progressText(progress)}`
              : '先创建或安排一项今天必须推进的任务。首页不该只是总览，而应该直接把你推入行动。'}
          </div>
          <div className="mission-chip-row">
            <span className="war-room-stamp">今日进度 {progress}%</span>
            <span className="war-room-stamp">连续 {streak.current_streak} 天</span>
            <span className={`war-room-stamp${heroTask?.overdue ? ' danger' : ''}`}>{risk}</span>
          </div>
          <div className="frontline-actions" style={{ marginTop: 'var(--space-md)' }}>
            {activePomodoro ? (
              <button className="btn btn-primary" onClick={onCompleteFocus}>完成当前专注</button>
            ) : heroTask ? (
              <button className="btn btn-primary" onClick={() => onStartFocus(heroTask)}>开始 25 分钟</button>
            ) : (
              <button className="btn btn-primary" onClick={onCreateTask}>创建主线任务</button>
            )}
            <button className="btn btn-ghost" onClick={() => onOpenAi?.({ intent: 'plan_today' })}>AI 重排今天</button>
            <button className="btn btn-ghost" onClick={onCreateNote}>新建记录</button>
            {heroTask && <button className="btn btn-ghost" onClick={() => onOpenTaskDetail?.(heroTask)}>查看主线详情</button>}
          </div>
        </div>

        <div className="mission-sidecard">
          <div className="mission-sidecard-title">战况总览</div>
          <div className="mission-sidecard-copy">
            {activePomodoro
              ? `专注已开启 ${activePomodoro.duration_minutes} 分钟，开始于 ${formatTimeShort(activePomodoro.start_time)}。`
              : heroTask
                ? `当前最值得立刻推进的是「${heroTask.task_name}」。先拿下一个可见结果，再切换。`
                : '今天还没有主线。先建立一条可执行战线，再让 AI 或日历辅助你排布。'}
          </div>
          <div className="mission-chip-row">
            {activePomodoro && <span className="badge badge-completed">专注进行中</span>}
            {heroTask?.estimated_minutes && <span className="badge badge-pending">预估 {heroTask.estimated_minutes} 分钟</span>}
            <span className="badge badge-warning">{focusTask ? '主线已锁定' : '待锁定主线'}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function FrontlineMap({
  tasks,
  activePomodoro,
  subtaskProgressMap,
  onStartFocus,
  onOpenTaskDetail,
  onPushTonight,
  onPushTomorrow,
  onComplete,
  onCreateTask,
}) {
  return (
    <section className="board-lane board-lane-enter">
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">TACTICAL MAP</div>
          <h3 className="board-lane-title">今日战术地图</h3>
          <div className="board-lane-copy">这里只放今天真正相关的战线任务，不把所有待办都堆进来。</div>
        </div>
        <button className="btn btn-sm btn-primary" onClick={onCreateTask}>+ 加入今日战线</button>
      </div>

      {tasks.length === 0 ? (
        <div className="empty-state" style={{ padding: 'var(--space-xl) 0' }}>
          <div className="empty-state-icon">🗺️</div>
          <div className="empty-state-text">今天还没有战线任务</div>
          <div className="empty-state-hint">先建立一项今天必须推进的任务。</div>
        </div>
      ) : (
        <div className="frontline-grid">
          {tasks.map(task => {
            const progress = subtaskProgressMap[task.task_id] || { total: 0, completed: 0 };
            const overdue = task.overdue || overdueDays(task.due_time) > 0;
            const active = activePomodoro?.task_id === task.task_id;
            const progressPct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
            return (
              <div
                key={task.task_id}
                className={`frontline-card${overdue ? ' overdue' : ''}${active ? ' active' : ''}`}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', marginBottom: 6 }}>
                      <span className="frontline-index">LINE {String(task.task_id).slice(0, 4)}</span>
                      <span className="section-kicker" style={{ marginBottom: 0 }}>{active ? 'ACTIVE LINE' : 'FRONTLINE'}</span>
                    </div>
                    <h3 className="frontline-title">{task.task_name}</h3>
                  </div>
                  <span className={overdue ? 'badge badge-error' : 'badge badge-pending'}>
                    {overdue ? `逾期 ${overdueDays(task.due_time)} 天` : '今日推进'}
                  </span>
                </div>

                <div className="frontline-copy">
                  {task.description
                    ? task.description.length > 96 ? `${task.description.slice(0, 96)}...` : task.description
                    : '还没有补充说明，建议先把这个任务拆到可执行。'}
                </div>

                <div className="frontline-metrics">
                  <div className="frontline-metric">
                    <div className="dossier-meta-label">时间窗</div>
                    <div>{taskWindow(task)}</div>
                  </div>
                  <div className="frontline-metric">
                    <div className="dossier-meta-label">子任务</div>
                    <div>{progress.total > 0 ? `${progress.completed}/${progress.total}` : '未拆解'}</div>
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', marginBottom: 6, fontSize: '0.74rem', color: 'var(--text-tertiary)' }}>
                    <span>推进阶段</span>
                    <span>{progress.total > 0 ? `${progressPct}%` : active ? '进行中' : '待启动'}</span>
                  </div>
                  <div className="frontline-progressbar">
                    <span style={{ width: `${progress.total > 0 ? progressPct : active ? 38 : 12}%` }} />
                  </div>
                </div>

                <div className="frontline-actions">
                  <button className="btn btn-sm btn-primary" onClick={() => onStartFocus(task)}>{active ? '继续专注' : '开始专注'}</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(task)}>详情</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => onPushTonight(task)}>今晚</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => onPushTomorrow(task)}>明早</button>
                  {task.status === 'pending' && <button className="btn btn-sm btn-success" onClick={() => onComplete(task.task_id)}>完成</button>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function RiskRadar({ overdueTasks, pendingTasks, todayTasks, onOpenTaskDetail, onOpenAi, onOpenCalendar }) {
  const unscheduledToday = todayTasks.filter(task => !task.start_time).length;
  const heavyLoad = todayTasks.filter(task => task.estimated_minutes).reduce((sum, task) => sum + Number(task.estimated_minutes || 0), 0);
  const staleTasks = pendingTasks.filter(task => !isTaskToday(task, new Date().toISOString().slice(0, 10)) && !task.overdue).slice(0, 2);
  const radarItems = [];

  if (overdueTasks.length > 0) {
    radarItems.push({
      key: 'overdue',
      title: `红区任务 ${overdueTasks.length} 项`,
      copy: `最严重的是「${overdueTasks[0].task_name}」，已逾期 ${overdueDays(overdueTasks[0].due_time)} 天。继续拖延会直接挤压今天主线。`,
      action: <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(overdueTasks[0])}>查看风险</button>,
    });
  }
  if (unscheduledToday > 0) {
    radarItems.push({
      key: 'unscheduled',
      title: `今日有 ${unscheduledToday} 项未排时段`,
      copy: '这会把今天变成临场救火。先把时间窗排出来，再谈推进质量。',
      action: <button className="btn btn-sm btn-ghost" onClick={onOpenCalendar}>打开日历</button>,
    });
  }
  if (heavyLoad > 360) {
    radarItems.push({
      key: 'overload',
      title: '今日估时超载',
      copy: `今天已排约 ${heavyLoad} 分钟，继续硬塞只会导致主线断裂，建议立刻缩表。`,
      action: <button className="btn btn-sm btn-ghost" onClick={() => onOpenAi?.({ intent: 'plan_today' })}>请求重排</button>,
    });
  }
  staleTasks.forEach(task => {
    radarItems.push({
      key: `stale-${task.task_id}`,
      title: `待推进任务悬空：${task.task_name}`,
      copy: '它不在今天战线里，也没有被清掉，属于最容易无限拖延的灰区任务。',
      action: <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(task)}>拉进主线</button>,
    });
  });

  return (
    <section className="board-lane board-lane-enter">
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">RISK RADAR</div>
          <h3 className="board-lane-title">风险雷达</h3>
          <div className="board-lane-copy">首页不只告诉你“有任务”，还要告诉你哪里已经开始烂掉。</div>
        </div>
      </div>
      {radarItems.length === 0 ? (
        <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
          <div className="empty-state-icon">🛡️</div>
          <div className="empty-state-text">当前没有明显风险</div>
          <div className="empty-state-hint">继续推进主线，保持节奏即可。</div>
        </div>
      ) : (
        <div className="radar-list">
          {radarItems.map(item => (
            <div className="radar-item" key={item.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                <div>
                  <div className="radar-title">{item.title}</div>
                  <div className="radar-copy">{item.copy}</div>
                </div>
                {item.action}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function AdviserDeck({ nextSuggestedTask, focusTask, noteReadyTasks, activePomodoro, onOpenAi, onStartFocus, onOpenTaskDetail }) {
  const briefing = activePomodoro
    ? '当前已经进入专注回合，AI 更适合帮你做后续重排和收尾。'
    : nextSuggestedTask?.overdue
      ? '当前第一风险是逾期任务，优先止损，再处理次级事项。'
      : nextSuggestedTask
        ? '今天主线已经浮现，先拿下它，再让 AI 帮你整理剩余部分。'
        : '还没有足够清晰的主线，可以让 AI 先安排今天。';

  return (
    <section className="board-lane board-lane-enter">
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">ADVISER DESK</div>
          <h3 className="board-lane-title">参谋台</h3>
          <div className="board-lane-copy">{briefing}</div>
        </div>
      </div>

      <div className="signal-list">
        <div className="signal-row">
          <div>
            <div className="signal-row-title">安排今天</div>
            <div className="signal-row-copy">基于当前任务重新排布今天的主线和时段，把碎片任务收口成一局。</div>
          </div>
          <button className="btn btn-sm btn-primary" onClick={() => onOpenAi?.({ intent: 'plan_today' })}>开始</button>
        </div>
        <div className="signal-row">
          <div>
            <div className="signal-row-title">拆解主任务</div>
            <div className="signal-row-copy">{(nextSuggestedTask || focusTask)?.task_name || '选择一项主线任务后再拆解。'}</div>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={() => onOpenAi?.({ intent: 'decompose_task', task: nextSuggestedTask || focusTask || null })}>拆解</button>
        </div>
        <div className="signal-row">
          <div>
            <div className="signal-row-title">整理记录</div>
            <div className="signal-row-copy">{noteReadyTasks[0]?.task_name ? `优先整理「${noteReadyTasks[0].task_name}」的上下文。` : '先形成可记录任务后再整理。'}</div>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={() => onOpenAi?.({ intent: 'summarize_notes', task: noteReadyTasks[0] || nextSuggestedTask || null })}>整理</button>
        </div>
        {nextSuggestedTask && !activePomodoro && (
          <div className="signal-row">
            <div>
              <div className="signal-row-title">直接推进主线</div>
              <div className="signal-row-copy">不等 AI，立刻给主线开一个 25 分钟推进窗口。</div>
            </div>
            <div className="inline-actions">
              <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(nextSuggestedTask)}>详情</button>
              <button className="btn btn-sm btn-primary" onClick={() => onStartFocus(nextSuggestedTask)}>开始</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function BattleTimeline({ recentLogs }) {
  return (
    <section className="board-lane board-lane-enter">
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">BATTLE LOG</div>
          <h3 className="board-lane-title">战报时间轴</h3>
          <div className="board-lane-copy">把今天真正发生的推进、完成和系统动作，整理成一条能回看的战报。</div>
        </div>
      </div>
      {recentLogs.length === 0 ? (
        <div className="empty-state" style={{ padding: 'var(--space-lg) 0' }}>
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-text">暂无战报</div>
          <div className="empty-state-hint">开始推进后，这里会记录今天的行动轨迹。</div>
        </div>
      ) : (
        <div className="timeline-list">
          {recentLogs.map(log => (
            <div className="timeline-item" key={log.id || log.created_at}>
              <div style={{ display: 'flex', gap: 'var(--space-sm)', minWidth: 0 }}>
                <span className="timeline-icon">{operationIcon(log.operation)}</span>
                <div>
                  <div className="signal-row-title">{log.detail || log.operation}</div>
                  <div className="signal-row-copy">操作类型：{log.operation}</div>
                </div>
              </div>
              <div className="signal-row-meta">{formatTimeShort(log.created_at)}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SupplyBay({ recentNotes, noteReadyTasks, onOpenNotes, onCreateTaskNote, onOpenTaskDetail, onOpenCalendar }) {
  return (
    <section className="board-lane">
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">SUPPLY BAY</div>
          <h3 className="board-lane-title">补给舱</h3>
          <div className="board-lane-copy">放低频但高实用的信息，不抢主线舞台。</div>
        </div>
      </div>

      <div className="supply-grid">
        <div className="supply-card">
          <div className="signal-row-title">情报摘录</div>
          {recentNotes.length === 0 ? (
            <div className="signal-row-copy">暂无最近笔记。</div>
          ) : (
            recentNotes.slice(0, 3).map(note => (
              <div key={note.note_id} className="signal-row-copy">
                {note.title} · {formatTimeShort(note.updated_at || note.created_at)}
              </div>
            ))
          )}
          <button className="btn btn-sm btn-ghost" onClick={onOpenNotes}>全部笔记</button>
        </div>

        <div className="supply-card">
          <div className="signal-row-title">可记录任务</div>
          {noteReadyTasks.length === 0 ? (
            <div className="signal-row-copy">还没有适合立刻记录的任务。</div>
          ) : (
            noteReadyTasks.slice(0, 3).map(task => (
              <div key={task.task_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)' }}>
                <span className="signal-row-copy">{task.task_name}</span>
                <button className="btn btn-sm btn-ghost" onClick={() => onCreateTaskNote?.(task)}>记录</button>
              </div>
            ))
          )}
        </div>

        <div className="supply-card">
          <div className="signal-row-title">快速跳转</div>
          <div className="signal-row-copy">需要切去别处时，从这里跳，不要打断主线浏览。</div>
          <div className="dossier-actions">
            <button className="btn btn-sm btn-ghost" onClick={onOpenCalendar}>打开日历</button>
            {noteReadyTasks[0] && (
              <button className="btn btn-sm btn-ghost" onClick={() => onOpenTaskDetail?.(noteReadyTasks[0])}>看主任务</button>
            )}
          </div>
        </div>
      </div>
    </section>
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
    } catch {}
  }, []);

  const fetchOverdueTasks = useCallback(async () => {
    try {
      const res = await apiPost('/api/task', { action: 'get_pending_tasks' });
      if (res.status === 'success') {
        const tasks = normalizeList(res, ['tasks', 'items']);
        setPendingTasks(tasks);
        setOverdueTasks(tasks.filter(t => t.overdue).slice(0, 5));
      }
    } catch {}
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
        const subtasks = res.status === 'success' ? normalizeList(res, ['subtasks', 'items']) : [];
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
      const res = await apiPut(`/api/task/${task.task_id}`, {
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

  const todayIso = new Date().toISOString().slice(0, 10);

  const todayTasks = useMemo(() => {
    const list = pendingTasks.filter(task => isTaskToday(task, todayIso) || task.overdue);
    return Array.isArray(list) ? list.slice(0, 6) : [];
  }, [pendingTasks, todayIso]);

  const recentNotes = useMemo(() => {
    const list = data?.recent_notes || [];
    return Array.isArray(list) ? list.slice(0, 5) : [];
  }, [data]);

  const recentLogs = useMemo(() => {
    const list = data?.recent_logs || [];
    return Array.isArray(list) ? list.slice(0, 6) : [];
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
  const focusTask = todayTasks[0] || null;

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 01 / Today Spread</div>
          <h1 className="atlas-chapter-title">今天不是列表，而是一张正在展开的行动页。</h1>
          <div className="atlas-chapter-copy">
            左页负责推进主线和今日战线，右页负责风险、参谋建议和节奏判断。低频信息退到页脚补给区，不再抢主舞台。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">本页导读</div>
          <div className="atlas-chapter-note-copy">先锁定主线，再排时段，再处理风险，最后补记录。</div>
        </div>
      </section>

      <BattleHero
        focusTask={focusTask}
        nextSuggestedTask={nextSuggestedTask}
        activePomodoro={activePomodoro}
        progress={progress}
        streak={streak}
        onCreateTask={onCreateTask}
        onCreateNote={onCreateNote}
        onOpenAi={onOpenAi}
        onStartFocus={startPomodoroForTask}
        onCompleteFocus={completePomodoro}
        onOpenTaskDetail={onOpenTaskDetail}
      />

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">今日战线</div>
          <div className="board-summary-value">{todayTasks.length}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">任务进度</div>
          <div className="board-summary-value">{progress}%</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">专注状态</div>
          <div className="board-summary-value" style={{ fontSize: '1rem' }}>{activePomodoro ? '进行中' : '待启动'}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">逾期数量</div>
          <div className="board-summary-value">{overdueTasks.length}</div>
        </div>
      </div>

      <div className="war-room-grid atlas-spread-grid">
        <div className="war-room-stack atlas-page-column">
          <FrontlineMap
            tasks={todayTasks}
            activePomodoro={activePomodoro}
            subtaskProgressMap={subtaskProgressMap}
            onStartFocus={startPomodoroForTask}
            onOpenTaskDetail={onOpenTaskDetail}
            onPushTonight={(task) => handlePushTask(task, 20)}
            onPushTomorrow={(task) => handlePushTask(task, 9)}
            onComplete={handleCompleteTask}
            onCreateTask={onCreateTask}
          />
          <section className="atlas-inline-note">
            <div className="atlas-inline-note-kicker">Left Page Margin</div>
            <div className="atlas-inline-note-copy">
              今日战线只保留真正要在今天推进的任务。能挪到明天的，不应该继续占据这张页。
            </div>
          </section>
          <BattleTimeline recentLogs={recentLogs} />
          <SupplyBay
            recentNotes={recentNotes}
            noteReadyTasks={noteReadyTasks}
            onOpenNotes={onOpenNotes}
            onCreateTaskNote={onCreateTaskNote}
            onOpenTaskDetail={onOpenTaskDetail}
            onOpenCalendar={onOpenCalendar}
          />
        </div>

        <div className="war-room-stack atlas-page-column">
          <RiskRadar
            overdueTasks={overdueTasks}
            pendingTasks={pendingTasks}
            todayTasks={todayTasks}
            onOpenTaskDetail={onOpenTaskDetail}
            onOpenAi={onOpenAi}
            onOpenCalendar={onOpenCalendar}
          />
          <AdviserDeck
            nextSuggestedTask={nextSuggestedTask}
            focusTask={focusTask}
            noteReadyTasks={noteReadyTasks}
            activePomodoro={activePomodoro}
            onOpenAi={onOpenAi}
            onStartFocus={startPomodoroForTask}
            onOpenTaskDetail={onOpenTaskDetail}
          />
          <section className="board-lane board-lane-enter atlas-ledger-lane">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">SCHEDULE PULSE</div>
                <h3 className="board-lane-title">今日节奏</h3>
                <div className="board-lane-copy">不是简单进度条，而是今天这一局目前的推进状态。</div>
              </div>
            </div>
            <div className="signal-list">
              <div className="signal-row">
                <div>
              <div className="signal-row-title">已完成 {streak.today_completed} / {streak.today_total || 0}</div>
              <div className="signal-row-copy">{progressText(progress)}</div>
            </div>
            <button className="btn btn-sm btn-ghost" onClick={onOpenCalendar}>看日历</button>
          </div>
              <div style={{
                height: 10,
                borderRadius: 999,
                background: 'rgba(67, 42, 28, 0.08)',
                overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%',
                  width: `${progress}%`,
                  background: progress >= 100 ? 'var(--success)' : 'var(--accent)',
                  transition: 'width 220ms var(--ease-apple)',
                }} />
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="page-shell">
      <div className="mission-masthead" style={{ minHeight: 180 }}>
        <div className="skeleton skeleton-text" style={{ width: 160, marginBottom: 'var(--space-sm)' }} />
        <div className="skeleton skeleton-text" style={{ width: '62%', height: 28 }} />
      </div>
      <div className="board-summary-grid">
        {[1, 2, 3, 4].map(i => (
          <div className="board-summary-card" key={i}>
            <div className="skeleton skeleton-text" style={{ width: 80 }} />
            <div className="skeleton skeleton-text" style={{ width: 56, height: 22 }} />
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
      <div className="empty-state-text">加载今天作战室失败</div>
      <div className="empty-state-hint">{error}</div>
      <button className="btn btn-primary" onClick={onRetry}>重试</button>
    </div>
  );
}
