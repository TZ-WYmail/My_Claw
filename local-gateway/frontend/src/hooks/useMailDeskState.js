import { useCallback, useEffect, useMemo, useState } from 'react';
import { useApi } from './useApi';
import { useMailDeskAccountActions } from './useMailDeskAccountActions';
import { useMailDeskComposer } from './useMailDeskComposer';
import { useMailDeskData } from './useMailDeskData';
import { useMailDeskPollingActions } from './useMailDeskPollingActions';
import { useMailDeskThreadActions } from './useMailDeskThreadActions';
import {
  buildMailtoReplyLink,
  getMailKindLabel,
  getReplyLevelLabel,
} from '../components/maildesk/maildeskShared.jsx';

export function useMailDeskState({
  quickAction = null,
  clearQuickAction = null,
  onOpenAi = null,
  toast,
}) {
  const { loading, request } = useApi();

  const [selectedAccount, setSelectedAccount] = useState('');
  const [selectedFolder, setSelectedFolder] = useState('');
  const [selectedThreadId, setSelectedThreadId] = useState('');
  const [taskComposerThreadId, setTaskComposerThreadId] = useState('');
  const [agentRunFilter, setAgentRunFilter] = useState('all');
  const [pollingState, setPollingState] = useState({
    enabled: false,
    interval_seconds: 300,
    folder_kind: 'inbox',
    limit: 20,
    is_running: false,
    last_started_at: '',
    last_finished_at: '',
    last_success_at: '',
    last_error: '',
    last_summary: null,
  });
  const [threadFilters, setThreadFilters] = useState({
    query: '',
    unreadOnly: false,
    needsReplyOnly: false,
    waitingDecisionOnly: false,
    scheduledOnly: false,
    failedDraftOnly: false,
  });

  const matchesThreadFilters = useCallback((thread) => {
    if (!thread) {
      return false;
    }
    if (selectedAccount && thread.account_id !== selectedAccount) {
      return false;
    }
    if (selectedFolder) {
      if (thread.latest_folder_kind !== selectedFolder) {
        return false;
      }
    } else if (thread.latest_folder_kind === 'archive') {
      return false;
    }
    const query = threadFilters.query.trim().toLowerCase();
    if (query) {
      const participants = (thread.participants || [])
        .map((item) => `${item.name || ''} ${item.email || ''}`.trim())
        .join(' ')
        .toLowerCase();
      const haystack = [thread.subject, thread.snippet, participants].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(query)) {
        return false;
      }
    }
    if (threadFilters.unreadOnly && !thread.unread_count) {
      return false;
    }
    if (threadFilters.needsReplyOnly && !thread.needs_reply) {
      return false;
    }
    if (threadFilters.waitingDecisionOnly && !thread.waiting_user_decision) {
      return false;
    }
    if (threadFilters.scheduledOnly && !thread.latest_draft_scheduled_send_at) {
      return false;
    }
    if (threadFilters.failedDraftOnly && thread.latest_draft_status !== 'failed') {
      return false;
    }
    return true;
  }, [selectedAccount, selectedFolder, threadFilters]);

  const deriveThreadSummaryFromDetail = useCallback((detail) => {
    if (!detail?.thread) {
      return null;
    }
    const pendingDrafts = (detail.drafts || []).filter((draft) => draft.status !== 'sent');
    const latestPendingDraft = pendingDrafts[0] || null;
    return {
      ...detail.thread,
      has_draft: pendingDrafts.length > 0,
      has_pending_draft: pendingDrafts.length > 0,
      latest_draft_scheduled_send_at: latestPendingDraft?.scheduled_send_at || '',
      latest_draft_status: latestPendingDraft?.status || '',
    };
  }, []);

  const {
    dashboard,
    threads,
    accounts,
    syncStatus,
    threadDetail,
    setThreadDetail,
    threadDetailLoading,
    agentRunsLoading,
    fetchAccounts,
    fetchDashboard,
    fetchThreads,
    fetchPollingStatus,
    fetchSyncStatus,
    fetchThreadDetail,
    fetchAgentRuns,
    refreshAll,
    refreshDeskSnapshot,
    syncThreadDetailIntoDesk,
  } = useMailDeskData({
    selectedAccount,
    selectedFolder,
    selectedThreadId,
    threadFilters,
    setPollingState,
    deriveThreadSummaryFromDetail,
    matchesThreadFilters,
    setSelectedThreadId,
  });

  const activeAccount = accounts.find(item => item.account_id === selectedAccount) || accounts[0] || null;
  const activeDraft = useMemo(
    () => (threadDetail?.drafts || []).find((draft) => draft.status !== 'sent') || null,
    [threadDetail],
  );
  const pollingSummary = pollingState.last_summary || null;
  const pollingResults = pollingSummary?.results || [];
  const selectedAgentRuns = useMemo(() => {
    const runs = threadDetail?.agent_runs || [];
    if (agentRunFilter === 'all') return runs;
    return runs.filter((run) => run.status === agentRunFilter);
  }, [agentRunFilter, threadDetail]);
  const decisionQueue = useMemo(
    () => threads.filter(item => item.waiting_user_decision && item.latest_folder_kind !== 'archive'),
    [threads],
  );
  const selectedThreadIndex = useMemo(
    () => threads.findIndex(item => item.thread_id === selectedThreadId),
    [threads, selectedThreadId],
  );
  const railThread = threads[selectedThreadIndex >= 0 ? selectedThreadIndex : 0] || null;
  const selectedThread = threadDetail?.thread || threads.find(item => item.thread_id === selectedThreadId) || null;
  const taskComposerThread = useMemo(
    () => threads.find((item) => item.thread_id === taskComposerThreadId) || (selectedThread?.thread_id === taskComposerThreadId ? selectedThread : null),
    [selectedThread, taskComposerThreadId, threads],
  );
  const selectedMailtoHref = useMemo(
    () => buildMailtoReplyLink(selectedThread, threadDetail, activeDraft),
    [activeDraft, selectedThread, threadDetail],
  );
  const selectedThreadAccount = useMemo(
    () => accounts.find((item) => item.account_id === selectedThread?.account_id) || null,
    [accounts, selectedThread],
  );
  const latestAgentRun = useMemo(
    () => (threadDetail?.agent_runs || [])[0] || null,
    [threadDetail],
  );

  const createTaskDraftFromThread = useCallback((thread) => {
    const sourceDetail = thread?.thread_id && thread?.thread_id === selectedThreadId ? threadDetail : null;
    const latestInbound = (sourceDetail?.messages || []).filter((item) => item.direction === 'inbound').slice(-1)[0];
    const descriptionParts = [
      thread?.analysis_reason ? `参谋判断：${thread.analysis_reason}` : '',
      thread?.snippet ? `邮件摘要：${thread.snippet}` : '',
      latestInbound?.text_body ? `最近来信：${latestInbound.text_body.slice(0, 400)}` : '',
    ].filter(Boolean);
    return {
      task_name: `邮件跟进：${thread?.subject || '未命名来信'}`,
      due_time: '',
      priority: thread?.risk_level === 'high' ? 1 : 2,
      description: descriptionParts.join('\n\n'),
    };
  }, [selectedThreadId, threadDetail]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    fetchDashboard(selectedAccount);
    fetchThreads(selectedAccount, selectedFolder);
    fetchSyncStatus(selectedAccount);
  }, [fetchDashboard, fetchThreads, fetchSyncStatus, selectedAccount, selectedFolder]);

  useEffect(() => {
    fetchThreadDetail(selectedThreadId);
  }, [fetchThreadDetail, selectedThreadId]);

  useEffect(() => {
    setAgentRunFilter('all');
  }, [selectedThreadId]);

  useEffect(() => {
    if (activeAccount) {
      setDraftForm((prev) => ({
        ...prev,
        account_id: prev.account_id || activeAccount.account_id,
        signature: prev.signature || activeAccount.signature_text || '',
        tone_mode: prev.tone_mode || activeAccount.tone_mode || 'warm',
      }));
    }
  }, [activeAccount]);

  useEffect(() => {
    if (accounts.length > 0 && !selectedAccount) {
      setSelectedAccount(accounts[0].account_id || '');
    }
  }, [accounts, selectedAccount]);

  useEffect(() => {
    if (!quickAction) return;
    if (quickAction.type === 'notify_network_ready') {
      refreshAll();
      clearQuickAction?.();
    }
  }, [quickAction, clearQuickAction, refreshAll]);

  const handleDiscussWithAi = useCallback((thread) => {
    const latestMessage = thread.thread_id === selectedThreadId
      ? (threadDetail?.messages || []).slice(-1)[0]
      : null;
    const participants = (thread.participants || []).map(item => item.email || item.name).filter(Boolean).join(', ');
    const summary = latestMessage?.text_body || latestMessage?.html_body || thread.snippet || '';
    onOpenAi?.({
      intent: 'mail_consult',
      thread,
      draftInput: `请作为书信参谋，帮我处理这封邮件。\n主题：${thread.subject}\n分类：${getMailKindLabel(thread.mail_kind)}\n回信强度：${getReplyLevelLabel(thread.reply_level)}\n判断理由：${thread.analysis_reason || '暂无'}\n相关参与者：${participants || '未记录'}\n邮件摘要：${summary.slice(0, 1200)}\n\n请输出：\n1. 我是否必须回复\n2. 若回复，给出建议语气与核心要点\n3. 若涉及安排，请给出任务/日程建议`,
    });
  }, [onOpenAi, selectedThreadId, threadDetail]);

  const openPrevThread = useCallback(() => {
    if (selectedThreadIndex > 0) {
      setSelectedThreadId(threads[selectedThreadIndex - 1].thread_id);
    }
  }, [selectedThreadIndex, threads]);

  const openNextThread = useCallback(() => {
    if (selectedThreadIndex >= 0 && selectedThreadIndex < threads.length - 1) {
      setSelectedThreadId(threads[selectedThreadIndex + 1].thread_id);
    }
  }, [selectedThreadIndex, threads]);

  const {
    syncing,
    policySaving,
    accountTesting,
    accountTestResult,
    openPortalPage,
    copyPortalLink,
    handleSyncInbox,
    handleAccountTest,
    handlePolicyChange,
  } = useMailDeskAccountActions({
    request,
    toast,
    activeAccount,
    selectedAccount,
    selectedFolder,
    selectedThreadId,
    refreshAll,
    refreshDeskSnapshot,
    fetchThreadDetail,
  });

  const {
    composerOpen,
    setComposerOpen,
    composerDraftId,
    composerThreadId,
    composerResetting,
    composerSaving,
    composerSending,
    taskComposerOpen,
    setTaskComposerOpen,
    taskCreatingThreadId,
    draftForm,
    setDraftForm,
    taskDraftForm,
    setTaskDraftForm,
    openDraftComposer,
    openBlankComposer,
    openTaskComposer,
    handleComposeSubmit,
    handleSaveDraftOnly,
    handleCreateTaskFromMail,
    handleSubmitTaskFromMail,
    handleReplyThread,
    handleResetComposerToLatestDraft,
  } = useMailDeskComposer({
    request,
    toast,
    activeAccount,
    activeDraft,
    selectedFolder,
    selectedThread,
    selectedThreadId,
    threadDetail,
    taskComposerThreadId,
    setTaskComposerThreadId,
    taskComposerThread,
    refreshDeskSnapshot,
    fetchDashboard,
    syncThreadDetailIntoDesk,
    setSelectedThreadId,
    setThreadDetail,
    createTaskDraftFromThread,
  });

  const {
    pollingSaving,
    pollingRunning,
    deskRefreshing,
    pollingFeedback,
    handleRunPollingOnce,
    handlePollingConfigChange,
    refreshDeskThreads,
  } = useMailDeskPollingActions({
    request,
    toast,
    pollingState,
    setPollingState,
    fetchPollingStatus,
    refreshDeskSnapshot,
    fetchThreadDetail,
    selectedAccount,
    selectedFolder,
    selectedThreadId,
  });

  const {
    archivingThreadId,
    markingReadThreadId,
    decisionUpdating,
    replyDraftGeneratingThreadId,
    draftSendingId,
    threadRefreshing,
    handleArchive,
    handleMarkRead,
    handleDecisionStatus,
    handleGenerateReplyDraft,
    handleSendDraftFromPanel,
    handleRefreshSelectedThread,
  } = useMailDeskThreadActions({
    request,
    toast,
    syncThreadDetailIntoDesk,
    fetchDashboard,
    fetchThreads,
    fetchThreadDetail,
    refreshDeskSnapshot,
    openDraftComposer,
    selectedAccount,
    selectedFolder,
    selectedThreadId,
    selectedThread,
    setSelectedThreadId,
    setThreadDetail,
  });

  return {
    loading,
    dashboard,
    threads,
    accounts,
    syncStatus,
    syncing,
    selectedAccount,
    setSelectedAccount,
    selectedFolder,
    setSelectedFolder,
    selectedThreadId,
    setSelectedThreadId,
    threadDetail,
    threadDetailLoading,
    composerOpen,
    setComposerOpen,
    policySaving,
    pollingSaving,
    pollingRunning,
    deskRefreshing,
    threadRefreshing,
    accountTesting,
    accountTestResult,
    composerDraftId,
    composerThreadId,
    composerResetting,
    composerSaving,
    composerSending,
    taskComposerOpen,
    setTaskComposerOpen,
    taskComposerThread,
    taskComposerThreadId,
    archivingThreadId,
    markingReadThreadId,
    decisionUpdating,
    replyDraftGeneratingThreadId,
    taskCreatingThreadId,
    draftSendingId,
    agentRunsLoading,
    agentRunFilter,
    setAgentRunFilter,
    pollingFeedback,
    pollingState,
    setPollingState,
    threadFilters,
    setThreadFilters,
    draftForm,
    setDraftForm,
    taskDraftForm,
    setTaskDraftForm,
    activeAccount,
    activeDraft,
    pollingSummary,
    pollingResults,
    selectedAgentRuns,
    decisionQueue,
    selectedThreadIndex,
    railThread,
    selectedThread,
    selectedMailtoHref,
    selectedThreadAccount,
    latestAgentRun,
    openPortalPage,
    copyPortalLink,
    refreshAll,
    openDraftComposer,
    openTaskComposer,
    fetchThreadDetail,
    fetchAgentRuns,
    handleComposeSubmit,
    handleSaveDraftOnly,
    handleArchive,
    handleMarkRead,
    handleSyncInbox,
    handleRunPollingOnce,
    handlePollingConfigChange,
    handleAccountTest,
    handleDecisionStatus,
    handleDiscussWithAi,
    handleCreateTaskFromMail,
    handleSubmitTaskFromMail,
    handleGenerateReplyDraft,
    handleReplyThread,
    handleSendDraftFromPanel,
    handleRefreshSelectedThread,
    refreshDeskThreads,
    handleResetComposerToLatestDraft,
    handlePolicyChange,
    openPrevThread,
    openNextThread,
    openBlankComposer,
  };
}
