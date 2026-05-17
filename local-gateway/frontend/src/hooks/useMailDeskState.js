import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost, apiPut, useApi } from './useApi';
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
  const [composerOpen, setComposerOpen] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);
  const [pollingSaving, setPollingSaving] = useState(false);
  const [pollingRunning, setPollingRunning] = useState(false);
  const [threadRefreshing, setThreadRefreshing] = useState(false);
  const [accountTesting, setAccountTesting] = useState(false);
  const [accountTestResult, setAccountTestResult] = useState(null);
  const [composerDraftId, setComposerDraftId] = useState('');
  const [composerThreadId, setComposerThreadId] = useState('');
  const [composerResetting, setComposerResetting] = useState(false);
  const [agentRunsLoading, setAgentRunsLoading] = useState(false);
  const [agentRunFilter, setAgentRunFilter] = useState('all');
  const [pollingFeedback, setPollingFeedback] = useState(null);
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

  const fetchThreads = useCallback(async (accountId = '', folder = '') => {
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    if (folder) params.set('folder', folder);
    if (threadFilters.query.trim()) params.set('q', threadFilters.query.trim());
    if (threadFilters.unreadOnly) params.set('unread_only', 'true');
    if (threadFilters.needsReplyOnly) params.set('needs_reply', 'true');
    if (threadFilters.waitingDecisionOnly) params.set('waiting_user_decision', 'true');
    const query = params.toString();
    const data = await apiGet(`/api/mail/threads${query ? `?${query}` : ''}`);
    const items = normalizeList(data, ['threads']);
    setThreads(items);
    setSelectedThreadId((current) => (
      current && items.some(item => item.thread_id === current)
        ? current
        : (items[0]?.thread_id || '')
    ));
  }, [threadFilters]);

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
      return;
    }
    const data = await apiGet(`/api/mail/threads/${threadId}`);
    setThreadDetail(data);
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

  const refreshAll = useCallback(async (accountId = selectedAccount, folder = selectedFolder) => {
    await Promise.all([
      fetchAccounts(),
      fetchDashboard(accountId),
      fetchThreads(accountId, folder),
      fetchSyncStatus(accountId),
      fetchPollingStatus(),
    ]);
  }, [fetchAccounts, fetchDashboard, fetchThreads, fetchSyncStatus, fetchPollingStatus, selectedAccount, selectedFolder]);

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
    try {
      const draft = await ensureDraftSaved();
      await request(() => apiPost(`/api/mail/drafts/${draft.draft_id}/send`, {}));
      toast('信已经寄出', 'success');
      setComposerOpen(false);
      resetComposer();
      await refreshAll(draftForm.account_id, selectedFolder);
      setSelectedThreadId(draft.thread_id);
    } catch (e2) {
      toast(e2.message || '寄信失败', 'error');
    }
  }, [draftForm.account_id, draftForm.subject, draftForm.to, ensureDraftSaved, refreshAll, request, resetComposer, selectedFolder, toast]);

  const handleSaveDraftOnly = useCallback(async () => {
    if (!draftForm.account_id) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    if (!draftForm.subject.trim()) {
      toast('请填写主题', 'warning');
      return;
    }
    try {
      const draft = await ensureDraftSaved();
      toast(composerDraftId ? '草稿已经更新' : '草稿已经放回案头', 'success');
      await refreshAll(draftForm.account_id, selectedFolder);
      if (draft.thread_id) {
        setSelectedThreadId(draft.thread_id);
        await fetchThreadDetail(draft.thread_id);
      }
    } catch (e) {
      toast(e.message || '保存草稿失败', 'error');
    }
  }, [composerDraftId, draftForm.account_id, draftForm.subject, ensureDraftSaved, fetchThreadDetail, refreshAll, selectedFolder, toast]);

  const handleArchive = useCallback(async (threadId) => {
    try {
      await request(() => apiPost(`/api/mail/threads/${threadId}/archive`, {}));
      toast('这封信已收进归档夹', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedFolder !== 'archive' && selectedThreadId === threadId) {
        setSelectedThreadId('');
        setThreadDetail(null);
      } else if (selectedThreadId === threadId) {
        await fetchThreadDetail(threadId);
      }
    } catch (e) {
      toast(e.message || '归档失败', 'error');
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  const handleMarkRead = useCallback(async (threadId) => {
    try {
      await request(() => apiPost(`/api/mail/threads/${threadId}/mark-read`, {}));
      toast('已把这封信翻到已读一侧', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId === threadId) {
        await fetchThreadDetail(threadId);
      }
    } catch (e) {
      toast(e.message || '标记已读失败', 'error');
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  const handleSyncInbox = useCallback(async () => {
    if (!selectedAccount) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    setSyncing(true);
    try {
      const data = await request(() => apiPost(`/api/mail/accounts/${selectedAccount}/sync?folder_kind=inbox&limit=20`, {}));
      toast(`收件箱已同步，新增 ${data.new_count ?? 0} 封信`, 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '同步收件箱失败', 'error');
    } finally {
      setSyncing(false);
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  const handleRunPollingOnce = useCallback(async () => {
    setPollingRunning(true);
    try {
      const data = await request(() => apiPost('/api/mail/polling/run-once', {}));
      const summary = data.polling?.last_summary || {};
      toast(`轮询已执行，新增 ${summary.new_count ?? 0} 封信`, 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '执行轮询失败', 'error');
    } finally {
      setPollingRunning(false);
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  const handlePollingConfigChange = useCallback(async (patch) => {
    setPollingSaving(true);
    const nextState = { ...pollingState, ...patch };
    setPollingState(nextState);
    try {
      const result = await request(() => apiPut('/api/mail/polling', {
        enabled: nextState.enabled,
        interval_seconds: Number(nextState.interval_seconds),
        folder_kind: nextState.folder_kind,
        limit: Number(nextState.limit),
      }));
      setPollingState((prev) => ({ ...prev, ...(result.polling || {}) }));
      setPollingFeedback({
        tone: 'success',
        message: patch.enabled !== undefined
          ? (nextState.enabled ? '后台轮询已开启，配置已写回执行器' : '后台轮询已关闭，配置已写回执行器')
          : '轮询配置已保存，后续执行会采用这一版参数',
        savedAt: new Date().toISOString(),
      });
      toast(nextState.enabled ? '后台轮询已经接通' : '后台轮询已经停下', 'success');
    } catch (e) {
      setPollingFeedback({
        tone: 'error',
        message: e.message || '更新轮询配置失败',
        savedAt: '',
      });
      toast(e.message || '更新轮询配置失败', 'error');
      await fetchPollingStatus();
    } finally {
      setPollingSaving(false);
    }
  }, [fetchPollingStatus, pollingState, request, toast]);

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

  const handleDecisionStatus = useCallback(async (threadId, decisionStatus) => {
    try {
      await request(() => apiPost(`/api/mail/threads/${threadId}/decision`, { decision_status: decisionStatus }));
      toast(decisionStatus === 'snoozed' ? '这封信稍后再来叩门' : '这封信先从待裁决队列退下', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId === threadId) {
        await fetchThreadDetail(threadId);
      }
    } catch (e) {
      toast(e.message || '更新决策状态失败', 'error');
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

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
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${thread.thread_id}/create-task`, {
        task_name: `邮件跟进：${thread.subject}`,
        priority: thread.risk_level === 'high' ? 1 : 2,
      }));
      toast(`已落成任务：${data.task_name}`, 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId === thread.thread_id) {
        await fetchThreadDetail(thread.thread_id);
      }
    } catch (e) {
      toast(e.message || '从邮件创建任务失败', 'error');
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  const handleGenerateReplyDraft = useCallback(async (thread) => {
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${thread.thread_id}/generate-reply-draft`, {}));
      const latestDraft = (data.drafts || [])[0];
      if (latestDraft) {
        openDraftComposer(latestDraft, thread);
      }
      setSelectedThreadId(thread.thread_id);
      toast(data.draft_source === 'ai' ? 'AI 已替你起草回信' : '已生成模板回信草稿', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      await fetchThreadDetail(thread.thread_id);
    } catch (e) {
      toast(e.message || '生成回信草稿失败', 'error');
    }
  }, [fetchThreadDetail, openDraftComposer, refreshAll, request, selectedAccount, selectedFolder, toast]);

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

  const handleSendDraftFromPanel = useCallback(async (draft) => {
    if (!draft?.draft_id || !selectedThread?.thread_id) {
      return;
    }
    try {
      await request(() => apiPost(`/api/mail/drafts/${draft.draft_id}/send`, {}));
      toast('这份草稿已经寄出', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      await fetchThreadDetail(selectedThread.thread_id);
    } catch (e) {
      toast(e.message || '发送草稿失败', 'error');
    }
  }, [fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThread, toast]);

  const handleRefreshSelectedThread = useCallback(async (threadId = selectedThreadId) => {
    if (!threadId) {
      return;
    }
    setThreadRefreshing(true);
    try {
      await Promise.all([
        fetchDashboard(selectedAccount),
        fetchThreads(selectedAccount, selectedFolder),
        fetchThreadDetail(threadId),
      ]);
      toast('这封信的当前内容已经刷新', 'success');
    } catch (e) {
      toast(e.message || '刷新当前线程失败', 'error');
    } finally {
      setThreadRefreshing(false);
    }
  }, [fetchDashboard, fetchThreadDetail, fetchThreads, selectedAccount, selectedFolder, selectedThreadId, toast]);

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
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '更新自动处理策略失败', 'error');
    } finally {
      setPolicySaving(false);
    }
  }, [activeAccount, fetchThreadDetail, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

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
    composerOpen,
    setComposerOpen,
    policySaving,
    pollingSaving,
    pollingRunning,
    threadRefreshing,
    accountTesting,
    accountTestResult,
    composerDraftId,
    composerThreadId,
    composerResetting,
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
    handleGenerateReplyDraft,
    handleReplyThread,
    handleSendDraftFromPanel,
    handleRefreshSelectedThread,
    handleResetComposerToLatestDraft,
    handlePolicyChange,
    openPrevThread,
    openNextThread,
    openBlankComposer,
  };
}
