function PlanningEditorCard({
  task,
  index,
  previewTask,
  draggingTaskId,
  setDraggingTaskId,
  reorderPlanningTask,
  movePlanningTask,
  duplicatePlanningTask,
  removePlanningTask,
  planningTasksLength,
  updatePlanningTaskField,
  formatPlanningDate,
}) {
  return (
    <div
      className={`planning-editor-card ${draggingTaskId === task.id ? 'dragging' : ''} ${index % 2 === 0 ? 'tilt-left' : 'tilt-right'}`}
      draggable
      onDragStart={() => setDraggingTaskId(task.id)}
      onDragEnd={() => setDraggingTaskId(null)}
      onDragOver={(event) => event.preventDefault()}
      onDrop={() => {
        reorderPlanningTask(draggingTaskId, task.id);
        setDraggingTaskId(null);
      }}
    >
      <div className="planning-editor-card-head">
        <div className="planning-task-title">{task.task_name || `任务 ${index + 1}`}</div>
        <div className="planning-editor-card-actions">
          <button className="btn btn-sm btn-ghost" onClick={() => movePlanningTask(task.id, -1)} disabled={index === 0}>上移</button>
          <button className="btn btn-sm btn-ghost" onClick={() => movePlanningTask(task.id, 1)} disabled={index === planningTasksLength - 1}>下移</button>
          <button className="btn btn-sm btn-ghost" onClick={() => duplicatePlanningTask(task.id)}>复制</button>
          <button className="btn btn-sm btn-ghost" onClick={() => removePlanningTask(task.id)} disabled={planningTasksLength <= 1}>删除</button>
        </div>
      </div>
      <div className="planning-editor-grid">
        <input
          value={task.task_name}
          onChange={(event) => updatePlanningTaskField(task.id, 'task_name', event.target.value)}
          placeholder="任务名称"
        />
        <input
          value={task.due_time}
          onChange={(event) => updatePlanningTaskField(task.id, 'due_time', event.target.value)}
          placeholder="截止日期 2026-05-20"
        />
        <input
          value={task.earliest_start}
          onChange={(event) => updatePlanningTaskField(task.id, 'earliest_start', event.target.value)}
          placeholder="最早开始 2026-05-18"
        />
        <input
          value={(task.depends_on || []).join(', ')}
          onChange={(event) => updatePlanningTaskField(task.id, 'depends_on', event.target.value)}
          placeholder="依赖任务，逗号分隔"
        />
      </div>
      <div className="planning-task-meta">
        <span>DDL {formatPlanningDate(task.due_time)}</span>
        <span>{task.depends_on?.length ? `依赖 ${task.depends_on.length}` : '可独立推进'}</span>
      </div>
      {previewTask.planned_slots?.length > 0 && (
        <div className="planning-task-slots">
          {previewTask.planned_slots.slice(0, 2).map((slot) => `${formatPlanningDate(slot.day)} ${slot.time_slot || `${slot.hours}h`}`).join(' · ')}
        </div>
      )}
    </div>
  );
}

export default function AiChatMissionBoard({
  planningTasks,
  visibleTasks,
  draggingTaskId,
  setDraggingTaskId,
  reorderPlanningTask,
  movePlanningTask,
  duplicatePlanningTask,
  removePlanningTask,
  updatePlanningTaskField,
  formatPlanningDate,
  addPlanningTask,
  showRawPlanningEditor,
  setShowRawPlanningEditor,
  draftedTasksCount,
  planningText,
  setPlanningText,
  planningTemplate,
  applyPlanningTextToCards,
  planningConstraints,
  updateConstraint,
  previewPlanning,
  planningLoading,
  loadPendingTasksIntoPlanning,
  fillPlanningTemplate,
  clearPlanningPreview,
  hasPlanningPreview,
}) {
  return (
    <div className="card ai-mission-board ai-book-chapter ai-tactics-chapter">
      <div className="board-lane-header ai-book-page-header ai-tactics-header">
        <div>
          <div className="section-kicker">Mission Board</div>
          <div className="board-lane-title">AI 安排任务</div>
          <div className="board-lane-copy">
            先编辑任务卡，再生成战术预览，对比不同风险等级的排兵路线。
          </div>
        </div>
        <span className="badge badge-pending">preview → confirm</span>
      </div>

      <div className="planning-card-editor ai-planning-card-editor ai-block-spacing-sm">
        {planningTasks.length === 0 ? (
          <div className="planning-empty">先添加一张任务卡，AI 才能开始排兵布阵。</div>
        ) : planningTasks.map((task, index) => {
          const previewTask = visibleTasks.find((item) => item.task_name === task.task_name) || task;
          return (
            <PlanningEditorCard
              key={task.id}
              task={task}
              index={index}
              previewTask={previewTask}
              draggingTaskId={draggingTaskId}
              setDraggingTaskId={setDraggingTaskId}
              reorderPlanningTask={reorderPlanningTask}
              movePlanningTask={movePlanningTask}
              duplicatePlanningTask={duplicatePlanningTask}
              removePlanningTask={removePlanningTask}
              planningTasksLength={planningTasks.length}
              updatePlanningTaskField={updatePlanningTaskField}
              formatPlanningDate={formatPlanningDate}
            />
          );
        })}
      </div>

      <div className="ai-inline-toolbar ai-block-spacing-sm">
        <button className="btn btn-ghost" onClick={addPlanningTask}>+ 添加任务卡</button>
        <button className="btn btn-ghost" onClick={() => setShowRawPlanningEditor((value) => !value)}>
          {showRawPlanningEditor ? '收起文本草稿' : '打开文本草稿'}
        </button>
        <div className="ai-inline-count">当前卡片 {draftedTasksCount} 张</div>
      </div>

      {showRawPlanningEditor && (
        <div className="planning-raw-editor ai-block-spacing-sm">
          <textarea
            value={planningText}
            onChange={(event) => setPlanningText(event.target.value)}
            placeholder={`每行一个任务，格式：\n任务名 | 截止时间 | 最早开始时间(可选) | 依赖任务(可选,逗号分隔)\n例如：\n${planningTemplate}`}
            rows={6}
            className="planning-raw-editor-textarea"
          />
          <div className="ai-inline-toolbar">
            <button className="btn btn-ghost" onClick={applyPlanningTextToCards}>文本同步到任务卡</button>
          </div>
        </div>
      )}

      <div className="planning-summary-grid ai-block-spacing-sm">
        <div className="planning-summary-card">
          <span className="planning-summary-label">工作日容量</span>
          <input
            type="number"
            min="1"
            max="12"
            value={planningConstraints.default_daily_hours}
            onChange={(event) => updateConstraint('default_daily_hours', event.target.value)}
          />
        </div>
        <div className="planning-summary-card">
          <span className="planning-summary-label">周末容量</span>
          <input
            type="number"
            min="0"
            max="12"
            value={planningConstraints.weekend_daily_hours}
            onChange={(event) => updateConstraint('weekend_daily_hours', event.target.value)}
          />
        </div>
        <div className="planning-summary-card">
          <span className="planning-summary-label">缓冲比例</span>
          <input
            type="number"
            min="0"
            max="0.8"
            step="0.05"
            value={planningConstraints.buffer_ratio}
            onChange={(event) => updateConstraint('buffer_ratio', event.target.value)}
          />
        </div>
      </div>

      <div className="ai-inline-toolbar">
        <button className="btn btn-primary" onClick={previewPlanning} disabled={planningLoading}>
          {planningLoading ? '预览中...' : '生成战术预览'}
        </button>
        <button className="btn btn-ghost" onClick={loadPendingTasksIntoPlanning} disabled={planningLoading}>载入今日待办</button>
        <button className="btn btn-ghost" onClick={fillPlanningTemplate}>填入示例</button>
        <button className="btn btn-ghost" onClick={clearPlanningPreview} disabled={!hasPlanningPreview}>清空预览</button>
        <div className="ai-inline-count">当前草案 {draftedTasksCount} 项</div>
      </div>
    </div>
  );
}
