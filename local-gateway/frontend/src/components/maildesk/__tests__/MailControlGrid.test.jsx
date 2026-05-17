import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import MailControlGrid from '../MailControlGrid';

function renderGrid(overrides = {}) {
  const props = {
    activeAccount: { account_id: 'acc-1', display_name: 'Primary', email_address: 'user@example.com', auto_mail_policy: 'draft_and_notify' },
    accountTestResult: null,
    accountTesting: false,
    accounts: [{ account_id: 'acc-1', display_name: 'Primary', email_address: 'user@example.com' }],
    handleAccountTest: vi.fn(),
    handlePollingConfigChange: vi.fn(),
    pollingFeedback: { tone: 'success', message: '轮询配置已保存', savedAt: '2026-05-17T12:00:00Z' },
    pollingResults: [],
    pollingSaving: false,
    pollingState: {
      enabled: true,
      interval_seconds: 300,
      folder_kind: 'inbox',
      limit: 20,
      is_running: false,
      last_started_at: '',
      last_finished_at: '',
      last_success_at: '2026-05-17T11:00:00Z',
      last_error: '',
      last_summary: {
        account_count: 1,
        success_count: 1,
        error_count: 0,
        new_count: 2,
        skipped_count: 0,
      },
    },
    pollingSummary: {
      account_count: 1,
      success_count: 1,
      error_count: 0,
      new_count: 2,
      skipped_count: 0,
    },
    pollingFolderOptions: [{ value: 'inbox', label: '收件箱' }],
    requestOpenNotifyNetwork: vi.fn(),
    syncStatus: { finished_at: '2026-05-17T11:30:00Z', status: 'success', folder_kind: 'inbox', fetched_count: 3, new_count: 2 },
    threadFilters: {
      query: '',
      unreadOnly: false,
      needsReplyOnly: false,
      waitingDecisionOnly: false,
      scheduledOnly: false,
      failedDraftOnly: false,
    },
    setThreadFilters: vi.fn(),
    refreshDeskThreads: vi.fn(),
    deskRefreshing: false,
    ...overrides,
  };

  const setPollingStateSpy = vi.fn();

  function Harness() {
    const [pollingState, setPollingState] = useState(props.pollingState);
    const [threadFilters, setThreadFilters] = useState(props.threadFilters);

    return (
      <MailControlGrid
        {...props}
        pollingState={pollingState}
        threadFilters={threadFilters}
        setPollingState={(updater) => {
          setPollingState((prev) => {
            const next = typeof updater === 'function' ? updater(prev) : updater;
            setPollingStateSpy(next);
            return next;
          });
        }}
        setThreadFilters={(updater) => {
          setThreadFilters((prev) => (typeof updater === 'function' ? updater(prev) : updater));
          props.setThreadFilters(updater);
        }}
      />
    );
  }

  render(<Harness />);
  props.setPollingState = setPollingStateSpy;
  return props;
}

describe('MailControlGrid', () => {
  it('shows polling feedback and summary cards', () => {
    renderGrid();

    expect(screen.getByText((content) => content.includes('轮询配置已保存'))).toBeInTheDocument();
    expect(screen.getByText('扫描账户')).toBeInTheDocument();
    expect(screen.getByText('新增来信')).toBeInTheDocument();
    expect(screen.getByText('后台轮询已开启')).toBeInTheDocument();
  });

  it('toggles thread filters and refresh action', () => {
    const props = renderGrid();

    fireEvent.click(screen.getByRole('button', { name: '只看未读' }));
    fireEvent.click(screen.getByRole('button', { name: '刷新案头' }));

    expect(props.setThreadFilters).toHaveBeenCalled();
    expect(props.refreshDeskThreads).toHaveBeenCalledTimes(1);
  });

  it('writes polling interval back on blur', () => {
    const props = renderGrid();
    const intervalInput = screen.getByDisplayValue('300');

    fireEvent.change(intervalInput, { target: { value: '120' } });
    fireEvent.blur(intervalInput);

    expect(props.setPollingState).toHaveBeenCalled();
    expect(props.handlePollingConfigChange).toHaveBeenCalledWith({ interval_seconds: 120 });
  });
});
