import { act, renderHook } from '@testing-library/react';
import { useMailDeskAccountActions } from '../useMailDeskAccountActions';
import { apiPost, apiPut } from '../useApi';

vi.mock('../useApi', async () => {
  const actual = await vi.importActual('../useApi');
  return {
    ...actual,
    apiPost: vi.fn(),
    apiPut: vi.fn(),
  };
});

describe('useMailDeskAccountActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'open', {
      value: vi.fn(),
      writable: true,
    });
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  it('opens and copies portal links with guards', async () => {
    const toast = vi.fn();

    const { result } = renderHook(() => useMailDeskAccountActions({
      request: async (fn) => fn(),
      toast,
      activeAccount: null,
      selectedAccount: '',
      selectedFolder: '',
      selectedThreadId: '',
      refreshAll: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      fetchThreadDetail: vi.fn(),
    }));

    act(() => {
      result.current.openPortalPage({});
    });
    expect(toast).toHaveBeenCalledWith('这封信还没有可打开的处理页链接', 'error');

    act(() => {
      result.current.openPortalPage({ portal_url: 'https://portal.example.com' });
    });
    expect(window.open).toHaveBeenCalledWith('https://portal.example.com', '_blank', 'noopener,noreferrer');

    await act(async () => {
      await result.current.copyPortalLink({ portal_url: 'https://portal.example.com' });
    });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://portal.example.com');
    expect(toast).toHaveBeenCalledWith('处理页链接已复制', 'success');
  });

  it('syncs inbox and refreshes selected thread on success', async () => {
    apiPost.mockResolvedValue({ new_count: 3 });
    const toast = vi.fn();
    const refreshDeskSnapshot = vi.fn().mockResolvedValue({ selectedThreadId: 'thread-1' });
    const fetchThreadDetail = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskAccountActions({
      request: async (fn) => fn(),
      toast,
      activeAccount: { account_id: 'acc-1', auto_mail_policy: 'draft_only' },
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-1',
      refreshAll: vi.fn(),
      refreshDeskSnapshot,
      fetchThreadDetail,
    }));

    await act(async () => {
      await result.current.handleSyncInbox();
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/accounts/acc-1/sync?folder_kind=inbox&limit=20', {});
    expect(refreshDeskSnapshot).toHaveBeenCalledWith('acc-1', 'inbox', 'thread-1');
    expect(fetchThreadDetail).toHaveBeenCalledWith('thread-1');
    expect(toast).toHaveBeenCalledWith('收件箱已同步，新增 3 封信', 'success');
    expect(result.current.syncing).toBe(false);
  });

  it('updates policy and refreshes desk state', async () => {
    apiPut.mockResolvedValue({});
    const toast = vi.fn();
    const refreshAll = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskAccountActions({
      request: async (fn) => fn(),
      toast,
      activeAccount: { account_id: 'acc-1', auto_mail_policy: 'draft_only' },
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-1',
      refreshAll,
      refreshDeskSnapshot: vi.fn(),
      fetchThreadDetail: vi.fn(),
    }));

    await act(async () => {
      await result.current.handlePolicyChange('auto_send');
    });

    expect(apiPut).toHaveBeenCalledWith('/api/mail/accounts/acc-1', {
      auto_mail_policy: 'auto_send',
    });
    expect(refreshAll).toHaveBeenCalledWith('acc-1', 'inbox', 'thread-1');
    expect(toast).toHaveBeenCalledWith('自动处理已切到“自动寄出”', 'success');
    expect(result.current.policySaving).toBe(false);
  });
});
