import { fireEvent, render, screen } from '@testing-library/react';
import MailRailPanel from '../MailRailPanel';

function createThread(id, subject, extras = {}) {
  return {
    thread_id: id,
    subject,
    participants: [{ name: `${subject} Sender`, email: `${id}@example.com` }],
    needs_reply: true,
    latest_message_at: '2026-05-17T10:00:00Z',
    latest_folder_kind: 'inbox',
    ...extras,
  };
}

describe('MailRailPanel', () => {
  it('renders carousel progress and navigates previous/next thread', () => {
    const threads = [
      createThread('thread-1', 'First letter'),
      createThread('thread-2', 'Second letter'),
      createThread('thread-3', 'Third letter'),
    ];
    const openPrevThread = vi.fn();
    const openNextThread = vi.fn();
    const setSelectedThreadId = vi.fn();

    render(
      <MailRailPanel
        selectedFolder=""
        selectedThreadId="thread-2"
        selectedThreadIndex={1}
        threads={threads}
        railThread={threads[1]}
        openPrevThread={openPrevThread}
        openNextThread={openNextThread}
        setSelectedThreadId={setSelectedThreadId}
      />,
    );

    expect(screen.getByText('第 2 / 3 封')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上一封' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '下一封' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: '上一封' }));
    fireEvent.click(screen.getByRole('button', { name: '下一封' }));
    fireEvent.click(screen.getByRole('button', { name: '3' }));

    expect(openPrevThread).toHaveBeenCalledTimes(1);
    expect(openNextThread).toHaveBeenCalledTimes(1);
    expect(setSelectedThreadId).toHaveBeenCalledWith('thread-3');
  });

  it('renders archive list without carousel controls', () => {
    const threads = [
      createThread('thread-1', 'Archived one', { latest_folder_kind: 'archive' }),
      createThread('thread-2', 'Archived two', { latest_folder_kind: 'archive' }),
    ];

    render(
      <MailRailPanel
        selectedFolder="archive"
        selectedThreadId="thread-1"
        selectedThreadIndex={0}
        threads={threads}
        railThread={threads[0]}
        openPrevThread={vi.fn()}
        openNextThread={vi.fn()}
        setSelectedThreadId={vi.fn()}
      />,
    );

    expect(screen.getByText('归档箱')).toBeInTheDocument();
    expect(screen.getByText('2 封已归档')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '上一封' })).not.toBeInTheDocument();
  });
});
