import { useEffect } from 'react';

export function useMailDeskLifecycle({
  refreshAll,
  fetchDashboard,
  fetchThreads,
  fetchSyncStatus,
  fetchThreadDetail,
  selectedAccount,
  selectedFolder,
  selectedThreadId,
  setAgentRunFilter,
  activeAccount,
  setDraftForm,
  accounts,
  setSelectedAccount,
  quickAction,
  clearQuickAction,
}) {
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
  }, [selectedThreadId, setAgentRunFilter]);

  useEffect(() => {
    if (activeAccount) {
      setDraftForm((prev) => ({
        ...prev,
        account_id: prev.account_id || activeAccount.account_id,
        signature: prev.signature || activeAccount.signature_text || '',
        tone_mode: prev.tone_mode || activeAccount.tone_mode || 'warm',
      }));
    }
  }, [activeAccount, setDraftForm]);

  useEffect(() => {
    if (accounts.length > 0 && !selectedAccount) {
      setSelectedAccount(accounts[0].account_id || '');
    }
  }, [accounts, selectedAccount, setSelectedAccount]);

  useEffect(() => {
    if (!quickAction) return;
    if (quickAction.type === 'notify_network_ready') {
      refreshAll();
      clearQuickAction?.();
    }
  }, [quickAction, clearQuickAction, refreshAll]);
}
