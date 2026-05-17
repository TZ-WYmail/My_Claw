import { ArchiveThreadRow, ThreadCard } from './maildeskShared.jsx';

export default function MailRailPanel({
  selectedFolder,
  selectedThreadId,
  selectedThreadIndex,
  threads,
  railThread,
  openPrevThread,
  openNextThread,
  setSelectedThreadId,
}) {
  const prevThread = selectedThreadIndex > 0 ? threads[selectedThreadIndex - 1] : null;
  const nextThread = selectedThreadIndex >= 0 && selectedThreadIndex < threads.length - 1 ? threads[selectedThreadIndex + 1] : null;

  return (
    <section className="board-lane atlas-paper-stack mail-spread-lane mail-rail-lane">
      <div className="board-lane-header mail-lane-header">
        <div className="mail-lane-head-copy">
          <div className="section-kicker">INBOX RAIL</div>
          <h3 className="board-lane-title">{selectedFolder === 'archive' ? '归档箱' : '来信匣'}</h3>
          <div className="board-lane-copy">
            {selectedFolder === 'archive'
              ? '归档箱不再维持工作流姿势，只保留一份安静的历史索引。你可以按时间翻检，但它们不该继续抢占案头。'
              : '这里改成像游戏里的选卡台。一次只看一封活跃线程，用上一封和下一封慢慢翻，不让长列表把注意力拖散。'}
          </div>
        </div>
        <div className="mail-lane-status">
          <div className="mail-lane-status-label">{selectedFolder === 'archive' ? '历史索引' : '翻页进度'}</div>
          <div className="mail-lane-status-value">
            {threads.length === 0
              ? '暂无线程'
              : (selectedFolder === 'archive'
                ? `${threads.length} 封已归档`
                : `第 ${Math.max(selectedThreadIndex + 1, 1)} / ${threads.length} 封`)}
          </div>
          <div className="mail-lane-status-copy">
            {selectedFolder === 'archive'
              ? '这些信只供回看，不继续占用当前工作台。'
              : '每次只翻一张卡，让注意力停在正在处理的那封来信上。'}
          </div>
        </div>
      </div>

      {threads.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">✉️</div>
          <div className="empty-state-text">案头还没有信</div>
          <div className="empty-state-hint">先接一个邮箱账户，或者从系统里写出第一封信。</div>
        </div>
      ) : (
        selectedFolder === 'archive' ? (
          <div className="signal-list mail-archive-list">
            {threads.map(thread => (
              <ArchiveThreadRow
                key={thread.thread_id}
                thread={thread}
                active={thread.thread_id === selectedThreadId}
                onOpen={setSelectedThreadId}
              />
            ))}
          </div>
        ) : (
          <div className="mail-rail-body">
            <div className="mail-rail-toolbar">
              <div className="mail-rail-toolbar-copy">
                活跃线程不会再拉成长长一列，而是像牌桌上一张张翻开。
              </div>
              <div className="inline-actions">
                <button className="btn btn-sm btn-ghost" onClick={openPrevThread} disabled={selectedThreadIndex <= 0}>上一封</button>
                <button className="btn btn-sm btn-ghost" onClick={openNextThread} disabled={selectedThreadIndex < 0 || selectedThreadIndex >= threads.length - 1}>下一封</button>
              </div>
            </div>

            {railThread && (
              <div className="mail-thread-stage mail-thread-stage-carousel">
                {prevThread && (
                  <div className="mail-thread-shadow-card mail-thread-shadow-card-prev" aria-hidden="true">
                    <ThreadCard
                      thread={prevThread}
                      active={false}
                      onOpen={setSelectedThreadId}
                    />
                  </div>
                )}
                <ThreadCard
                  key={railThread.thread_id}
                  thread={railThread}
                  active={railThread.thread_id === selectedThreadId}
                  onOpen={setSelectedThreadId}
                />
                {nextThread && (
                  <div className="mail-thread-shadow-card mail-thread-shadow-card-next" aria-hidden="true">
                    <ThreadCard
                      thread={nextThread}
                      active={false}
                      onOpen={setSelectedThreadId}
                    />
                  </div>
                )}
              </div>
            )}

            {threads.length > 1 && (
              <div className="mail-rail-pagination">
                {threads.map((thread, index) => (
                  <button
                    key={thread.thread_id}
                    type="button"
                    className={`badge ${thread.thread_id === selectedThreadId ? 'badge-warning' : 'badge-ghost'}`}
                    onClick={() => setSelectedThreadId(thread.thread_id)}
                    style={{ cursor: 'pointer' }}
                    title={thread.subject}
                  >
                    {index + 1}
                  </button>
                ))}
              </div>
            )}
          </div>
        )
      )}
    </section>
  );
}
