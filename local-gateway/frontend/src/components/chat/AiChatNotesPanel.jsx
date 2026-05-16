import { ensureArray } from '../../utils/normalize';

function CompactList({ items, className = '' }) {
  if (!items.length) return null;
  return (
    <div className={`ai-compact-list ${className}`.trim()}>
      {items.map((item, index) => (
        <div key={`${item}-${index}`} className="ai-compact-list-item">{item}</div>
      ))}
    </div>
  );
}

function ReflectionBlock({ activeRoundAssistantMessage }) {
  const thinking = activeRoundAssistantMessage?.thinking?.trim() || '';
  const toolCalls = ensureArray(activeRoundAssistantMessage?.tool_calls);
  if (!thinking && toolCalls.length === 0) return null;

  const actionLines = toolCalls
    .slice(0, 2)
    .map((tc) => tc.function?.name || tc.name || 'tool');

  return (
    <div className="ai-insight-compact-card reflection">
      <div className="ai-message-card-head">
        <span>🤔 反思者质疑</span>
        <strong>Reflection</strong>
      </div>
      {thinking ? <div className="ai-message-card-copy">{thinking}</div> : null}
      {actionLines.length > 0 ? (
        <CompactList
          items={actionLines.map((line) => `执行动作 · ${line}`)}
          className="muted"
        />
      ) : null}
    </div>
  );
}

function PlannerPerspectiveBlock({
  activePlanningView,
  planningPreview,
  visibleTasks,
  activeSummary,
  planHourTotal,
  formatPlanningDate,
}) {
  if (!planningPreview) return null;

  const urgentTasks = visibleTasks
    .filter((task) => task.due_time || task.earliest_start || task.planned_slots?.length)
    .slice(0, 3)
    .map((task) => {
      const firstSlot = task.planned_slots?.[0];
      const slotLabel = firstSlot
        ? `${formatPlanningDate(firstSlot.day)} ${firstSlot.time_slot || `${firstSlot.hours}h`}`
        : '待分配';
      return `${task.task_name} · 截止 ${formatPlanningDate(task.due_time)} · ${slotLabel}`;
    });

  const alerts = [
    ...(activePlanningView?.conflicts || []).map((item) => item.message),
    ...(activePlanningView?.overload_days || []).map((item) => `${item.date} 过载 ${item.total_hours}h / 可用 ${item.available_hours}h`),
    ...(activePlanningView?.infeasible_tasks || []).map((item) => `${item.task_name}：${item.reason}`),
  ].slice(0, 3);

  return (
    <div className="ai-insight-compact-card planner">
      <div className="ai-message-card-head">
        <span>🎯 规划者视角</span>
        <strong>{activeSummary?.risk_level || 'balanced'}</strong>
      </div>
      <div className="ai-compact-metrics">
        <div className="ai-compact-metric">
          <span>风险</span>
          <strong>{activeSummary?.risk_level || 'low'}</strong>
        </div>
        <div className="ai-compact-metric">
          <span>总时长</span>
          <strong>{planHourTotal.toFixed(1)}h</strong>
        </div>
        <div className="ai-compact-metric">
          <span>今日战线</span>
          <strong>{urgentTasks.length} 项</strong>
        </div>
      </div>
      <CompactList items={urgentTasks} />
      <CompactList items={alerts} className="warning" />
    </div>
  );
}

export default function AiChatNotesPanel(props) {
  const {
    activeRoundAssistantMessage,
    planningPreview,
    activePlanningView,
    visibleTasks,
    activeSummary,
    planHourTotal,
    formatPlanningDate,
  } = props;

  const hasReflection = Boolean(activeRoundAssistantMessage?.thinking?.trim() || activeRoundAssistantMessage?.tool_calls?.length);
  const hasPlanner = Boolean(planningPreview);

  if (!hasReflection && !hasPlanner) return null;

  return (
    <div className="ai-insights-compact-row">
      <ReflectionBlock activeRoundAssistantMessage={activeRoundAssistantMessage} />
      <PlannerPerspectiveBlock
        activePlanningView={activePlanningView}
        planningPreview={planningPreview}
        visibleTasks={visibleTasks}
        activeSummary={activeSummary}
        planHourTotal={planHourTotal}
        formatPlanningDate={formatPlanningDate}
      />
    </div>
  );
}
