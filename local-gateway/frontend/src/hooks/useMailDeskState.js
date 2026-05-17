import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost, apiPut, useApi } from './useApi';
import { useMailDeskPollingActions } from './useMailDeskPollingActions';
import { useMailDeskThreadActions } from './useMailDeskThreadActions';
import { normalizeList } from '../utils/normalize';
import {
  buildMailtoReplyLink,
  createComposerStateFromDraft,
  getAutoMailPolicyLabel,
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

  const [dashboard, setDashboard] = useState(null);
  const [threads, setThreads] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState('');
  const [selectedFolder, setSelectedFolder] = useState('');
  const [selectedThreadId, setSelectedThreadId] = useState('');
  const [threadDetail, setThreadDetail] = useState(null);
  const [threadDetailLoading, setThreadDetailLoading] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);
  const [accountTesting, setAccountTesting] = useState(false);
  const [accountTestResult, setAccountTestResult] = useState(null);
  const [composerDraftId, setComposerDraftId] = useState('');
  const [composerThreadId, setComposerThreadId] = useState('');
  const [composerResetting, setComposerResetting] = useState(false);
  const [composerSaving, setComposerSaving] = useState(false);
  const [composerSending, setComposerSending] = useState(false);
  const [taskComposerOpen, setTaskComposerOpen] = useState(false);
  const [taskComposerThreadId, setTaskComposerThreadId] = useState('');
  const [taskCreatingThreadId, setTaskCreatingThreadId] = useState('');
  const [agentRunsLoading, setAgentRunsLoading] = useState(false);
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
  const [draftForm, setDraftForm] = useState({
    account_id: '',
    to: '',
    cc: '',
    bcc: '',
    subject: '',
    body_html: '',
    tone_mode: 'warm',
    signature: '',
    scheduled_send_at: '',
  });
  const [taskDraftForm, setTaskDraftForm] = useState({
    task_name: '',
    due_time: '',
    priority: 2,
    description: '',
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

  const syncThreadDetailIntoDesk = useCallback((detail, options = {}) => {
    const summary = deriveThreadSummaryFromDetail(detail);
    if (!summary) {
      return false;
    }
    const { removeWhenFilteredOut = true } = options;
    const matches = matchesThreadFilters(summary);
    setThreads((prev) => {
      const next = [...prev];
      const existingIndex = next.findIndex((item) => item.thread_id === summary.thread_id);
      if (!matches && removeWhenFilteredOut) {
        if (existingIndex >= 0) {
          next.splice(existingIndex, 1);
        }
      } else if (existingIndex >= 0) {
        next[existingIndex] = summary;
      } else {
        next.unshift(summary);
      }
      next.sort((left, right) => {
        const leftTime = Date.parse(left.latest_message_at || left.updated_at || 0) || 0;
        const rightTime = Date.parse(right.latest_message_at || right.updated_at || 0) || 0;
        return rightTime - leftTime;
      });
      return next;
    });
    setThreadDetail((prev) => (prev?.thread?.thread_id === summary.thread_id ? detail : prev));
    return matches;
  }, [deriveThreadSummaryFromDetail, matchesThreadFilters]);

  const openPortalPage = useCallback((thread) => {
    if (!thread?.portal_url) {
      toast('这封信还没有可打开的处理页链接', 'error');
      return;
    }
    window.open(thread.portal_url, '_blank', 'noopener,noreferrer');
  }, [toast]);

  const copyPortalLink = useCallback(async (thread) => {
    if (!thread?.portal_url) {
      toast('这封信还没有可复制的处理页链接', 'error');
      return;
    }
    try {
      await navigator.clipboard.writeText(thread.portal_url);
      toast('处理页链接已复制', 'success');
    } catch {
      toast('复制链接失败', 'error');
    }
  }, [toast]);

  const parseRecipientLine = useCallback((value) => {
    return value
      .split(/[,\n]/)
      .map(item => item.trim())
      .filter(Boolean)
      .map(email => ({ email, name: email.split('@')[0] || email }));
  }, []);

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

  const fetchAccounts = useCallback(async () => {
    const data = await apiGet('/api/mail/accounts');
    const items = normalizeList(data, ['accounts']);
    setAccounts(items);
    setSelectedAccount((current) => current || items[0]?.account_id || '');
    setDraftForm((prev) => ({
      ...prev,
      account_id: prev.account_id || items[0]?.account_id || '',
      signature: prev.signature || items[0]?.signature_text || '',
      tone_mode: prev.tone_mode || items[0]?.tone_mode || 'warm',
    }));
  }, []);

  const fetchDashboard = useCallback(async (accountId = '') => {
    const suffix = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    const data = await apiGet(`/api/mail/dashboard${suffix}`);
    setDashboard(data.summary || null);
  }, []);

  const fetchThreads = useCallback(async (accountId = '', folder = '', preferredThreadId = selectedThreadId) => {
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    if (folder) params.set('folder', folder);
    if (threadFilters.query.trim()) params.set('q', threadFilters.query.trim());
    if (threadFilters.unreadOnly) params.set('unread_only', 'true');
    if (threadFilters.needsReplyOnly) params.set('needs_reply', 'true');
    if (threadFilters.waitingDecisionOnly) params.set('waiting_user_decision', 'true');
    if (threadFilters.scheduledOnly) params.set('scheduled_only', 'true');
    if (threadFilters.failedDraftOnly) params.set('failed_draft_only', 'true');
    const query = params.toString();
    const data = await apiGet(`/api/mail/threads${query ? `?${query}` : ''}`);
    const items = normalizeList(data, ['threads']);
    const resolvedThreadId = preferredThreadId && items.some(item => item.thread_id === preferredThreadId)
      ? preferredThreadId
      : (items[0]?.thread_id || '');
    setThreads(items);
    setSelectedThreadId(resolvedThreadId);
    return { items, selectedThreadId: resolvedThreadId };
  }, [selectedThreadId, threadFilters]);

  const fetchPollingStatus = useCallback(async () => {
    try {
      const data = await apiGet('/api/mail/polling');
      setPollingState((prev) => ({
        ...prev,
        ...(data.polling || {}),
      }));
    } catch {
      setPollingState((prev) => ({
        ...prev,
        last_error: prev.last_error || '轮询状态读取失败',
      }));
    }
  }, []);

  const fetchSyncStatus = useCallback(async (accountId) => {
    if (!accountId) {
      setSyncStatus(null);
      return;
    }
    try {
      const data = await apiGet(`/api/mail/accounts/${accountId}/sync-status`);
      setSyncStatus(data.latest_run || null);
    } catch {
      setSyncStatus(null);
    }
  }, []);

  const fetchThreadDetail = useCallback(async (threadId) => {
    if (!threadId) {
      setThreadDetail(null);
      setThreadDetailLoading(false);
      return;
    }
    setThreadDetailLoading(true);
    setThreadDetail((prev) => (prev?.thread?.thread_id === threadId ? prev : null));
    try {
      const data = await apiGet(`/api/mail/threads/${threadId}`);
      setThreadDetail(data);
    } finally {
      setThreadDetailLoading(false);
    }
  }, []);

  const fetchAgentRuns = useCallback(async (threadId, limit = 20) => {
    if (!threadId) {
      return;
    }
    setAgentRunsLoading(true);
    try {
      const data = await apiGet(`/api/mail/threads/${threadId}/agent-runs?limit=${limit}`);
      setThreadDetail((prev) => {
        if (!prev || prev.thread?.thread_id !== threadId) {
          return prev;
        }
        return {
          ...prev,
          agent_runs: data.agent_runs || [],
        };
      });
    } finally {
      setAgentRunsLoading(false);
    }
  }, []);

  const refreshAll = useCallback(async (accountId = selectedAccount, folder = selectedFolder, preferredThreadId = selectedThreadId) => {
    const [, threadsInfo] = await Promise.all([
      fetchAccounts(),
      fetchDashboard(accountId),
      fetchThreads(accountId, folder, preferredThreadId),
      fetchSyncStatus(accountId),
      fetchPollingStatus(),
    ]);
    return threadsInfo;
  }, [fetchAccounts, fetchDashboard, fetchThreads, fetchSyncStatus, fetchPollingStatus, selectedAccount, selectedFolder, selectedThreadId]);

  const refreshDeskSnapshot = useCallback(async (accountId = selectedAccount, folder = selectedFolder, preferredThreadId = selectedThreadId) => {
    const [, threadsInfo] = await Promise.all([
      fetchDashboard(accountId),
      fetchThreads(accountId, folder, preferredThreadId),
      fetchSyncStatus(accountId),
    ]);
    return threadsInfo;
  }, [fetchDashboard, fetchThreads, fetchSyncStatus, selectedAccount, selectedFolder, selectedThreadId]);

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
      }));
    }
  }, [activeAccount]);

  useEffect(() => {
    if (!quickAction) return;
    if (quickAction.type === 'notify_network_ready') {
      refreshAll();
      clearQuickAction?.();
    }
  }, [quickAction, clearQuickAction, refreshAll]);

  const resetComposer = useCallback(() => {
    setComposerDraftId('');
    setComposerThreadId('');
    setDraftForm((prev) => ({
      ...prev,
      account_id: activeAccount?.account_id || prev.account_id,
      to: '',
      cc: '',
      bcc: '',
      subject: '',
      body_html: '',
      tone_mode: activeAccount?.tone_mode || 'warm',
      signature: activeAccount?.signature_text || '',
      scheduled_send_at: '',
    }));
  }, [activeAccount]);

  const hydrateComposerFromDraft = useCallback((draft, thread = null) => {
    setComposerDraftId(draft?.draft_id || '');
    setComposerThreadId(draft?.thread_id || thread?.thread_id || '');
    setDraftForm(createComposerStateFromDraft(draft, thread, activeAccount));
  }, [activeAccount]);

  const openDraftComposer = useCallback((draft, thread = null) => {
    hydrateComposerFromDraft(draft, thread);
    setComposerOpen(true);
  }, [hydrateComposerFromDraft]);

  const openTaskComposer = useCallback((thread) => {
    if (!thread?.thread_id) {
      toast('当前没有可落成任务的邮件线程', 'warning');
      return;
    }
    setTaskComposerThreadId(thread.thread_id);
    setTaskDraftForm(createTaskDraftFromThread(thread));
    setTaskComposerOpen(true);
  }, [createTaskDraftFromThread, toast]);

  const createDraftPayload = useCallback(() => ({
    account_id: draftForm.account_id,
    subject: draftForm.subject.trim(),
    body_html: draftForm.body_html.trim().replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\n/g, '<br>'),
    to: parseRecipientLine(draftForm.to),
    cc: parseRecipientLine(draftForm.cc),
    bcc: parseRecipientLine(draftForm.bcc),
    thread_id: composerThreadId || undefined,
    tone_mode: draftForm.tone_mode,
    signature: draftForm.signature,
    scheduled_send_at: draftForm.scheduled_send_at ? new Date(draftForm.scheduled_send_at).toISOString() : null,
    user_edited_after_ai: true,
  }), [composerThreadId, draftForm, parseRecipientLine]);

  const ensureDraftSaved = useCallback(async () => {
    const payload = createDraftPayload();
    if (composerDraftId) {
      const updated = await request(() => apiPut(`/api/mail/drafts/${composerDraftId}`, payload));
      const nextThreadId = updated.thread?.thread_id || updated.thread_id || composerThreadId;
      setComposerThreadId(nextThreadId || '');
      return { draft_id: composerDraftId, thread_id: nextThreadId };
    }

    const created = await request(() => apiPost('/api/mail/drafts', payload));
    setComposerDraftId(created.draft_id || '');
    setComposerThreadId(created.thread_id || '');
    return { draft_id: created.draft_id, thread_id: created.thread_id };
  }, [composerDraftId, composerThreadId, createDraftPayload, request]);

  const handleComposeSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (!draftForm.account_id) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    if (!draftForm.subject.trim()) {
      toast('请填写主题', 'warning');
      return;
    }
    if (!draftForm.to.trim()) {
      toast('请填写至少一个收件人', 'warning');
      return;
    }
    setComposerSending(true);
    try {
      const draft = await ensureDraftSaved();
      await request(() => apiPost(`/api/mail/drafts/${draft.draft_id}/send`, {}));
      toast('信已经寄出', 'success');
      setComposerOpen(false);
      resetComposer();
      await refreshDeskSnapshot(draftForm.account_id, selectedFolder);
      setSelectedThreadId(draft.thread_id);
    } catch (e2) {
      toast(e2.message || '寄信失败', 'error');
    } finally {
      setComposerSending(false);
    }
  }, [draftForm.account_id, draftForm.subject, draftForm.to, ensureDraftSaved, refreshDeskSnapshot, request, resetComposer, selectedFolder, toast]);

  const handleSaveDraftOnly = useCallback(async () => {
    if (!draftForm.account_id) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    if (!draftForm.subject.trim()) {
      toast('请填写主题', 'warning');
      return;
    }
    setComposerSaving(true);
    try {
      const draft = await ensureDraftSaved();
      toast(composerDraftId ? '草稿已经更新' : '草稿已经放回案头', 'success');
      if (draft.thread_id) {
        setSelectedThreadId(draft.thread_id);
        const detail = await apiGet(`/api/mail/threads/${draft.thread_id}`);
        syncThreadDetailIntoDesk(detail);
        await fetchDashboard(draftForm.account_id);
      }
    } catch (e) {
      toast(e.message || '保存草稿失败', 'error');
    } finally {
      setComposerSaving(false);
    }
  }, [composerDraftId, draftForm.account_id, draftForm.subject, ensureDraftSaved, fetchDashboard, syncThreadDetailIntoDesk, toast]);

  const handleSyncInbox = useCallback(async () => {
    if (!selectedAccount) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    setSyncing(true);
    try {
      const data = await request(() => apiPost(`/api/mail/accounts/${selectedAccount}/sync?folder_kind=inbox&limit=20`, {}));
      toast(`收件箱已同步，新增 ${data.new_count ?? 0} 封信`, 'success');
      const threadsInfo = await refreshDeskSnapshot(selectedAccount, selectedFolder, selectedThreadId);
      if (threadsInfo?.selectedThreadId && threadsInfo.selectedThreadId === selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '同步收件箱失败', 'error');
    } finally {
      setSyncing(false);
    }
  }, [fetchThreadDetail, refreshDeskSnapshot, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  const handleAccountTest = useCallback(async () => {
    if (!activeAccount?.account_id) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    setAccountTesting(true);
    setAccountTestResult(null);
    try {
      const result = await request(() => apiPost(`/api/mail/accounts/${activeAccount.account_id}/test`, {}));
      setAccountTestResult(result);
      toast(result.status === 'success' ? '账户链路检定通过' : '账户链路检定失败', result.status === 'success' ? 'success' : 'error');
    } catch (e) {
      setAccountTestResult({ status: 'error', message: e.message || '链路检定失败' });
      toast(e.message || '账户链路检定失败', 'error');
    } finally {
      setAccountTesting(false);
    }
  }, [activeAccount, request, toast]);

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

  const handleCreateTaskFromMail = useCallback(async (thread) => {
    openTaskComposer(thread);
  }, [openTaskComposer]);

  const handleSubmitTaskFromMail = useCallback(async (e) => {
    e?.preventDefault?.();
    if (!taskComposerThread?.thread_id) {
      toast('当前没有可关联的邮件线程', 'warning');
      return;
    }
    if (!taskDraftForm.task_name.trim()) {
      toast('请先写下任务标题', 'warning');
      return;
    }
    setTaskCreatingThreadId(taskComposerThread.thread_id);
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${taskComposerThread.thread_id}/create-task`, {
        task_name: taskDraftForm.task_name.trim(),
        due_time: taskDraftForm.due_time ? new Date(taskDraftForm.due_time).toISOString() : null,
        description: taskDraftForm.description.trim(),
        priority: Number(taskDraftForm.priority),
      }));
      toast(`已落成任务：${data.task_name}`, 'success');
      syncThreadDetailIntoDesk(data, { removeWhenFilteredOut: false });
      setTaskComposerOpen(false);
      setTaskComposerThreadId('');
    } catch (e) {
      toast(e.message || '从邮件创建任务失败', 'error');
    } finally {
      setTaskCreatingThreadId('');
    }
  }, [request, syncThreadDetailIntoDesk, taskComposerThread, taskDraftForm, toast]);

  const handleReplyThread = useCallback((thread) => {
    if (!thread) {
      return;
    }
    if (activeDraft) {
      openDraftComposer(activeDraft, thread);
      return;
    }
    resetComposer();
    setComposerThreadId(thread.thread_id);
    setComposerOpen(true);
    const latestInbound = (threadDetail?.messages || []).filter(item => item.direction === 'inbound').slice(-1)[0];
    setDraftForm(prev => ({
      ...prev,
      account_id: thread.account_id,
      subject: thread.subject.startsWith('Re:') ? thread.subject : `Re: ${thread.subject}`,
      to: latestInbound?.from_email || '',
      signature: activeAccount?.signature_text || prev.signature,
    }));
  }, [activeAccount, activeDraft, openDraftComposer, resetComposer, threadDetail]);

  const handleResetComposerToLatestDraft = useCallback(async () => {
    const threadId = composerThreadId || selectedThreadId;
    if (!composerDraftId || !threadId) {
      toast('当前没有可回退的已保存草稿', 'warning');
      return;
    }
    setComposerResetting(true);
    try {
      const data = await request(() => apiGet(`/api/mail/threads/${threadId}`));
      const latestDraft = (data.drafts || []).find((draft) => draft.status !== 'sent' && draft.draft_id === composerDraftId)
        || (data.drafts || []).find((draft) => draft.status !== 'sent');
      if (!latestDraft) {
        toast('服务器上已经没有这份待发草稿了', 'warning');
        return;
      }
      setThreadDetail((prev) => (prev?.thread?.thread_id === threadId ? data : prev));
      hydrateComposerFromDraft(latestDraft, data.thread || selectedThread);
      toast('已回到服务器上的最新草稿版本', 'success');
    } catch (e) {
      toast(e.message || '重置草稿失败', 'error');
    } finally {
      setComposerResetting(false);
    }
  }, [composerDraftId, composerThreadId, hydrateComposerFromDraft, request, selectedThread, selectedThreadId, toast]);

  const handlePolicyChange = useCallback(async (nextPolicy) => {
    if (!activeAccount?.account_id || nextPolicy === activeAccount.auto_mail_policy) {
      return;
    }
    setPolicySaving(true);
    try {
      await request(() => apiPut(`/api/mail/accounts/${activeAccount.account_id}`, {
        auto_mail_policy: nextPolicy,
      }));
      toast(`自动处理已切到“${getAutoMailPolicyLabel(nextPolicy)}”`, 'success');
      await refreshAll(selectedAccount, selectedFolder, selectedThreadId);
    } catch (e) {
      toast(e.message || '更新自动处理策略失败', 'error');
    } finally {
      setPolicySaving(false);
    }
  }, [activeAccount, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

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

  const openBlankComposer = useCallback(() => {
    resetComposer();
    setComposerOpen(true);
  }, [resetComposer]);

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
