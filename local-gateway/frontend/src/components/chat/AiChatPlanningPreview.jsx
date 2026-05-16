function RiskSummaryCard({ tone, label, value }) {
  return (
    <div className={`planning-summary-card ${tone ? 'planning-summary-card-risk' : ''}`} style={tone ? { background: tone.background, color: tone.color } : undefined}>
      <span className="planning-summary-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SuggestionList({
  title,
  toneClass,
  items,
  acceptedSuggestions,
  setAcceptedSuggestions,
}) {
  if (!items.length) return null;

  return (
    <div className="ai-preview-section">
      <div className={`ai-preview-section-title ${toneClass}`}>{title}</div>
      {items.slice(0, 6).map((item, index) => (
        <label key={`${title}-${index}`} className={`planning-suggestion-row ${toneClass === 'danger' ? 'must' : ''}`}>
          <input
            type="checkbox"
            checked={acceptedSuggestions.includes(item.task_name)}
            onChange={(event) => {
              setAcceptedSuggestions((prev) => (
                event.target.checked
                  ? [...new Set([...prev, item.task_name])]
                  : prev.filter((name) => name !== item.task_name)
              ));
            }}
            className="planning-suggestion-checkbox"
          />
          <span>
            <strong>{item.task_name}</strong> → {item.suggestion} {item.target_day ? `/ ${item.target_day}` : ''}
            <span className="planning-suggestion-meta">
              {item.reason_type} · 影响 {item.impact_scope?.days || 0}天 {item.impact_scope?.tasks || 0}任务 · 置信度 {Math.round((item.confidence || 0) * 100)}%
            </span>
            <span className="planning-suggestion-meta">{item.reason}</span>
          </span>
        </label>
      ))}
    </div>
  );
}

export default function AiChatPlanningPreview({
  planningPreview,
  activePlanningView,
  selectedVariant,
  setSelectedVariant,
  getRiskTone,
  activeSummary,
  planHourTotal,
  visibleTasks,
  formatPlanningDate,
  interruptTaskName,
  setInterruptTaskName,
  interruptTaskDueTime,
  setInterruptTaskDueTime,
  replanWithInterrupt,
  planningLoading,
  replanResult,
  reasonOptions,
  reasonFilter,
  setReasonFilter,
  mustChangeSuggestions,
  optionalSuggestions,
  acceptedSuggestions,
  setAcceptedSuggestions,
  rerunWithAcceptedSuggestions,
  confirmPlanning,
}) {
  if (!planningPreview) return null;

  return (
    <div className="card planning-preview-shell ai-preview-bay ai-book-chapter ai-book-preview-chapter">
      <div className="ai-preview-annex-head ai-preview-annex-layout ai-block-spacing-sm">
        <div className="ai-preview-annex-titleblock">
          <div className="section-kicker">Battle Preview</div>
          <h3 className="ai-preview-annex-title">预览结果</h3>
          <div className="ai-preview-annex-summary">
            {activePlanningView?.explanation?.summary || planningPreview.explanation?.summary || '已生成结构化预览'}
          </div>
        </div>
        <div className="ai-preview-variant-strip ai-preview-variant-wrap">
          {(planningPreview.variants || []).map((variant) => (
            <button
              key={variant.id}
              className={`planning-variant-card ${selectedVariant === variant.id ? 'selected' : ''}`}
              onClick={() => setSelectedVariant(variant.id)}
            >
              <span className="planning-variant-label">{variant.label}</span>
              <span className="planning-variant-risk">{getRiskTone(variant.summary?.risk_level).label}</span>
              <span className="planning-variant-desc">{variant.description}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="planning-summary-grid ai-preview-summary-grid">
        <RiskSummaryCard tone={getRiskTone(activeSummary.risk_level)} label="风险等级" value={getRiskTone(activeSummary.risk_level).label} />
        <RiskSummaryCard label="总排程时长" value={`${planHourTotal.toFixed(1)}h`} />
        <RiskSummaryCard label="过载日" value={activeSummary.overload_day_count || 0} />
        <RiskSummaryCard label="冲突数" value={activeSummary.conflict_count || 0} />
        <RiskSummaryCard label="深度工作日" value={activeSummary.deep_work_days || 0} />
        <RiskSummaryCard label="不可行任务" value={activeSummary.infeasible_count || 0} />
      </div>

      <div className="planning-columns">
        <div className="planning-main-column">
          <div className="planning-panel ai-annex-panel">
            <div className="planning-panel-header">
              <h4>任务战线</h4>
              <span>{visibleTasks.length} 项</span>
            </div>
            <div className="planning-roster">
              {visibleTasks.map((task, index) => (
                <div key={task.key || `${task.task_name}-${index}`} className="planning-roster-row">
                  <div>
                    <div className="planning-roster-title">{task.task_name}</div>
                    <div className="planning-roster-meta">
                      截止 {formatPlanningDate(task.due_time)}
                      {task.earliest_start ? ` · 最早 ${formatPlanningDate(task.earliest_start)}` : ''}
                      {task.depends_on?.length ? ` · 依赖 ${task.depends_on.join('、')}` : ''}
                    </div>
                  </div>
                  <div className="planning-roster-slot">
                    {task.planned_slots?.length > 0
                      ? task.planned_slots.slice(0, 2).map((slot) => (
                        <span key={`${task.task_name}-${slot.day}-${slot.time_slot || slot.hours}`} className="planning-slot-chip">
                          {formatPlanningDate(slot.day)} {slot.time_slot || `${slot.hours}h`}
                        </span>
                      ))
                      : <span className="planning-slot-empty">待分配</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="planning-panel ai-annex-panel">
            <div className="planning-panel-header">
              <h4>每日战役板</h4>
              <span>{Object.keys(activePlanningView?.daily_plan || {}).length} 天</span>
            </div>
            <div className="planning-day-grid">
              {Object.entries(activePlanningView?.daily_plan || {}).slice(0, 8).map(([date, info]) => (
                <div key={date} className={`planning-day-card ${info.overload ? 'overload' : ''}`}>
                  <div className="planning-day-head">
                    <strong>{formatPlanningDate(date)}</strong>
                    <span>{info.total_hours}h / {info.available_hours ?? '-'}h</span>
                  </div>
                  {(info.calendar_events || []).length > 0 && (
                    <div className="planning-day-note">
                      占用：{(info.calendar_events || []).map((event) => event.title).join(' / ')}
                    </div>
                  )}
                  <div className="planning-day-task-list">
                    {(info.tasks || []).map((task, taskIndex) => (
                      <div key={`${date}-${task.task_name}-${taskIndex}`} className="planning-day-task">
                        <span>{task.task_name}</span>
                        <span>{task.time_slot || `${task.hours}h`}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="planning-side-column">
          <div className="planning-panel ai-annex-panel">
            <div className="planning-panel-header">
              <h4>关键提示</h4>
              <span>{(activePlanningView?.conflicts || []).length + (activePlanningView?.overload_days || []).length}</span>
            </div>
            <div className="planning-alert-stack">
              {(activePlanningView?.conflicts || []).map((item, index) => (
                <div key={index} className="planning-alert warning">{item.message}</div>
              ))}
              {(activePlanningView?.overload_days || []).map((item, index) => (
                <div key={`ol-${index}`} className="planning-alert danger">
                  {item.date} 过载 {item.total_hours}h，可用 {item.available_hours}h
                </div>
              ))}
              {(activePlanningView?.infeasible_tasks || []).map((item, index) => (
                <div key={`if-${index}`} className="planning-alert danger">
                  {item.task_name}：{item.reason}
                </div>
              ))}
              {!(activePlanningView?.conflicts || []).length && !(activePlanningView?.overload_days || []).length && !(activePlanningView?.infeasible_tasks || []).length && (
                <div className="planning-alert success">当前方案没有明显冲突，可直接确认。</div>
              )}
            </div>
          </div>

          <div className="planning-panel ai-annex-panel">
            <div className="planning-panel-header">
              <h4>时间线摘要</h4>
              <span>{(activePlanningView?.daily_timeline || []).length}</span>
            </div>
            <div className="planning-timeline-list">
              {(activePlanningView?.daily_timeline || []).slice(0, 6).map((line, index) => (
                <div key={index} className="planning-timeline-item">{line}</div>
              ))}
            </div>
          </div>

          <div className="planning-panel ai-annex-panel">
            <div className="planning-panel-header">
              <h4>突发任务插队</h4>
              <span>Replan</span>
            </div>
            <div className="ai-single-column-form">
              <input
                value={interruptTaskName}
                onChange={(event) => setInterruptTaskName(event.target.value)}
                placeholder="突发任务名称"
              />
              <input
                value={interruptTaskDueTime}
                onChange={(event) => setInterruptTaskDueTime(event.target.value)}
                placeholder="截止时间，如 2026-05-18"
              />
              <button className="btn btn-ghost" onClick={replanWithInterrupt} disabled={planningLoading}>
                {planningLoading ? '重排中...' : '插队重排'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {replanResult && (
        <div className="planning-panel ai-annex-panel ai-replan-annex ai-block-spacing-sm">
          <div className="planning-panel-header">
            <h4>重排影响说明</h4>
            <span>{replanResult.reordered_tasks?.length || 0} 条建议</span>
          </div>
          <div className="planning-impact-list">
            {(replanResult.impact_summary || []).map((item, index) => (
              <div key={`impact-${index}`} className="planning-impact-item">{item}</div>
            ))}
            {(replanResult.risk_changes || []).map((item, index) => (
              <div key={`risk-${index}`} className="planning-impact-item warning">{item}</div>
            ))}
          </div>
          {(replanResult.conflict_chain || []).length > 0 && (
            <div className="ai-preview-section">
              <div className="ai-preview-section-title">冲突链</div>
              {(replanResult.conflict_chain || []).slice(0, 5).map((item, index) => (
                <div key={`chain-${index}`} className="planning-chain-item">
                  {item.task_name}：{(item.dates || []).join('、') || '无日期'} / {(item.reasons || []).slice(0, 2).join('；')}
                </div>
              ))}
            </div>
          )}
          {(replanResult.reordered_tasks || []).length > 0 && (
            <div className="ai-preview-section">
              <div className="ai-preview-section-title">重排建议</div>
              <div className="ai-inline-toolbar ai-inline-toolbar-tight">
                {reasonOptions.map(([value, label]) => (
                  <button
                    key={value}
                    className={`btn btn-sm ${reasonFilter === value ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => setReasonFilter(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <SuggestionList
                title="必须调整"
                toneClass="danger"
                items={mustChangeSuggestions}
                acceptedSuggestions={acceptedSuggestions}
                setAcceptedSuggestions={setAcceptedSuggestions}
              />
              <SuggestionList
                title="可选优化"
                toneClass="warning"
                items={optionalSuggestions}
                acceptedSuggestions={acceptedSuggestions}
                setAcceptedSuggestions={setAcceptedSuggestions}
              />
              <button className="btn btn-sm btn-ghost" onClick={rerunWithAcceptedSuggestions} disabled={planningLoading}>
                按已选建议二次重排
              </button>
            </div>
          )}
          {(replanResult.applied_actions || []).length > 0 && (
            <div className="ai-preview-section">
              <div className="ai-preview-section-title">已应用动作</div>
              {(replanResult.applied_actions || []).slice(0, 6).map((item, index) => (
                <div key={`applied-${index}`} className="planning-chain-item">
                  {item.task_name} → {item.action} / {item.target_day || '-'} / {item.reason_type || '-'} / {item.severity || '-'} / 影响 {item.impact_scope?.days || 0}天 {item.impact_scope?.tasks || 0}任务 / 置信度 {Math.round((item.confidence || 0) * 100)}% / {item.reason || '无'}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="ai-preview-annex-footer ai-preview-annex-footer-layout">
        <div className="ai-preview-annex-note ai-preview-annex-summary">
          {planningPreview.explanation?.next_step || '确认后会把当前方案落成真实任务。'}
        </div>
        <button className="btn btn-primary" onClick={confirmPlanning} disabled={planningLoading}>
          {planningLoading ? '创建中...' : '确认创建'}
        </button>
      </div>
    </div>
  );
}
