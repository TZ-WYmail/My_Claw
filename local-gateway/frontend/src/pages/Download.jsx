import MailComposerModal from '../components/maildesk/MailComposerModal';
import MailControlGrid from '../components/maildesk/MailControlGrid';
import OpenLetterPanel from '../components/maildesk/OpenLetterPanel';
import MailRailPanel from '../components/maildesk/MailRailPanel';
import {
  DecisionQueueCard,
  formatDateTime,
  getAutoMailPolicyLabel,
  getAutoPolicyNarrative,
} from '../components/maildesk/maildeskShared.jsx';
import { useMailDeskState } from '../hooks/useMailDeskState';
import { useToast } from '../hooks/useToast';

const FOLDER_OPTIONS = [
  { value: '', label: '全部信箱' },
  { value: 'inbox', label: '收件箱' },
  { value: 'archive', label: '归档' },
  { value: 'sent', label: '已发出' },
  { value: 'drafts', label: '草稿' },
];

const TONE_OPTIONS = [
  { value: 'plain', label: '克制' },
  { value: 'warm', label: '温和' },
  { value: 'romantic', label: '书信式' },
];

const AUTO_MAIL_POLICY_OPTIONS = [
  { value: 'draft_only', label: '只起草，不触发确认' },
  { value: 'draft_and_notify', label: '起草后等我确认' },
  { value: 'auto_send', label: '自动寄出回信' },
];

const POLLING_FOLDER_OPTIONS = [
  { value: 'inbox', label: '收件箱' },
  { value: 'sent', label: '已发出' },
  { value: 'drafts', label: '草稿' },
  { value: 'archive', label: '归档' },
];

export default function Download({ quickAction = null, clearQuickAction = null, onOpenNotifyNetwork = null, onOpenAi = null }) {
  const toast = useToast();
  const state = useMailDeskState({
    quickAction,
    clearQuickAction,
    onOpenAi,
    toast,
  });

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 09 / Correspondence Desk</div>
          <h1 className="atlas-chapter-title">这里不再是下载转运页，而是一张真正开始运作的书信台。</h1>
          <div className="atlas-chapter-copy">
            来信、回信、草稿、已读与归档，都不该散落在系统边缘。每一封信都应该被放回桌面中央，重新编入你的任务、记忆与今日节奏。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">处理顺序</div>
          <div className="atlas-chapter-note-copy">先看今天有多少封信需要回应，再读最紧要的那一封，最后安静地把回信写完寄出。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">LETTER ROOM</span>
            <h1 className="mission-title">书信台该像一张有来有往的案桌，而不是一堵冷冰冰的消息墙。</h1>
            <div className="mission-copy">
              如果今天有信抵达，你会在这里看见它们的来处、语气、等待和重量。若要回信，也不必匆忙，只要先把最重要的一封翻开。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-warning">{state.dashboard?.inbound_today ?? 0} 封今日来信</span>
              <span className="badge badge-error">{state.dashboard?.needs_reply_threads ?? 0} 条待回应线程</span>
              <span className="badge badge-pending">{state.dashboard?.waiting_decision_threads ?? 0} 封待你决定</span>
              <span className="badge badge-pending">{state.dashboard?.draft_count ?? 0} 份草稿</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">通信气候</div>
            <div className="mission-sidecard-copy">
              清晰永远先于修辞，但一封体面的信仍然值得有温度。你可以让它克制，也可以让它像月光下写成的短笺。
            </div>
          </div>
        </div>
      </section>

      <div className="atlas-toolbar">
        <select value={state.selectedAccount} onChange={(e) => state.setSelectedAccount(e.target.value)} style={{ maxWidth: 220 }}>
          <option value="">全部账户</option>
          {state.accounts.map(account => (
            <option key={account.account_id} value={account.account_id}>{account.display_name} · {account.email_address}</option>
          ))}
        </select>
        <select value={state.selectedFolder} onChange={(e) => state.setSelectedFolder(e.target.value)} style={{ maxWidth: 160 }}>
          {FOLDER_OPTIONS.map(option => (
            <option key={option.value || 'all'} value={option.value}>{option.label}</option>
          ))}
        </select>
        <button className="btn btn-ghost" onClick={state.handleSyncInbox} disabled={!state.selectedAccount || state.syncing || state.loading}>
          {state.syncing ? '正在拉信…' : '同步收件箱'}
        </button>
        <button className="btn btn-ghost" onClick={state.handleRunPollingOnce} disabled={state.pollingRunning || state.loading}>
          {state.pollingRunning ? '轮询执行中…' : '执行后台轮询'}
        </button>
        <select
          value={state.activeAccount?.auto_mail_policy || 'draft_and_notify'}
          onChange={(e) => state.handlePolicyChange(e.target.value)}
          disabled={!state.activeAccount || state.policySaving || state.loading}
          style={{ maxWidth: 200 }}
        >
          {AUTO_MAIL_POLICY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-ghost" onClick={() => onOpenNotifyNetwork?.()}>账户接线</button>
        <button className="btn btn-ghost" onClick={state.handleAccountTest} disabled={!state.activeAccount || state.accountTesting || state.loading}>
          {state.accountTesting ? '检定中…' : '账户检定'}
        </button>
        <button className="btn btn-primary" onClick={state.openBlankComposer}>写一封信</button>
      </div>

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">活跃线程</div>
          <div className="board-summary-value">{state.dashboard?.total_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">未读线程</div>
          <div className="board-summary-value">{state.dashboard?.unread_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">待回信</div>
          <div className="board-summary-value">{state.dashboard?.needs_reply_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">待你决定</div>
          <div className="board-summary-value">{state.dashboard?.waiting_decision_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">最近同步</div>
          <div className="board-summary-value" style={{ fontSize: '1rem' }}>
            {state.syncStatus?.finished_at ? formatDateTime(state.syncStatus.finished_at) : '尚未拉信'}
          </div>
        </div>
      </div>

      <MailControlGrid
        activeAccount={state.activeAccount}
        accountTestResult={state.accountTestResult}
        accountTesting={state.accountTesting}
        accounts={state.accounts}
        handleAccountTest={state.handleAccountTest}
        handlePollingConfigChange={state.handlePollingConfigChange}
        loading={state.loading}
        pollingFeedback={state.pollingFeedback}
        pollingResults={state.pollingResults}
        pollingSaving={state.pollingSaving}
        pollingState={state.pollingState}
        pollingSummary={state.pollingSummary}
        pollingFolderOptions={POLLING_FOLDER_OPTIONS}
        requestOpenNotifyNetwork={() => onOpenNotifyNetwork?.()}
        setPollingState={state.setPollingState}
        syncStatus={state.syncStatus}
        threadFilters={state.threadFilters}
        setThreadFilters={state.setThreadFilters}
        refreshDeskThreads={state.refreshDeskThreads}
      />

      {state.activeAccount && (
        <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">AUTO HANDLER</div>
              <h3 className="board-lane-title">自动回信策略</h3>
              <div className="board-lane-copy">
                当前账户「{state.activeAccount.display_name}」采用“{getAutoMailPolicyLabel(state.activeAccount.auto_mail_policy)}”。
                这是书信代理的行事准则，决定它在手机端来信抵达后，是只起草、等你确认，还是直接替你寄出。
              </div>
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{state.activeAccount.email_address}</span>
              <span className="badge badge-warning">{getAutoMailPolicyLabel(state.activeAccount.auto_mail_policy)}</span>
            </div>
          </div>
          <div className="signal-row" style={{ marginTop: 'var(--space-md)', alignItems: 'flex-start' }}>
            <div>
              <div className="signal-row-title">当前行为说明</div>
              <div className="signal-row-copy">{getAutoPolicyNarrative(state.activeAccount.auto_mail_policy)}</div>
            </div>
            <button className="btn btn-sm btn-ghost" onClick={() => onOpenNotifyNetwork?.()}>去接线检定页调整</button>
          </div>
        </section>
      )}

      {state.decisionQueue.length > 0 && (
        <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">DECISION QUEUE</div>
              <h3 className="board-lane-title">待你决定</h3>
              <div className="board-lane-copy">有些信不该被立刻埋进归档。它们像黄昏时分的敲门声，等你决定是回信、安排，还是让它稍后再来。</div>
            </div>
          </div>
          <div className="board-card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
            {state.decisionQueue.slice(0, 6).map(thread => (
              <DecisionQueueCard
                key={thread.thread_id}
                thread={thread}
                onOpen={state.setSelectedThreadId}
                onDiscuss={state.handleDiscussWithAi}
                onCreateTask={state.handleCreateTaskFromMail}
              />
            ))}
          </div>
        </section>
      )}

      <div className="war-room-grid mail-spread-grid">
        <div className="war-room-stack">
          <MailRailPanel
            selectedFolder={state.selectedFolder}
            selectedThreadId={state.selectedThreadId}
            selectedThreadIndex={state.selectedThreadIndex}
            threads={state.threads}
            railThread={state.railThread}
            openPrevThread={state.openPrevThread}
            openNextThread={state.openNextThread}
            setSelectedThreadId={state.setSelectedThreadId}
          />
        </div>

        <div className="war-room-stack">
          <OpenLetterPanel
            selectedFolder={state.selectedFolder}
            selectedThread={state.selectedThread}
            selectedThreadAccount={state.selectedThreadAccount}
            selectedMailtoHref={state.selectedMailtoHref}
            threadRefreshing={state.threadRefreshing}
            activeDraft={state.activeDraft}
            latestAgentRun={state.latestAgentRun}
            threadDetail={state.threadDetail}
            selectedAgentRuns={state.selectedAgentRuns}
            agentRunFilter={state.agentRunFilter}
            agentRunsLoading={state.agentRunsLoading}
            openPortalPage={state.openPortalPage}
            copyPortalLink={state.copyPortalLink}
            handleRefreshSelectedThread={state.handleRefreshSelectedThread}
            handleMarkRead={state.handleMarkRead}
            handleArchive={state.handleArchive}
            handleDecisionStatus={state.handleDecisionStatus}
            handleReplyThread={state.handleReplyThread}
            handleGenerateReplyDraft={state.handleGenerateReplyDraft}
            handleCreateTaskFromMail={state.handleCreateTaskFromMail}
            handleDiscussWithAi={state.handleDiscussWithAi}
            fetchAgentRuns={state.fetchAgentRuns}
            setAgentRunFilter={state.setAgentRunFilter}
            onOpenDraftComposer={state.openDraftComposer}
            onSendDraft={state.handleSendDraftFromPanel}
          />
        </div>
      </div>

      <MailComposerModal
        open={state.composerOpen}
        onClose={() => state.setComposerOpen(false)}
        onSubmit={state.handleComposeSubmit}
        composerDraftId={state.composerDraftId}
        composerThreadId={state.composerThreadId}
        composerResetting={state.composerResetting}
        activeDraft={state.activeDraft}
        loading={state.loading}
        draftForm={state.draftForm}
        setDraftForm={state.setDraftForm}
        accounts={state.accounts}
        toneOptions={TONE_OPTIONS}
        onResetToLatestDraft={state.handleResetComposerToLatestDraft}
        onSaveDraftOnly={state.handleSaveDraftOnly}
      />
    </div>
  );
}
