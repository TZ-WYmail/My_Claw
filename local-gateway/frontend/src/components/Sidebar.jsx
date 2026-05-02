import { useApp } from '../contexts';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { view: 'dashboard', icon: '📊', label: '仪表盘' },
  { view: 'tasks', icon: '📋', label: '任务' },
  { view: 'notes', icon: '📝', label: '笔记' },
  { view: 'habits', icon: '🎯', label: '习惯' },
  { view: 'calendar', icon: '📅', label: '日历' },
  { sep: true },
  { view: 'ai-chat', icon: '🤖', label: 'AI 对话' },
  { view: 'workflows', icon: '⚡', label: '工作流' },
  { view: 'sync', icon: '🔄', label: '同步' },
  { view: 'download', icon: '📥', label: '下载' },
  { view: 'sandbox', icon: '🔧', label: '沙盒' },
];

export default function Sidebar({ current, onNavigate, collapsed }) {
  const { connected, version } = useApp();

  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
      <div className={styles.header}>
        <span className={styles.logo}>🧠 LCC</span>
        {connected && !collapsed && <span className={styles.version}>v{version}</span>}
      </div>
      <nav className={styles.nav}>
        {NAV_ITEMS.map((item, i) =>
          item.sep ? <div key={i} className={styles.separator} /> : (
            <button key={item.view}
              className={`${styles.navItem} ${current === item.view ? styles.active : ''}`}
              onClick={() => onNavigate(item.view)}>
              <span className={styles.navIcon}>{item.icon}</span>
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          )
        )}
      </nav>
      <div className={styles.footer}>
        <button className={`${styles.navItem} ${current === 'settings' ? styles.active : ''}`}
          onClick={() => onNavigate('settings')}>
          <span className={styles.navIcon}>⚙️</span>
          <span className={styles.navLabel}>设置</span>
        </button>
        <div className={styles.statusRow}>
          <span className={`${styles.statusDot} ${connected ? styles.connected : ''}`} />
          <span style={{ fontSize: '0.75rem' }}>{connected ? '已连接' : '未连接'}</span>
        </div>
      </div>
    </aside>
  );
}
