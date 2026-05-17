import { useState, useEffect, useCallback, useMemo } from 'react';
import { useApi, apiGet, apiPost, apiPut } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { normalizeList } from '../utils/normalize';
import MailComposerModal from '../components/maildesk/MailComposerModal';
import OpenLetterPanel from '../components/maildesk/OpenLetterPanel';
import {
  ArchiveThreadRow,
  buildMailtoReplyLink,
  createComposerStateFromDraft,
  DecisionQueueCard,
  formatDateTime,
  getAgentRunFilterLabel,
  getAgentRunReasonLabel,
  getAgentRunStatusBadge,
  getAgentRunStatusLabel,
  getAutoMailPolicyLabel,
  getAutoPolicyNarrative,
  getDecisionStatusLabel,
  getExecutionBadgeClass,
  getExecutionStatusLabel,
  getInboxLabel,
  getMailCommandLabel,
  getMailKindLabel,
  getReplyLevelLabel,
  getRiskBadgeClass,
  MessagePaper,
  ThreadCard,
} from '../components/maildesk/maildeskShared.jsx';

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

  const parseRecipientLine = (value) => {
    return value
      .split(/[,\n]/)
      .map(item => item.trim())
      .filter(Boolean)
      .map(email => ({ email, name: email.split('@')[0] || email }));
  };

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
  }), [composerThreadId, draftForm]);

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

  const handleComposeSubmit = async (e) => {
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
  };

  const handleSaveDraftOnly = async () => {
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
  };

  const handleArchive = async (threadId) => {
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
  };

  const handleMarkRead = async (threadId) => {
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
  };

  const handleSyncInbox = async () => {
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
  };

  const handleRunPollingOnce = async () => {
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
  };

  const handlePollingConfigChange = async (patch) => {
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
  };

  const handleAccountTest = async () => {
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
  };

  const handleDecisionStatus = async (threadId, decisionStatus) => {
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
  };

  const handleDiscussWithAi = (thread) => {
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
  };

  const handleCreateTaskFromMail = async (thread) => {
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
  };

  const handleGenerateReplyDraft = async (thread) => {
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
  };

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

  const handlePolicyChange = async (nextPolicy) => {
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
  };

  const openPrevThread = () => {
    if (selectedThreadIndex > 0) {
      setSelectedThreadId(threads[selectedThreadIndex - 1].thread_id);
    }
  };

  const openNextThread = () => {
    if (selectedThreadIndex >= 0 && selectedThreadIndex < threads.length - 1) {
      setSelectedThreadId(threads[selectedThreadIndex + 1].thread_id);
    }
  };

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
              <span className="badge badge-warning">{dashboard?.inbound_today ?? 0} 封今日来信</span>
              <span className="badge badge-error">{dashboard?.needs_reply_threads ?? 0} 条待回应线程</span>
              <span className="badge badge-pending">{dashboard?.waiting_decision_threads ?? 0} 封待你决定</span>
              <span className="badge badge-pending">{dashboard?.draft_count ?? 0} 份草稿</span>
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
        <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)} style={{ maxWidth: 220 }}>
          <option value="">全部账户</option>
          {accounts.map(account => (
            <option key={account.account_id} value={account.account_id}>{account.display_name} · {account.email_address}</option>
          ))}
        </select>
        <select value={selectedFolder} onChange={(e) => setSelectedFolder(e.target.value)} style={{ maxWidth: 160 }}>
          {FOLDER_OPTIONS.map(option => (
            <option key={option.value || 'all'} value={option.value}>{option.label}</option>
          ))}
        </select>
        <button className="btn btn-ghost" onClick={handleSyncInbox} disabled={!selectedAccount || syncing || loading}>
          {syncing ? '正在拉信…' : '同步收件箱'}
        </button>
        <button className="btn btn-ghost" onClick={handleRunPollingOnce} disabled={pollingRunning || loading}>
          {pollingRunning ? '轮询执行中…' : '执行后台轮询'}
        </button>
        <select
          value={activeAccount?.auto_mail_policy || 'draft_and_notify'}
          onChange={(e) => handlePolicyChange(e.target.value)}
          disabled={!activeAccount || policySaving || loading}
          style={{ maxWidth: 200 }}
        >
          {AUTO_MAIL_POLICY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-ghost" onClick={() => onOpenNotifyNetwork?.()}>账户接线</button>
        <button className="btn btn-ghost" onClick={handleAccountTest} disabled={!activeAccount || accountTesting || loading}>
          {accountTesting ? '检定中…' : '账户检定'}
        </button>
        <button className="btn btn-primary" onClick={() => { resetComposer(); setComposerOpen(true); }}>写一封信</button>
      </div>

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">活跃线程</div>
          <div className="board-summary-value">{dashboard?.total_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">未读线程</div>
          <div className="board-summary-value">{dashboard?.unread_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">待回信</div>
          <div className="board-summary-value">{dashboard?.needs_reply_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">待你决定</div>
          <div className="board-summary-value">{dashboard?.waiting_decision_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">最近同步</div>
          <div className="board-summary-value" style={{ fontSize: '1rem' }}>
            {syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : '尚未拉信'}
          </div>
        </div>
      </div>

      <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="board-lane-header">
          <div>
            <div className="section-kicker">MAIL CONTROL GRID</div>
            <h3 className="board-lane-title">工作台控制面</h3>
            <div className="board-lane-copy">
              把轮询、筛选、同步台账和账户链路都放回同一张桌面，而不是让你为了一个动作反复跳去设置页。
            </div>
          </div>
        </div>
        <div className="mail-control-grid">
          <article className="mail-control-card">
            <div className="section-kicker">THREAD FILTERS</div>
            <div className="mail-control-title">筛选当前案头</div>
            <div className="mail-control-copy">按是否未读、是否待回、是否待决定和关键词收窄当前来信堆，让真正需要你处理的那几封浮到最上面。</div>
            <div className="command-form mail-filter-form">
              <div className="form-group">
                <label>检索词</label>
                <input
                  value={threadFilters.query}
                  onChange={(e) => setThreadFilters(prev => ({ ...prev, query: e.target.value }))}
                  placeholder="主题、摘要或参与者"
                />
              </div>
              <div className="mail-filter-toggles">
                <button type="button" className={`badge ${threadFilters.unreadOnly ? 'badge-warning' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, unreadOnly: !prev.unreadOnly }))}>只看未读</button>
                <button type="button" className={`badge ${threadFilters.needsReplyOnly ? 'badge-error' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, needsReplyOnly: !prev.needsReplyOnly }))}>只看待回信</button>
                <button type="button" className={`badge ${threadFilters.waitingDecisionOnly ? 'badge-pending' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, waitingDecisionOnly: !prev.waitingDecisionOnly }))}>只看待决定</button>
                <button
                  type="button"
                  className="badge badge-ghost"
                  onClick={() => setThreadFilters({ query: '', unreadOnly: false, needsReplyOnly: false, waitingDecisionOnly: false })}
                >
                  清空筛选
                </button>
              </div>
            </div>
          </article>

          <article className="mail-control-card">
            <div className="section-kicker">POLLING DESK</div>
            <div className="mail-control-title">后台拉信轮询</div>
            <div className="mail-control-copy">系统现在可以按固定节奏主动去邮箱看信，而不是只在你点按钮时才醒来。</div>
            <div className="mail-polling-grid">
              <label className="mail-toggle-row">
                <span>轮询开关</span>
                <input
                  type="checkbox"
                  checked={!!pollingState.enabled}
                  disabled={pollingSaving || loading}
                  onChange={(e) => handlePollingConfigChange({ enabled: e.target.checked })}
                />
              </label>
              <div className="form-group">
                <label>轮询信箱</label>
                <select
                  value={pollingState.folder_kind || 'inbox'}
                  disabled={pollingSaving || loading}
                  onChange={(e) => handlePollingConfigChange({ folder_kind: e.target.value })}
                >
                  {POLLING_FOLDER_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>间隔秒数</label>
                <input
                  type="number"
                  min={60}
                  max={86400}
                  value={pollingState.interval_seconds || 300}
                  disabled={pollingSaving || loading}
                  onChange={(e) => setPollingState(prev => ({ ...prev, interval_seconds: e.target.value }))}
                  onBlur={() => handlePollingConfigChange({ interval_seconds: Math.max(60, Number(pollingState.interval_seconds) || 300) })}
                />
              </div>
              <div className="form-group">
                <label>单次上限</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={pollingState.limit || 20}
                  disabled={pollingSaving || loading}
                  onChange={(e) => setPollingState(prev => ({ ...prev, limit: e.target.value }))}
                  onBlur={() => handlePollingConfigChange({ limit: Math.min(100, Math.max(1, Number(pollingState.limit) || 20)) })}
                />
              </div>
            </div>
            <div className="mail-control-meta">
              <span className={`badge ${pollingState.enabled ? 'badge-completed' : 'badge-ghost'}`}>{pollingState.enabled ? '后台轮询已开启' : '后台轮询已关闭'}</span>
              <span className={`badge ${pollingState.is_running ? 'badge-warning' : 'badge-ghost'}`}>{pollingState.is_running ? '正在执行' : '当前空闲'}</span>
              <span className="badge badge-ghost">最近成功 {pollingState.last_success_at ? formatDateTime(pollingState.last_success_at) : '未记录'}</span>
              {pollingSaving && <span className="badge badge-warning">正在保存配置</span>}
            </div>
            {!pollingSaving && pollingFeedback && (
              <div className={`mail-inline-alert ${pollingFeedback.tone === 'error' ? 'mail-inline-alert-error' : 'mail-inline-alert-success'}`}>
                {pollingFeedback.message}
                {pollingFeedback.savedAt ? ` · ${formatDateTime(pollingFeedback.savedAt)}` : ''}
              </div>
            )}
            {!!pollingState.last_error && (
              <div className="mail-inline-alert mail-inline-alert-error">{pollingState.last_error}</div>
            )}
            {pollingSummary && (
              <div className="mail-polling-summary">
                <div className="mail-polling-summary-grid">
                  <div className="mail-polling-summary-card">
                    <div className="mail-polling-summary-label">扫描账户</div>
                    <div className="mail-polling-summary-value">{pollingSummary.account_count ?? 0}</div>
                  </div>
                  <div className="mail-polling-summary-card">
                    <div className="mail-polling-summary-label">成功</div>
                    <div className="mail-polling-summary-value">{pollingSummary.success_count ?? 0}</div>
                  </div>
                  <div className="mail-polling-summary-card">
                    <div className="mail-polling-summary-label">错误</div>
                    <div className="mail-polling-summary-value">{pollingSummary.error_count ?? 0}</div>
                  </div>
                  <div className="mail-polling-summary-card">
                    <div className="mail-polling-summary-label">新增来信</div>
                    <div className="mail-polling-summary-value">{pollingSummary.new_count ?? 0}</div>
                  </div>
                </div>
                <details className="mail-detail-block">
                  <summary>展开本轮轮询台账</summary>
                  <div className="signal-list" style={{ marginTop: 'var(--space-sm)' }}>
                    {pollingResults.length === 0 ? (
                      <div className="signal-row">
                        <div>
                          <div className="signal-row-title">本轮没有明细</div>
                          <div className="signal-row-copy">可能当前没有开启可同步账户，或这一轮没有命中实际执行。</div>
                        </div>
                      </div>
                    ) : (
                      pollingResults.map((item, index) => (
                        <div key={`${item.account_id || 'result'}-${index}`} className="signal-row">
                          <div>
                            <div className="signal-row-title">
                              {(accounts.find(account => account.account_id === item.account_id)?.display_name) || item.account_id || '未命名账户'}
                            </div>
                            <div className="signal-row-copy">{item.message || '本轮已记录执行结果。'}</div>
                          </div>
                          <span className={`badge ${getExecutionBadgeClass(item.status)}`}>{getExecutionStatusLabel(item.status)}</span>
                        </div>
                      ))
                    )}
                  </div>
                </details>
              </div>
            )}
          </article>

          <article className="mail-control-card">
            <div className="section-kicker">ACCOUNT CHECK</div>
            <div className="mail-control-title">当前账户链路</div>
            <div className="mail-control-copy">检定 SMTP 和 IMAP 是否真的打通，免得案头没有来信时，你分不清是世界安静还是线路已经断了。</div>
            {activeAccount ? (
              <>
                <div className="signal-list">
                  <div className="signal-row">
                    <div>
                      <div className="signal-row-title">{activeAccount.display_name}</div>
                      <div className="signal-row-copy">{activeAccount.email_address}</div>
                    </div>
                    <span className="badge badge-pending">{getAutoMailPolicyLabel(activeAccount.auto_mail_policy)}</span>
                  </div>
                  <div className="signal-row">
                    <div>
                      <div className="signal-row-title">同步状态</div>
                      <div className="signal-row-copy">{activeAccount.sync_enabled ? '允许拉信' : '已暂停同步'}</div>
                    </div>
                    <span className={`badge ${activeAccount.sync_enabled ? 'badge-completed' : 'badge-ghost'}`}>{activeAccount.sync_enabled ? '同步开启' : '同步关闭'}</span>
                  </div>
                </div>
                {accountTestResult?.results && (
                  <div className="signal-list" style={{ marginTop: 'var(--space-sm)' }}>
                    {Object.entries(accountTestResult.results).map(([key, value]) => (
                      <div key={key} className="signal-row">
                        <div>
                          <div className="signal-row-title">{key.toUpperCase()}</div>
                          <div className="signal-row-copy">{value.message}</div>
                        </div>
                        <span className={`badge ${value.status === 'success' ? 'badge-completed' : value.status === 'error' ? 'badge-error' : 'badge-ghost'}`}>
                          {value.status === 'success' ? '通过' : value.status === 'error' ? '失败' : '跳过'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="mail-control-copy">先接入一个书信账户，这里才会显示真实链路状态。</div>
            )}
          </article>

          <article className="mail-control-card">
            <div className="section-kicker">SYNC LEDGER</div>
            <div className="mail-control-title">最近同步台账</div>
            <div className="mail-control-copy">显示最近一轮拉信抓了多少、入了多少新信、最后停在什么 UID，而不是只剩一颗同步按钮。</div>
            <div className="signal-list">
              <div className="signal-row">
                <div>
                  <div className="signal-row-title">最近状态</div>
                  <div className="signal-row-copy">{syncStatus?.status || '尚未执行'}</div>
                </div>
                <span className={`badge ${syncStatus?.status === 'success' ? 'badge-completed' : syncStatus?.status === 'error' ? 'badge-error' : 'badge-ghost'}`}>
                  {syncStatus?.status === 'success' ? '成功' : syncStatus?.status === 'error' ? '失败' : '未执行'}
                </span>
              </div>
              <div className="signal-row">
                <div>
                  <div className="signal-row-title">抓取 / 新增</div>
                  <div className="signal-row-copy">{syncStatus ? `${syncStatus.fetched_count || 0} / ${syncStatus.new_count || 0}` : '0 / 0'}</div>
                </div>
                <span className="badge badge-ghost">{syncStatus?.latest_uid || '无 UID'}</span>
              </div>
              <div className="signal-row">
                <div>
                  <div className="signal-row-title">完成时间</div>
                  <div className="signal-row-copy">{syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : '尚未记录'}</div>
                </div>
              </div>
            </div>
            {syncStatus?.status === 'error' && (
              <div className="mail-inline-alert mail-inline-alert-error">
                最近一次拉信失败于 {formatDateTime(syncStatus.finished_at || syncStatus.started_at || syncStatus.created_at)}。
                {syncStatus.error_message ? ` ${syncStatus.error_message}` : ' 请先检查账户链路或立即重试同步。'}
              </div>
            )}
            {!!syncStatus?.error_message && (
              <div className="mail-inline-alert mail-inline-alert-error">{syncStatus.error_message}</div>
            )}
          </article>
        </div>
      </section>

      {activeAccount && (
        <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">AUTO HANDLER</div>
              <h3 className="board-lane-title">自动回信策略</h3>
              <div className="board-lane-copy">
                当前账户「{activeAccount.display_name}」采用“{getAutoMailPolicyLabel(activeAccount.auto_mail_policy)}”。
                这是书信代理的行事准则，决定它在手机端来信抵达后，是只起草、等你确认，还是直接替你寄出。
              </div>
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{activeAccount.email_address}</span>
              <span className="badge badge-warning">{getAutoMailPolicyLabel(activeAccount.auto_mail_policy)}</span>
            </div>
          </div>
          <div className="signal-row" style={{ marginTop: 'var(--space-md)', alignItems: 'flex-start' }}>
            <div>
              <div className="signal-row-title">当前行为说明</div>
              <div className="signal-row-copy">{getAutoPolicyNarrative(activeAccount.auto_mail_policy)}</div>
            </div>
            <button className="btn btn-sm btn-ghost" onClick={() => onOpenNotifyNetwork?.()}>去接线检定页调整</button>
          </div>
        </section>
      )}

      {decisionQueue.length > 0 && (
        <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">DECISION QUEUE</div>
              <h3 className="board-lane-title">待你决定</h3>
              <div className="board-lane-copy">有些信不该被立刻埋进归档。它们像黄昏时分的敲门声，等你决定是回信、安排，还是让它稍后再来。</div>
            </div>
          </div>
          <div className="board-card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
            {decisionQueue.slice(0, 6).map(thread => (
              <DecisionQueueCard
                key={thread.thread_id}
                thread={thread}
                onOpen={setSelectedThreadId}
                onDiscuss={handleDiscussWithAi}
                onCreateTask={handleCreateTaskFromMail}
              />
            ))}
          </div>
        </section>
      )}

      <div className="war-room-grid mail-spread-grid">
        <div className="war-room-stack">
          <section className="board-lane atlas-paper-stack mail-spread-lane mail-rail-lane">
            <div className="board-lane-header mail-lane-header">
              <div className="mail-lane-head-copy">
                <div className="section-kicker">INBOX RAIL</div>
                <h3 className="board-lane-title">{selectedFolder === 'archive' ? '归档箱' : '来信匣'}</h3>
                <div className="board-lane-copy">
                  {selectedFolder === 'archive'
                    ? '归档箱不再维持工作流姿势，只保留一份安静的历史索引。你可以按时间翻检，但它们不该继续抢占案头。'
                    : '这里改成像游戏里的选卡台。一次只看一封活跃线程，用上一封和下一封慢慢翻，不让长列表把注意力拖散。'}
                </div>
              </div>
              <div className="mail-lane-status">
                <div className="mail-lane-status-label">{selectedFolder === 'archive' ? '历史索引' : '翻页进度'}</div>
                <div className="mail-lane-status-value">
                  {threads.length === 0
                    ? '暂无线程'
                    : (selectedFolder === 'archive'
                      ? `${threads.length} 封已归档`
                      : `第 ${Math.max(selectedThreadIndex + 1, 1)} / ${threads.length} 封`)}
                </div>
                <div className="mail-lane-status-copy">
                  {selectedFolder === 'archive'
                    ? '这些信只供回看，不继续占用当前工作台。'
                    : '每次只翻一张卡，让注意力停在正在处理的那封来信上。'}
                </div>
              </div>
            </div>

            {threads.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✉️</div>
                <div className="empty-state-text">案头还没有信</div>
                <div className="empty-state-hint">先接一个邮箱账户，或者从系统里写出第一封信。</div>
              </div>
            ) : (
              selectedFolder === 'archive' ? (
                <div className="signal-list mail-archive-list">
                  {threads.map(thread => (
                    <ArchiveThreadRow
                      key={thread.thread_id}
                      thread={thread}
                      active={thread.thread_id === selectedThreadId}
                      onOpen={setSelectedThreadId}
                    />
                  ))}
                </div>
              ) : (
                <div className="mail-rail-body">
                  <div className="mail-rail-toolbar">
                    <div className="mail-rail-toolbar-copy">
                      活跃线程不会再拉成长长一列，而是像牌桌上一张张翻开。
                    </div>
                    <div className="inline-actions">
                      <button className="btn btn-sm btn-ghost" onClick={openPrevThread} disabled={selectedThreadIndex <= 0}>上一封</button>
                      <button className="btn btn-sm btn-ghost" onClick={openNextThread} disabled={selectedThreadIndex < 0 || selectedThreadIndex >= threads.length - 1}>下一封</button>
                    </div>
                  </div>

                  {railThread && (
                    <div className="mail-thread-stage">
                      <ThreadCard
                        key={railThread.thread_id}
                        thread={railThread}
                        active={railThread.thread_id === selectedThreadId}
                        onOpen={setSelectedThreadId}
                      />
                    </div>
                  )}

                  {threads.length > 1 && (
                    <div className="mail-rail-pagination">
                      {threads.map((thread, index) => (
                        <button
                          key={thread.thread_id}
                          type="button"
                          className={`badge ${thread.thread_id === selectedThreadId ? 'badge-warning' : 'badge-ghost'}`}
                          onClick={() => setSelectedThreadId(thread.thread_id)}
                          style={{ cursor: 'pointer' }}
                          title={thread.subject}
                        >
                          {index + 1}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            )}
          </section>
        </div>

        <div className="war-room-stack">
          <OpenLetterPanel
            selectedFolder={selectedFolder}
            selectedThread={selectedThread}
            selectedThreadAccount={selectedThreadAccount}
            selectedMailtoHref={selectedMailtoHref}
            threadRefreshing={threadRefreshing}
            activeDraft={activeDraft}
            latestAgentRun={latestAgentRun}
            threadDetail={threadDetail}
            selectedAgentRuns={selectedAgentRuns}
            agentRunFilter={agentRunFilter}
            agentRunsLoading={agentRunsLoading}
            openPortalPage={openPortalPage}
            copyPortalLink={copyPortalLink}
            handleRefreshSelectedThread={handleRefreshSelectedThread}
            handleMarkRead={handleMarkRead}
            handleArchive={handleArchive}
            handleDecisionStatus={handleDecisionStatus}
            handleReplyThread={handleReplyThread}
            handleGenerateReplyDraft={handleGenerateReplyDraft}
            handleCreateTaskFromMail={handleCreateTaskFromMail}
            handleDiscussWithAi={handleDiscussWithAi}
            fetchAgentRuns={fetchAgentRuns}
            setAgentRunFilter={setAgentRunFilter}
            onOpenDraftComposer={openDraftComposer}
            onSendDraft={handleSendDraftFromPanel}
          />
        </div>
      </div>

      <MailComposerModal
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        onSubmit={handleComposeSubmit}
        composerDraftId={composerDraftId}
        composerThreadId={composerThreadId}
        composerResetting={composerResetting}
        loading={loading}
        draftForm={draftForm}
        setDraftForm={setDraftForm}
        accounts={accounts}
        toneOptions={TONE_OPTIONS}
        onResetToLatestDraft={handleResetComposerToLatestDraft}
        onSaveDraftOnly={handleSaveDraftOnly}
      />

    </div>
  );
}
