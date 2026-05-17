import { useCallback, useState } from 'react';
import { apiPost, apiPut } from './useApi';

export function useMailDeskPollingActions({
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
}) {
  const [pollingSaving, setPollingSaving] = useState(false);
  const [pollingRunning, setPollingRunning] = useState(false);
  const [deskRefreshing, setDeskRefreshing] = useState(false);
  const [pollingFeedback, setPollingFeedback] = useState(null);

  const handleRunPollingOnce = useCallback(async () => {
    setPollingRunning(true);
    try {
      const data = await request(() => apiPost('/api/mail/polling/run-once', {}));
      const summary = data.polling?.last_summary || {};
      toast(`轮询已执行，新增 ${summary.new_count ?? 0} 封信`, 'success');
      const [threadsInfo] = await Promise.all([
        refreshDeskSnapshot(selectedAccount, selectedFolder, selectedThreadId),
        fetchPollingStatus(),
      ]);
      if (threadsInfo?.selectedThreadId && threadsInfo.selectedThreadId === selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '执行轮询失败', 'error');
    } finally {
      setPollingRunning(false);
    }
  }, [
    fetchPollingStatus,
    fetchThreadDetail,
    refreshDeskSnapshot,
    request,
    selectedAccount,
    selectedFolder,
    selectedThreadId,
    toast,
  ]);

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
  }, [fetchPollingStatus, pollingState, request, setPollingState, toast]);

  const refreshDeskThreads = useCallback(async () => {
    setDeskRefreshing(true);
    try {
      await refreshDeskSnapshot(selectedAccount, selectedFolder);
      toast('案头线程已经刷新', 'success');
    } catch (e) {
      toast(e.message || '刷新案头失败', 'error');
    } finally {
      setDeskRefreshing(false);
    }
  }, [refreshDeskSnapshot, selectedAccount, selectedFolder, toast]);

  return {
    pollingSaving,
    pollingRunning,
    deskRefreshing,
    pollingFeedback,
    handleRunPollingOnce,
    handlePollingConfigChange,
    refreshDeskThreads,
  };
}
