import { useCallback, useState } from 'react';
import { apiGet } from './useApi';
import { normalizeList } from '../utils/normalize';

export function useMailDeskData({
  selectedAccount,
  selectedFolder,
  selectedThreadId,
  threadFilters,
  setPollingState,
  deriveThreadSummaryFromDetail,
  matchesThreadFilters,
  setSelectedThreadId,
}) {
  const [dashboard, setDashboard] = useState(null);
  const [threads, setThreads] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [threadDetail, setThreadDetail] = useState(null);
  const [threadDetailLoading, setThreadDetailLoading] = useState(false);
  const [agentRunsLoading, setAgentRunsLoading] = useState(false);

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

  const fetchAccounts = useCallback(async () => {
    const data = await apiGet('/api/mail/accounts');
    const items = normalizeList(data, ['accounts']);
    setAccounts(items);
    return items;
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
    const resolvedThreadId = preferredThreadId && items.some((item) => item.thread_id === preferredThreadId)
      ? preferredThreadId
      : (items[0]?.thread_id || '');
    setThreads(items);
    setSelectedThreadId(resolvedThreadId);
    return { items, selectedThreadId: resolvedThreadId };
  }, [selectedThreadId, setSelectedThreadId, threadFilters]);

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
  }, [setPollingState]);

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
    const [items, , threadsInfo] = await Promise.all([
      fetchAccounts(),
      fetchDashboard(accountId),
      fetchThreads(accountId, folder, preferredThreadId),
      fetchSyncStatus(accountId),
      fetchPollingStatus(),
    ]);
    return { accounts: items, ...threadsInfo };
  }, [
    fetchAccounts,
    fetchDashboard,
    fetchPollingStatus,
    fetchSyncStatus,
    fetchThreads,
    selectedAccount,
    selectedFolder,
    selectedThreadId,
  ]);

  const refreshDeskSnapshot = useCallback(async (accountId = selectedAccount, folder = selectedFolder, preferredThreadId = selectedThreadId) => {
    const [, threadsInfo] = await Promise.all([
      fetchDashboard(accountId),
      fetchThreads(accountId, folder, preferredThreadId),
      fetchSyncStatus(accountId),
    ]);
    return threadsInfo;
  }, [fetchDashboard, fetchSyncStatus, fetchThreads, selectedAccount, selectedFolder, selectedThreadId]);

  return {
    dashboard,
    threads,
    accounts,
    syncStatus,
    threadDetail,
    setThreadDetail,
    threadDetailLoading,
    agentRunsLoading,
    setAccounts,
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
  };
}
