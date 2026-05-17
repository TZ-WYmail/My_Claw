import { act, renderHook } from '@testing-library/react';
import { useMailDeskDerivedState } from '../useMailDeskDerivedState';

function createThread(id, extras = {}) {
  return {
    thread_id: id,
    account_id: 'acc-1',
    subject: `Subject ${id}`,
    snippet: `Snippet ${id}`,
    latest_folder_kind: 'inbox',
    latest_message_at: '2026-05-17T10:00:00Z',
    waiting_user_decision: false,
    participants: [{ name: `User ${id}`, email: `${id}@example.com` }],
    mail_kind: 'planning',
    reply_level: 'must_reply',
    analysis_reason: 'Need reply',
    ...extras,
  };
}

describe('useMailDeskDerivedState', () => {
  it('filters agent runs and derives selected thread state', () => {
    const setSelectedThreadId = vi.fn();
    const onOpenAi = vi.fn();
    const threads = [
      createThread('thread-1', { waiting_user_decision: true }),
      createThread('thread-2'),
    ];
    const threadDetail = {
      thread: threads[0],
      messages: [
        {
          direction: 'inbound',
          text_body: 'Please confirm the schedule.',
          html_body: '',
        },
      ],
      agent_runs: [
        { run_id: 'run-1', status: 'draft_created' },
        { run_id: 'run-2', status: 'sent' },
      ],
    };

    const { result } = renderHook(() => useMailDeskDerivedState({
      accounts: [{ account_id: 'acc-1', email_address: 'owner@example.com' }],
      threads,
      threadDetail,
      activeDraft: {
        subject: 'Re: Subject thread-1',
        to: [{ email: 'reply@example.com' }],
      },
      agentRunFilter: 'sent',
      selectedThreadId: 'thread-1',
      taskComposerThreadId: 'thread-2',
      onOpenAi,
      setSelectedThreadId,
    }));

    expect(result.current.selectedAgentRuns).toEqual([{ run_id: 'run-2', status: 'sent' }]);
    expect(result.current.decisionQueue).toHaveLength(1);
    expect(result.current.selectedThreadIndex).toBe(0);
    expect(result.current.railThread?.thread_id).toBe('thread-1');
    expect(result.current.selectedThread?.thread_id).toBe('thread-1');
    expect(result.current.taskComposerThread?.thread_id).toBe('thread-2');
    expect(result.current.selectedThreadAccount?.account_id).toBe('acc-1');
    expect(result.current.latestAgentRun?.run_id).toBe('run-1');
    expect(result.current.selectedMailtoHref).toBe('mailto:reply@example.com?subject=Re%3A+Subject+thread-1');

    act(() => {
      result.current.handleDiscussWithAi(threads[0]);
      result.current.openNextThread();
    });

    expect(onOpenAi).toHaveBeenCalledWith(expect.objectContaining({
      intent: 'mail_consult',
      thread: threads[0],
    }));
    expect(onOpenAi.mock.calls[0][0].draftInput).toContain('Please confirm the schedule.');
    expect(setSelectedThreadId).toHaveBeenCalledWith('thread-2');
  });

  it('opens previous thread when selection is not at first item', () => {
    const setSelectedThreadId = vi.fn();
    const threads = [createThread('thread-1'), createThread('thread-2'), createThread('thread-3')];

    const { result } = renderHook(() => useMailDeskDerivedState({
      accounts: [],
      threads,
      threadDetail: { thread: threads[1], messages: [], agent_runs: [] },
      activeDraft: null,
      agentRunFilter: 'all',
      selectedThreadId: 'thread-2',
      taskComposerThreadId: '',
      onOpenAi: null,
      setSelectedThreadId,
    }));

    act(() => {
      result.current.openPrevThread();
    });

    expect(setSelectedThreadId).toHaveBeenCalledWith('thread-1');
  });
});
