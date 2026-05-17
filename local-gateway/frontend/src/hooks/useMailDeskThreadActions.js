import { useCallback, useState } from 'react';
import { apiGet, apiPost } from './useApi';

export function useMailDeskThreadActions({
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
}) {
  const [archivingThreadId, setArchivingThreadId] = useState('');
  const [markingReadThreadId, setMarkingReadThreadId] = useState('');
  const [decisionUpdating, setDecisionUpdating] = useState({ threadId: '', status: '' });
  const [replyDraftGeneratingThreadId, setReplyDraftGeneratingThreadId] = useState('');
  const [draftSendingId, setDraftSendingId] = useState('');
  const [threadRefreshing, setThreadRefreshing] = useState(false);

  const handleArchive = useCallback(async (threadId) => {
    setArchivingThreadId(threadId);
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${threadId}/archive`, {}));
      toast('这封信已收进归档夹', 'success');
      const stillVisible = syncThreadDetailIntoDesk(data);
      await fetchDashboard(selectedAccount);
      if (selectedFolder !== 'archive' && selectedThreadId === threadId) {
        setSelectedThreadId('');
        setThreadDetail(null);
      } else if (selectedThreadId === threadId && stillVisible) {
        setThreadDetail(data);
      }
    } catch (e) {
      toast(e.message || '归档失败', 'error');
    } finally {
      setArchivingThreadId('');
    }
  }, [
    fetchDashboard,
    request,
    selectedAccount,
    selectedFolder,
    selectedThreadId,
    setSelectedThreadId,
    setThreadDetail,
    syncThreadDetailIntoDesk,
    toast,
  ]);

  const handleMarkRead = useCallback(async (threadId) => {
    setMarkingReadThreadId(threadId);
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${threadId}/mark-read`, {}));
      toast('已把这封信翻到已读一侧', 'success');
      syncThreadDetailIntoDesk(data);
      await fetchDashboard(selectedAccount);
    } catch (e) {
      toast(e.message || '标记已读失败', 'error');
    } finally {
      setMarkingReadThreadId('');
    }
  }, [fetchDashboard, request, selectedAccount, syncThreadDetailIntoDesk, toast]);

  const handleDecisionStatus = useCallback(async (threadId, decisionStatus) => {
    setDecisionUpdating({ threadId, status: decisionStatus });
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${threadId}/decision`, { decision_status: decisionStatus }));
      toast(decisionStatus === 'snoozed' ? '这封信稍后再来叩门' : '这封信先从待裁决队列退下', 'success');
      syncThreadDetailIntoDesk(data);
      await fetchDashboard(selectedAccount);
    } catch (e) {
      toast(e.message || '更新决策状态失败', 'error');
    } finally {
      setDecisionUpdating({ threadId: '', status: '' });
    }
  }, [fetchDashboard, request, selectedAccount, syncThreadDetailIntoDesk, toast]);

  const handleGenerateReplyDraft = useCallback(async (thread) => {
    setReplyDraftGeneratingThreadId(thread.thread_id);
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${thread.thread_id}/generate-reply-draft`, {}));
      const latestDraft = (data.drafts || [])[0];
      if (latestDraft) {
        openDraftComposer(latestDraft, thread);
      }
      setSelectedThreadId(thread.thread_id);
      toast(data.draft_source === 'ai' ? 'AI 已替你起草回信' : '已生成模板回信草稿', 'success');
      syncThreadDetailIntoDesk(data);
      await fetchDashboard(selectedAccount);
    } catch (e) {
      toast(e.message || '生成回信草稿失败', 'error');
    } finally {
      setReplyDraftGeneratingThreadId('');
    }
  }, [fetchDashboard, openDraftComposer, request, selectedAccount, setSelectedThreadId, syncThreadDetailIntoDesk, toast]);

  const handleSendDraftFromPanel = useCallback(async (draft) => {
    if (!draft?.draft_id || !selectedThread?.thread_id) {
      return;
    }
    setDraftSendingId(draft.draft_id);
    try {
      const data = await request(() => apiPost(`/api/mail/drafts/${draft.draft_id}/send`, {}));
      toast('这份草稿已经寄出', 'success');
      syncThreadDetailIntoDesk(data);
      await fetchDashboard(selectedAccount);
    } catch (e) {
      toast(e.message || '发送草稿失败', 'error');
    } finally {
      setDraftSendingId('');
    }
  }, [fetchDashboard, request, selectedAccount, selectedThread, syncThreadDetailIntoDesk, toast]);

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

  return {
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
  };
}
