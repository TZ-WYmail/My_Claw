import {
  formatDateTime,
  getAgentRunFilterLabel,
  getAgentRunReasonLabel,
  getAgentRunStatusBadge,
  getAgentRunStatusLabel,
  getAutoMailPolicyLabel,
  getAutoPolicyNarrative,
  getDecisionStatusLabel,
  getDraftStatusBadge,
  getDraftStatusLabel,
  getInboxLabel,
  getMailCommandLabel,
  getReplyLevelLabel,
  getRiskBadgeClass,
  MessagePaper,
} from './maildeskShared.jsx';

export default function OpenLetterPanel({
  selectedFolder,
  selectedThread,
  selectedThreadAccount,
  selectedMailtoHref,
  threadRefreshing,
  threadDetailLoading,
  activeDraft,
  latestAgentRun,
  threadDetail,
  archivingThreadId,
  markingReadThreadId,
  decisionUpdating,
  replyDraftGeneratingThreadId,
  taskCreatingThreadId,
  draftSendingId,
  selectedAgentRuns,
  agentRunFilter,
  agentRunsLoading,
  openPortalPage,
  copyPortalLink,
  handleRefreshSelectedThread,
  handleMarkRead,
  handleArchive,
  handleDecisionStatus,
  handleReplyThread,
  handleGenerateReplyDraft,
  handleCreateTaskFromMail,
  handleDiscussWithAi,
  fetchAgentRuns,
  setAgentRunFilter,
  onOpenDraftComposer,
  onSendDraft,
}) {
  const selectedThreadId = selectedThread?.thread_id || '';
  const isArchivingSelected = archivingThreadId && archivingThreadId === selectedThreadId;
  const isMarkingReadSelected = markingReadThreadId && markingReadThreadId === selectedThreadId;
  const isGeneratingReplyDraft = replyDraftGeneratingThreadId && replyDraftGeneratingThreadId === selectedThreadId;
  const isCreatingTask = taskCreatingThreadId && taskCreatingThreadId === selectedThreadId;
  const isDecisionPending = (status) => decisionUpdating.threadId === selectedThreadId && decisionUpdating.status === status;

  return (
    <section className="board-lane atlas-ledger-lane mail-spread-lane mail-letter-lane">
      <div className="board-lane-header mail-lane-header">
        <div className="mail-lane-head-copy">
          <div className="section-kicker">OPEN LETTER</div>
          <h3 className="board-lane-title">{selectedThread?.subject || '当前没有展开的信'}</h3>
          <div className="board-lane-copy">
            {selectedThread
              ? (selectedThread.latest_folder_kind === 'archive'
                ? '这是一条已经归档的往来记录。这里更适合翻阅、回看和确认历史，而不是继续把它摆在当前工作流正中央。'
                : `最近收在 ${getInboxLabel(selectedThread.latest_folder_kind)}，${selectedThread.needs_reply ? '仍在等待你的回信。' : '这条往返已经暂时安静下来。'}`)
              : '当你翻开一条线程，它会在这里展开成一叠真正可以阅读的往返信件。'}
          </div>
        </div>
        <div className="mail-lane-status">
          <div className="mail-lane-status-label">展开状态</div>
          <div className="mail-lane-status-value">
            {selectedThread ? formatDateTime(selectedThread.latest_message_at) : '等待翻开'}
          </div>
          <div className="mail-lane-status-copy">
            {selectedThread
              ? (selectedThread.latest_folder_kind === 'archive'
                ? '这是一条已归档往来，适合回看与确认历史。'
                : (selectedThread.needs_reply ? '这封信仍在等待你的下一步回应。' : '这条往返已暂时安静，但仍可继续处理。'))
              : '先从左侧翻开一封信，右页才会真正亮起来。'}
          </div>
        </div>
      </div>
      <div className="mail-letter-annotations">
        {!selectedThread && selectedFolder !== 'archive' && (
          <div className="mail-letter-note">
            默认只展示仍在流动的活跃线程。已归档的信不会继续占住案头，要看它们请切到归档箱。
          </div>
        )}
        {selectedThread?.portal_url && (
          <div className="mail-letter-note">
            这封信也有一张可从邮件里直接点开的处理页。桌面端和邮件端现在走的是同一条入口，不再是两套说法。
          </div>
        )}
        {!!selectedThread?.decision_status && (
          <div className="mail-letter-note">
            当前处理状态是“{getDecisionStatusLabel(selectedThread.decision_status)}”。
            {selectedThread.waiting_user_decision ? ' 它仍停在你的裁决栈里。' : ' 现在不占用待决定队列，但你随时可以把它重新放回案头。'}
          </div>
        )}
        {!!selectedThread?.linked_task_count && (
          <div className="mail-letter-note">
            这封信已经牵出 {selectedThread.linked_task_count} 项任务，纸页之外，事情已经开始移动。
          </div>
        )}
        {selectedThread?.last_actor && (
          <div className="mail-letter-note">
            当前往返停在
            {selectedThread.last_actor === 'counterparty' ? '对方' : selectedThread.last_actor === 'self' ? '我方' : '空白'}
            一侧；
            {selectedThread.has_new_inbound ? '有新的入站来信尚未闭环。' : '最近一轮往返已经暂时闭合。'}
            {selectedThread.has_pending_draft ? '案头还有一份待发草稿。' : '当前没有挂起草稿。'}
          </div>
        )}
        {selectedThreadAccount && (
          <div className="mail-letter-note">
            当前账户策略是“{getAutoMailPolicyLabel(selectedThreadAccount.auto_mail_policy)}”。
            {getAutoPolicyNarrative(selectedThreadAccount.auto_mail_policy)}
          </div>
        )}
        {!!selectedThread?.latest_draft_scheduled_send_at && (
          <div className="mail-letter-note">
            这条线程当前挂着一份计划寄出的草稿，时间定在 {formatDateTime(selectedThread.latest_draft_scheduled_send_at)}。
            {selectedThread.latest_draft_status === 'failed' ? ' 不过它上一次发送失败过，寄出前仍值得再看一眼。' : ' 在那之前，你仍然可以继续改写或提前寄出。'}
          </div>
        )}
      </div>
      {selectedThread && (
        <div className="mail-letter-toolbar">
          <div>
            <div className="section-kicker">MAIL-FIRST ENTRY</div>
            <div className="inline-actions" style={{ marginTop: 8 }}>
              <button className="btn btn-sm btn-primary" onClick={() => openPortalPage(selectedThread)}>打开处理页</button>
              <button className="btn btn-sm btn-ghost" onClick={() => copyPortalLink(selectedThread)}>复制处理页链接</button>
              {selectedMailtoHref && (
                <a className="btn btn-sm btn-ghost" href={selectedMailtoHref}>
                  在邮箱里继续回
                </a>
              )}
            </div>
          </div>

          <div>
            <div className="section-kicker">DESKTOP ACTIONS</div>
            <div className="inline-actions" style={{ marginTop: 8 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => handleRefreshSelectedThread(selectedThread.thread_id)} disabled={threadRefreshing}>
                {threadRefreshing ? '刷新中…' : '刷新这封信'}
              </button>
              {!!selectedThread.unread_count && (
                <button className="btn btn-sm btn-ghost" onClick={() => handleMarkRead(selectedThread.thread_id)} disabled={isMarkingReadSelected}>
                  {isMarkingReadSelected ? '标记中…' : '标记已读'}
                </button>
              )}
              {selectedThread.latest_folder_kind !== 'archive' && (
                <button className="btn btn-sm btn-ghost" onClick={() => handleArchive(selectedThread.thread_id)} disabled={isArchivingSelected}>
                  {isArchivingSelected ? '归档中…' : '归档'}
                </button>
              )}
              {selectedThread.decision_status !== 'pending' && (
                <button className="btn btn-sm btn-ghost" onClick={() => handleDecisionStatus(selectedThread.thread_id, 'pending')} disabled={isDecisionPending('pending')}>
                  {isDecisionPending('pending') ? '恢复中…' : '恢复待决定'}
                </button>
              )}
              {selectedThread.waiting_user_decision && (
                <button className="btn btn-sm btn-ghost" onClick={() => handleDecisionStatus(selectedThread.thread_id, 'snoozed')} disabled={isDecisionPending('snoozed')}>
                  {isDecisionPending('snoozed') ? '稍候中…' : '稍后再问'}
                </button>
              )}
              {selectedThread.waiting_user_decision && (
                <button className="btn btn-sm btn-ghost" onClick={() => handleDecisionStatus(selectedThread.thread_id, 'cleared')} disabled={isDecisionPending('cleared')}>
                  {isDecisionPending('cleared') ? '收束中…' : '暂时处理完'}
                </button>
              )}
              <button className="btn btn-sm btn-primary" onClick={() => handleReplyThread(selectedThread)}>
                {activeDraft ? '继续写草稿' : '回复这封信'}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => handleGenerateReplyDraft(selectedThread)} disabled={isGeneratingReplyDraft}>
                {isGeneratingReplyDraft ? '起草中…' : '一键起草'}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => handleCreateTaskFromMail(selectedThread)} disabled={isCreatingTask}>
                {isCreatingTask ? '落任务中…' : '转成任务'}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => handleDiscussWithAi(selectedThread)}>和 AI 商量</button>
            </div>
          </div>
        </div>
      )}

      {!selectedThread ? (
        <div className="empty-state">
          <div className="empty-state-icon">🕯️</div>
          <div className="empty-state-text">先从左侧选一封信</div>
          <div className="empty-state-hint">最值得先翻开的，通常是那条还亮着未读或待回标记的线程。</div>
        </div>
      ) : threadDetailLoading || !threadDetail ? (
        <div className="empty-state">
          <div className="empty-state-icon">📨</div>
          <div className="empty-state-text">正在展开这封信</div>
          <div className="empty-state-hint">旧纸页已经收起，新的上下文与自动处理台账正在落到桌面上。</div>
        </div>
      ) : (
        <div className="board-card-grid mail-letter-stack" style={{ gridTemplateColumns: '1fr' }}>
          <article className="dossier-card" style={{ transform: 'rotate(-0.15deg)', borderColor: 'rgba(103, 78, 40, 0.22)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
              <div>
                <div className="section-kicker">AUTOMATION COUNSEL</div>
                <h3 className="dossier-title">自动处理说明</h3>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                  这里解释系统为什么把它判成待回复、待决定，或者为什么自动流程没有继续往下走。
                </div>
              </div>
              <span className={`badge ${selectedThread.waiting_user_decision ? 'badge-warning' : 'badge-ghost'}`}>
                {selectedThread.waiting_user_decision ? '仍待你裁决' : '当前不占裁决栈'}
              </span>
            </div>
            <div className="signal-list" style={{ marginTop: 'var(--space-md)' }}>
              <div className="signal-row">
                <div>
                  <div className="signal-row-title">线程判断</div>
                  <div className="signal-row-copy">{selectedThread.analysis_reason || '当前还没有分析说明。'}</div>
                </div>
                <span className={`badge ${getRiskBadgeClass(selectedThread.risk_level)}`}>{getReplyLevelLabel(selectedThread.reply_level)}</span>
              </div>
              <div className="signal-row">
                <div>
                  <div className="signal-row-title">自动策略</div>
                  <div className="signal-row-copy">
                    {selectedThreadAccount
                      ? `${getAutoMailPolicyLabel(selectedThreadAccount.auto_mail_policy)} · ${getAutoPolicyNarrative(selectedThreadAccount.auto_mail_policy)}`
                      : '当前还没找到这条线程对应的账户策略。'}
                  </div>
                </div>
                <span className="badge badge-ghost">{selectedThreadAccount ? getAutoMailPolicyLabel(selectedThreadAccount.auto_mail_policy) : '未识别'}</span>
              </div>
              {latestAgentRun && (
                <>
                  <div className="signal-row">
                    <div>
                      <div className="signal-row-title">最近一次代理判断</div>
                      <div className="signal-row-copy">{latestAgentRun.result_summary || '已记录自动处理结果。'}</div>
                      {!!latestAgentRun.details?.reason_code && (
                        <div className="signal-row-copy" style={{ marginTop: 6 }}>
                          {getAgentRunReasonLabel(latestAgentRun.details.reason_code) || latestAgentRun.details.reason_code}
                        </div>
                      )}
                    </div>
                    <span className={`badge ${getAgentRunStatusBadge(latestAgentRun.status)}`}>{getAgentRunStatusLabel(latestAgentRun.status)}</span>
                  </div>
                  <div className="signal-row">
                    <div>
                      <div className="signal-row-title">代理命令解释</div>
                      <div className="signal-row-copy">{getMailCommandLabel(latestAgentRun.details?.command)}</div>
                    </div>
                    <span className="badge badge-ghost">{formatDateTime(latestAgentRun.updated_at || latestAgentRun.created_at)}</span>
                  </div>
                </>
              )}
              {!latestAgentRun && (
                <div className="signal-row">
                  <div>
                    <div className="signal-row-title">尚未留下自动处理台账</div>
                    <div className="signal-row-copy">这通常意味着后台轮询还没处理到这封新来信，或者当前线程还没有触发自动处理链路。</div>
                  </div>
                </div>
              )}
            </div>
            {selectedThreadAccount?.auto_mail_policy === 'auto_send' && (
              <div className="mail-inline-alert mail-inline-alert-error" style={{ marginTop: 'var(--space-md)' }}>
                当前账户处于“自动寄出”策略。只要线程被判断为直接协商来信且自动起草成功，系统可能直接把回信发出。
              </div>
            )}
          </article>
          {(threadDetail.agent_runs || []).length > 0 && (
            <article className="dossier-card" style={{ transform: 'rotate(0.25deg)', borderColor: 'var(--accent)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                <div>
                  <div className="section-kicker">AGENT LEDGER</div>
                  <h3 className="dossier-title">自动处理台账</h3>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                    系统替你起草、跳过、等待确认或自动寄出的动作，都会在这里留下痕迹。
                  </div>
                </div>
                <span className="badge badge-ghost">{selectedAgentRuns.length} / {(threadDetail.agent_runs || []).length} 条记录</span>
              </div>
              <div className="mail-filter-toggles" style={{ marginTop: 'var(--space-md)' }}>
                {['all', 'user_confirmation_required', 'draft_created', 'sent', 'failed', 'skipped_non_direct'].map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    className={`badge ${agentRunFilter === filter ? 'badge-warning' : 'badge-ghost'}`}
                    onClick={() => setAgentRunFilter(filter)}
                  >
                    {getAgentRunFilterLabel(filter)}
                  </button>
                ))}
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => fetchAgentRuns(selectedThread.thread_id)}
                  disabled={agentRunsLoading}
                >
                  {agentRunsLoading ? '刷新中…' : '刷新台账'}
                </button>
              </div>
              <div className="signal-list" style={{ marginTop: 'var(--space-md)' }}>
                {selectedAgentRuns.length === 0 ? (
                  <div className="signal-row">
                    <div>
                      <div className="signal-row-title">当前筛选下没有记录</div>
                      <div className="signal-row-copy">切换筛选标签，或刷新这条线程的自动处理台账。</div>
                    </div>
                  </div>
                ) : (
                  selectedAgentRuns.map((run) => (
                    <details key={run.run_id} className="mail-detail-block mail-detail-block-card">
                      <summary>
                        <span>{run.action_kind === 'auto_reply' ? '自动回信代理' : run.action_kind}</span>
                        <span className={`badge ${getAgentRunStatusBadge(run.status)}`}>{getAgentRunStatusLabel(run.status)}</span>
                      </summary>
                      <div className="signal-list" style={{ marginTop: 'var(--space-sm)' }}>
                        <div className="signal-row">
                          <div>
                            <div className="signal-row-title">结果摘要</div>
                            <div className="signal-row-copy">{run.result_summary || '系统已记录这一轮自动处理。'}</div>
                          </div>
                          <span className="badge badge-ghost">{formatDateTime(run.updated_at || run.created_at)}</span>
                        </div>
                        {!!run.details?.reason_code && (
                          <div className="signal-row">
                            <div>
                              <div className="signal-row-title">原因代码</div>
                              <div className="signal-row-copy">{getAgentRunReasonLabel(run.details.reason_code) || run.details.reason_code}</div>
                            </div>
                            <span className="badge badge-ghost">{run.details.reason_code}</span>
                          </div>
                        )}
                        {(run.details?.policy || run.details?.command) && (
                          <div className="signal-row">
                            <div>
                              <div className="signal-row-title">策略与指令</div>
                              <div className="signal-row-copy">
                                {run.details?.policy ? `策略 ${getAutoMailPolicyLabel(run.details.policy)}` : '未记录策略'}
                                {run.details?.command ? ` · ${getMailCommandLabel(run.details.command)}` : ' · 未识别邮件指令'}
                              </div>
                            </div>
                          </div>
                        )}
                        {!!run.details?.draft_id && (
                          <div className="signal-row">
                            <div>
                              <div className="signal-row-title">关联草稿</div>
                              <div className="signal-row-copy">这次自动处理写到了草稿 {run.details.draft_id}。</div>
                            </div>
                            <span className="badge badge-ghost">{run.details.draft_id}</span>
                          </div>
                        )}
                      </div>
                    </details>
                  ))
                )}
              </div>
            </article>
          )}
          {(threadDetail.messages || []).map(message => (
            <MessagePaper key={message.message_id} message={message} />
          ))}
          {(threadDetail.drafts || []).filter(draft => draft.status !== 'sent').map(draft => (
            <article key={draft.draft_id} className="dossier-card" style={{ transform: 'rotate(-0.2deg)', borderColor: 'var(--warning)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                <div>
                  <div className="section-kicker">草稿席</div>
                  <h3 className="dossier-title">{draft.subject}</h3>
                </div>
                <span className={`badge ${getDraftStatusBadge(draft.status)}`}>{getDraftStatusLabel(draft.status)}</span>
              </div>
              <div className="mission-chip-row" style={{ marginTop: 'var(--space-sm)' }}>
                <span className="badge badge-ghost">{draft.ai_generated ? 'AI 起草' : '手动草稿'}</span>
                <span className={`badge ${draft.user_edited_after_ai ? 'badge-warning' : 'badge-ghost'}`}>
                  {draft.user_edited_after_ai ? '你后来改过' : '保持原始版本'}
                </span>
                {!!draft.scheduled_send_at && (
                  <span className="badge badge-ghost">计划寄出 {formatDateTime(draft.scheduled_send_at)}</span>
                )}
              </div>
              {draft.status === 'failed' && (
                <div className="mail-inline-alert mail-inline-alert-error" style={{ marginTop: 'var(--space-md)' }}>
                  这份草稿上一次发送没有成功。你可以先继续编辑，确认收件人与内容后重新寄出。
                </div>
              )}
              <div style={{ marginTop: 10, whiteSpace: 'pre-wrap', fontSize: '0.92rem', lineHeight: 1.65 }}>
                {draft.body_html || '这份草稿还没有正文。'}
              </div>
              <div className="inline-actions" style={{ marginTop: 'var(--space-md)' }}>
                <button className="btn btn-sm btn-primary" onClick={() => onOpenDraftComposer(draft, selectedThread)}>继续编辑</button>
                <button className="btn btn-sm btn-ghost" onClick={() => onSendDraft(draft)} disabled={draftSendingId === draft.draft_id}>
                  {draftSendingId === draft.draft_id ? '寄送中…' : draft.status === 'failed' ? '重新寄出这版' : '发送这版'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
