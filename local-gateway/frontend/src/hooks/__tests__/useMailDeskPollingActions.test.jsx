import { act, renderHook } from '@testing-library/react';
import { useMailDeskPollingActions } from '../useMailDeskPollingActions';
import { apiPost, apiPut } from '../useApi';

vi.mock('../useApi', async () => {
  const actual = await vi.importActual('../useApi');
  return {
    ...actual,
    apiPost: vi.fn(),
    apiPut: vi.fn(),
  };
});

describe('useMailDeskPollingActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runs polling once and refreshes the selected thread when it stays selected', async () => {
    apiPost.mockResolvedValue({
      polling: {
        last_summary: {
          new_count: 2,
        },
      },
    });
    const toast = vi.fn();
    const refreshDeskSnapshot = vi.fn().mockResolvedValue({ selectedThreadId: 'thread-1' });
    const fetchPollingStatus = vi.fn().mockResolvedValue(undefined);
    const fetchThreadDetail = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskPollingActions({
      request: async (fn) => fn(),
      toast,
      pollingState: {
        enabled: true,
        interval_seconds: 300,
        folder_kind: 'inbox',
        limit: 20,
      },
      setPollingState: vi.fn(),
      fetchPollingStatus,
      refreshDeskSnapshot,
      fetchThreadDetail,
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-1',
    }));

    await act(async () => {
      await result.current.handleRunPollingOnce();
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/polling/run-once', {});
    expect(refreshDeskSnapshot).toHaveBeenCalledWith('acc-1', 'inbox', 'thread-1');
    expect(fetchPollingStatus).toHaveBeenCalled();
    expect(fetchThreadDetail).toHaveBeenCalledWith('thread-1');
    expect(toast).toHaveBeenCalledWith('轮询已执行，新增 2 封信', 'success');
    expect(result.current.pollingRunning).toBe(false);
  });

  it('saves polling config and records feedback', async () => {
    apiPut.mockResolvedValue({
      polling: {
        enabled: true,
        interval_seconds: 900,
        folder_kind: 'archive',
        limit: 10,
      },
    });
    const toast = vi.fn();
    const setPollingState = vi.fn();

    const { result } = renderHook(() => useMailDeskPollingActions({
      request: async (fn) => fn(),
      toast,
      pollingState: {
        enabled: false,
        interval_seconds: 300,
        folder_kind: 'inbox',
        limit: 20,
      },
      setPollingState,
      fetchPollingStatus: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      fetchThreadDetail: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-1',
    }));

    await act(async () => {
      await result.current.handlePollingConfigChange({
        enabled: true,
        interval_seconds: 900,
        folder_kind: 'archive',
        limit: 10,
      });
    });

    expect(apiPut).toHaveBeenCalledWith('/api/mail/polling', {
      enabled: true,
      interval_seconds: 900,
      folder_kind: 'archive',
      limit: 10,
    });
    expect(setPollingState).toHaveBeenCalledTimes(2);
    expect(setPollingState).toHaveBeenNthCalledWith(1, {
      enabled: true,
      interval_seconds: 900,
      folder_kind: 'archive',
      limit: 10,
    });
    expect(setPollingState.mock.calls[1][0]).toEqual(expect.any(Function));
    expect(result.current.pollingFeedback).toEqual(expect.objectContaining({
      tone: 'success',
      message: '后台轮询已开启，配置已写回执行器',
    }));
    expect(toast).toHaveBeenCalledWith('后台轮询已经接通', 'success');
    expect(result.current.pollingSaving).toBe(false);
  });

  it('restores status when polling config save fails', async () => {
    apiPut.mockRejectedValue(new Error('save failed'));
    const toast = vi.fn();
    const fetchPollingStatus = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskPollingActions({
      request: async (fn) => fn(),
      toast,
      pollingState: {
        enabled: true,
        interval_seconds: 300,
        folder_kind: 'inbox',
        limit: 20,
      },
      setPollingState: vi.fn(),
      fetchPollingStatus,
      refreshDeskSnapshot: vi.fn(),
      fetchThreadDetail: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-1',
    }));

    await act(async () => {
      await result.current.handlePollingConfigChange({ enabled: false });
    });

    expect(fetchPollingStatus).toHaveBeenCalled();
    expect(result.current.pollingFeedback).toEqual({
      tone: 'error',
      message: 'save failed',
      savedAt: '',
    });
    expect(toast).toHaveBeenCalledWith('save failed', 'error');
    expect(result.current.pollingSaving).toBe(false);
  });

  it('refreshes desk threads from the current account and folder', async () => {
    const toast = vi.fn();
    const refreshDeskSnapshot = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskPollingActions({
      request: async (fn) => fn(),
      toast,
      pollingState: {
        enabled: true,
        interval_seconds: 300,
        folder_kind: 'inbox',
        limit: 20,
      },
      setPollingState: vi.fn(),
      fetchPollingStatus: vi.fn(),
      refreshDeskSnapshot,
      fetchThreadDetail: vi.fn(),
      selectedAccount: 'acc-9',
      selectedFolder: 'pending',
      selectedThreadId: '',
    }));

    await act(async () => {
      await result.current.refreshDeskThreads();
    });

    expect(refreshDeskSnapshot).toHaveBeenCalledWith('acc-9', 'pending');
    expect(toast).toHaveBeenCalledWith('案头线程已经刷新', 'success');
    expect(result.current.deskRefreshing).toBe(false);
  });
});
