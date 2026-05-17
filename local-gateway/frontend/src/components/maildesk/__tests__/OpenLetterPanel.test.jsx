import { fireEvent, render, screen } from '@testing-library/react';
import OpenLetterPanel from '../OpenLetterPanel';

function createRun(id, status, extras = {}) {
  return {
    run_id: id,
    action_kind: 'auto_reply',
    status,
    result_summary: `${status} summary`,
    updated_at: '2026-05-17T12:00:00Z',
    details: {},
    ...extras,
  };
}

function createThread(overrides = {}) {
  return {
    thread_id: 'thread-1',
    account_id: 'acc-1',
    subject: 'Need confirmation on schedule',
    latest_folder_kind: 'inbox',
    latest_message_at: '2026-05-17T10:00:00Z',
    unread_count: 1,
    needs_reply: true,
    waiting_user_decision: true,
    decision_status: 'pending',
    has_pending_draft: true,
    has_new_inbound: true,
    linked_task_count: 1,
    last_actor: 'counterparty',
    analysis_reason: '对方在确认下周安排，需要继续协商。',
    reply_level: 'must_reply',
    risk_level: 'high',
    mail_kind: 'planning',
    portal_url: 'https://portal.example.com/thread-1',
    participants: [{ name: 'Alex', email: 'alex@example.com' }],
    ...overrides,
  };
}

function createDetail(overrides = {}) {
  return {
    messages: [
      {
        message_id: 'msg-inbound',
        direction: 'inbound',
        from_name: 'Alex',
        from_email: 'alex@example.com',
        subject: 'Need confirmation on schedule',
        received_at: '2026-05-17T09:30:00Z',
        text_body: 'Please confirm schedule at https://example.com/confirm and cc alex@example.com',
        html_body: '',
        to: [],
        cc: [],
        bcc: [],
        reply_to: [],
        attachments: [],
      },
    ],
    drafts: [
      {
        draft_id: 'draft-1',
        account_id: 'acc-1',
        thread_id: 'thread-1',
        subject: 'Re: Need confirmation on schedule',
        body_html: 'Draft body with <a href="https://draft.example.com">link</a>',
        to: [{ email: 'alex@example.com', name: 'Alex' }],
        cc: [],
        bcc: [],
        signature: 'Regards',
        tone_mode: 'warm',
        status: 'queued',
        ai_generated: true,
        user_edited_after_ai: false,
        scheduled_send_at: '',
      },
    ],
    agent_runs: [
      createRun('run-1', 'draft_created', { details: { policy: 'draft_only', command: 'draft_reply' } }),
      createRun('run-2', 'sent', { details: { policy: 'auto_send', command: 'draft_reply', draft_id: 'draft-1' } }),
    ],
    task_summaries: [
      {
        link_id: 'link-1',
        task_id: 'task-1',
        task_name: 'Confirm next week schedule',
        status: 'pending',
        priority: 1,
        description: 'Follow up based on inbound email.',
        due_time: '2026-05-18T09:00:00Z',
      },
    ],
    ...overrides,
  };
}

function renderPanel(overrides = {}) {
  const selectedThread = createThread(overrides.selectedThread);
  const threadDetail = createDetail(overrides.threadDetail);
  const props = {
    selectedFolder: '',
    selectedThread,
    selectedThreadAccount: {
      account_id: 'acc-1',
      email_address: 'owner@example.com',
      auto_mail_policy: 'draft_and_notify',
    },
    selectedMailtoHref: 'mailto:alex@example.com?subject=Re%3A%20Need%20confirmation%20on%20schedule',
    threadRefreshing: false,
    threadDetailLoading: false,
    activeDraft: threadDetail.drafts[0],
    latestAgentRun: threadDetail.agent_runs[0],
    threadDetail,
    archivingThreadId: '',
    markingReadThreadId: '',
    decisionUpdating: { threadId: '', status: '' },
    replyDraftGeneratingThreadId: '',
    taskCreatingThreadId: '',
    draftSendingId: '',
    selectedAgentRuns: threadDetail.agent_runs,
    agentRunFilter: 'all',
    agentRunsLoading: false,
    openPortalPage: vi.fn(),
    copyPortalLink: vi.fn(),
    handleRefreshSelectedThread: vi.fn(),
    handleMarkRead: vi.fn(),
    handleArchive: vi.fn(),
    handleDecisionStatus: vi.fn(),
    handleReplyThread: vi.fn(),
    handleGenerateReplyDraft: vi.fn(),
    handleCreateTaskFromMail: vi.fn(),
    handleDiscussWithAi: vi.fn(),
    fetchAgentRuns: vi.fn(),
    setAgentRunFilter: vi.fn(),
    onOpenDraftComposer: vi.fn(),
    onSendDraft: vi.fn(),
    onOpenTask: vi.fn(),
    onCreateNoteFromTask: vi.fn(),
    ...overrides,
  };

  render(<OpenLetterPanel {...props} />);
  return props;
}

describe('OpenLetterPanel', () => {
  it('renders mail-first entry actions and uses handlers', () => {
    const props = renderPanel();

    const portalButton = screen.getByRole('button', { name: '打开处理页' });
    const copyButton = screen.getByRole('button', { name: '复制处理页链接' });
    const mailtoLink = screen.getByRole('link', { name: '在邮箱里继续回' });

    expect(mailtoLink).toHaveAttribute('href', 'mailto:alex@example.com?subject=Re%3A%20Need%20confirmation%20on%20schedule');

    fireEvent.click(portalButton);
    fireEvent.click(copyButton);

    expect(props.openPortalPage).toHaveBeenCalledWith(expect.objectContaining({ thread_id: 'thread-1' }));
    expect(props.copyPortalLink).toHaveBeenCalledWith(expect.objectContaining({ thread_id: 'thread-1' }));
  });

  it('renders agent ledger rows and delegates filter changes', () => {
    const props = renderPanel({
      selectedAgentRuns: [createRun('run-2', 'sent', { details: { reason_code: 'policy_auto_send', draft_id: 'draft-1' } })],
      agentRunFilter: 'sent',
    });

    expect(screen.getByText('AGENT LEDGER')).toBeInTheDocument();
    expect(screen.getByText('1 / 2 条记录')).toBeInTheDocument();
    expect(screen.getByText('sent summary')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全部记录' }));
    fireEvent.click(screen.getByRole('button', { name: '刷新台账' }));

    expect(props.setAgentRunFilter).toHaveBeenCalledWith('all');
    expect(props.fetchAgentRuns).toHaveBeenCalledWith('thread-1');
  });

  it('renders draft and message links as safe anchors', () => {
    renderPanel();

    expect(screen.getByRole('link', { name: 'link' })).toHaveAttribute('href', 'https://draft.example.com/');
    expect(screen.getByRole('link', { name: 'https://example.com/confirm' })).toHaveAttribute('href', 'https://example.com/confirm');
    expect(screen.getByRole('link', { name: 'alex@example.com' })).toHaveAttribute('href', 'mailto:alex@example.com');
  });
});
