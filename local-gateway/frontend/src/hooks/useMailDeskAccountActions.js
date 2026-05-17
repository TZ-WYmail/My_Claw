import { useCallback, useState } from 'react';
import { apiPost, apiPut } from './useApi';
import { getAutoMailPolicyLabel } from '../components/maildesk/maildeskShared.jsx';

export function useMailDeskAccountActions({
  request,
  toast,
  activeAccount,
  selectedAccount,
  selectedFolder,
  selectedThreadId,
  refreshAll,
  refreshDeskSnapshot,
  fetchThreadDetail,
}) {
  const [syncing, setSyncing] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);
  const [accountTesting, setAccountTesting] = useState(false);
  const [accountTestResult, setAccountTestResult] = useState(null);

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
    } catch (error) {
      toast(error.message || '同步收件箱失败', 'error');
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
    } catch (error) {
      setAccountTestResult({ status: 'error', message: error.message || '链路检定失败' });
      toast(error.message || '账户链路检定失败', 'error');
    } finally {
      setAccountTesting(false);
    }
  }, [activeAccount, request, toast]);

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
    } catch (error) {
      toast(error.message || '更新自动处理策略失败', 'error');
    } finally {
      setPolicySaving(false);
    }
  }, [activeAccount, refreshAll, request, selectedAccount, selectedFolder, selectedThreadId, toast]);

  return {
    syncing,
    policySaving,
    accountTesting,
    accountTestResult,
    openPortalPage,
    copyPortalLink,
    handleSyncInbox,
    handleAccountTest,
    handlePolicyChange,
  };
}
