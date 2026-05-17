import { act, renderHook } from '@testing-library/react';
import { useMailDeskThreadActions } from '../useMailDeskThreadActions';
import { apiPost } from '../useApi';

vi.mock('../useApi', async () => {
  const actual = await vi.importActual('../useApi');
  return {
    ...actual,
    apiPost: vi.fn(),
  };
});

describe('useMailDeskThreadActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('archives the selected inbox thread and clears the open panel when it disappears', async () => {
    apiPost.mockResolvedValue({ thread: { thread_id: 'thread-1' } });
    const toast = vi.fn();
    const fetchDashboard = vi.fn().mockResolvedValue(undefined);
    const setSelectedThreadId = vi.fn();
    const setThreadDetail = vi.fn();
    const syncThreadDetailIntoDesk = vi.fn().mockReturnValue(false);

    const { result } = renderHook(() => useMailDeskThreadActions({
      request: async (fn) => fn(),
      toast,
      syncThreadDetailIntoDesk,
      fetchDashboard,
      fetchThreads: vi.fn(),
      fetchThreadDetail: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      openDraftComposer: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-1',
      selectedThread: { thread_id: 'thread-1' },
      setSelectedThreadId,
      setThreadDetail,
    }));

    await act(async () => {
      await result.current.handleArchive('thread-1');
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/threads/thread-1/archive', {});
    expect(syncThreadDetailIntoDesk).toHaveBeenCalled();
    expect(fetchDashboard).toHaveBeenCalledWith('acc-1');
    expect(setSelectedThreadId).toHaveBeenCalledWith('');
    expect(setThreadDetail).toHaveBeenCalledWith(null);
    expect(toast).toHaveBeenCalledWith('这封信已收进归档夹', 'success');
    expect(result.current.archivingThreadId).toBe('');
  });

  it('marks a thread read and updates dashboard badges', async () => {
    apiPost.mockResolvedValue({ thread: { thread_id: 'thread-2' } });
    const toast = vi.fn();
    const syncThreadDetailIntoDesk = vi.fn();
    const fetchDashboard = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskThreadActions({
      request: async (fn) => fn(),
      toast,
      syncThreadDetailIntoDesk,
      fetchDashboard,
      fetchThreads: vi.fn(),
      fetchThreadDetail: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      openDraftComposer: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: '',
      selectedThread: null,
      setSelectedThreadId: vi.fn(),
      setThreadDetail: vi.fn(),
    }));

    await act(async () => {
      await result.current.handleMarkRead('thread-2');
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/threads/thread-2/mark-read', {});
    expect(syncThreadDetailIntoDesk).toHaveBeenCalled();
    expect(fetchDashboard).toHaveBeenCalledWith('acc-1');
    expect(toast).toHaveBeenCalledWith('已把这封信翻到已读一侧', 'success');
    expect(result.current.markingReadThreadId).toBe('');
  });

  it('updates decision status and clears the loading marker afterwards', async () => {
    apiPost.mockResolvedValue({ thread: { thread_id: 'thread-3' } });
    const toast = vi.fn();
    const syncThreadDetailIntoDesk = vi.fn();
    const fetchDashboard = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskThreadActions({
      request: async (fn) => fn(),
      toast,
      syncThreadDetailIntoDesk,
      fetchDashboard,
      fetchThreads: vi.fn(),
      fetchThreadDetail: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      openDraftComposer: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'pending',
      selectedThreadId: '',
      selectedThread: null,
      setSelectedThreadId: vi.fn(),
      setThreadDetail: vi.fn(),
    }));

    await act(async () => {
      await result.current.handleDecisionStatus('thread-3', 'snoozed');
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/threads/thread-3/decision', {
      decision_status: 'snoozed',
    });
    expect(syncThreadDetailIntoDesk).toHaveBeenCalled();
    expect(fetchDashboard).toHaveBeenCalledWith('acc-1');
    expect(toast).toHaveBeenCalledWith('这封信稍后再来叩门', 'success');
    expect(result.current.decisionUpdating).toEqual({ threadId: '', status: '' });
  });

  it('generates a reply draft and opens it in the composer', async () => {
    apiPost.mockResolvedValue({
      draft_source: 'ai',
      drafts: [
        {
          draft_id: 'draft-1',
          subject: 'Re: Hello',
        },
      ],
    });
    const toast = vi.fn();
    const syncThreadDetailIntoDesk = vi.fn();
    const fetchDashboard = vi.fn().mockResolvedValue(undefined);
    const openDraftComposer = vi.fn();
    const setSelectedThreadId = vi.fn();
    const thread = { thread_id: 'thread-4', subject: 'Hello' };

    const { result } = renderHook(() => useMailDeskThreadActions({
      request: async (fn) => fn(),
      toast,
      syncThreadDetailIntoDesk,
      fetchDashboard,
      fetchThreads: vi.fn(),
      fetchThreadDetail: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      openDraftComposer,
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: '',
      selectedThread: thread,
      setSelectedThreadId,
      setThreadDetail: vi.fn(),
    }));

    await act(async () => {
      await result.current.handleGenerateReplyDraft(thread);
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/threads/thread-4/generate-reply-draft', {});
    expect(openDraftComposer).toHaveBeenCalledWith({ draft_id: 'draft-1', subject: 'Re: Hello' }, thread);
    expect(setSelectedThreadId).toHaveBeenCalledWith('thread-4');
    expect(syncThreadDetailIntoDesk).toHaveBeenCalled();
    expect(fetchDashboard).toHaveBeenCalledWith('acc-1');
    expect(toast).toHaveBeenCalledWith('AI 已替你起草回信', 'success');
    expect(result.current.replyDraftGeneratingThreadId).toBe('');
  });

  it('sends the selected draft from the panel', async () => {
    apiPost.mockResolvedValue({ thread: { thread_id: 'thread-5' } });
    const toast = vi.fn();
    const syncThreadDetailIntoDesk = vi.fn();
    const fetchDashboard = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskThreadActions({
      request: async (fn) => fn(),
      toast,
      syncThreadDetailIntoDesk,
      fetchDashboard,
      fetchThreads: vi.fn(),
      fetchThreadDetail: vi.fn(),
      refreshDeskSnapshot: vi.fn(),
      openDraftComposer: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'inbox',
      selectedThreadId: 'thread-5',
      selectedThread: { thread_id: 'thread-5' },
      setSelectedThreadId: vi.fn(),
      setThreadDetail: vi.fn(),
    }));

    await act(async () => {
      await result.current.handleSendDraftFromPanel({ draft_id: 'draft-9' });
    });

    expect(apiPost).toHaveBeenCalledWith('/api/mail/drafts/draft-9/send', {});
    expect(syncThreadDetailIntoDesk).toHaveBeenCalled();
    expect(fetchDashboard).toHaveBeenCalledWith('acc-1');
    expect(toast).toHaveBeenCalledWith('这份草稿已经寄出', 'success');
    expect(result.current.draftSendingId).toBe('');
  });

  it('refreshes the selected thread detail and thread list together', async () => {
    const toast = vi.fn();
    const fetchDashboard = vi.fn().mockResolvedValue(undefined);
    const fetchThreads = vi.fn().mockResolvedValue(undefined);
    const fetchThreadDetail = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useMailDeskThreadActions({
      request: async (fn) => fn(),
      toast,
      syncThreadDetailIntoDesk: vi.fn(),
      fetchDashboard,
      fetchThreads,
      fetchThreadDetail,
      refreshDeskSnapshot: vi.fn(),
      openDraftComposer: vi.fn(),
      selectedAccount: 'acc-1',
      selectedFolder: 'archive',
      selectedThreadId: 'thread-6',
      selectedThread: { thread_id: 'thread-6' },
      setSelectedThreadId: vi.fn(),
      setThreadDetail: vi.fn(),
    }));

    await act(async () => {
      await result.current.handleRefreshSelectedThread();
    });

    expect(fetchDashboard).toHaveBeenCalledWith('acc-1');
    expect(fetchThreads).toHaveBeenCalledWith('acc-1', 'archive');
    expect(fetchThreadDetail).toHaveBeenCalledWith('thread-6');
    expect(toast).toHaveBeenCalledWith('这封信的当前内容已经刷新', 'success');
    expect(result.current.threadRefreshing).toBe(false);
  });
});
