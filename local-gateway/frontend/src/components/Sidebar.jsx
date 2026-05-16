import { useApp } from '../contexts';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { view: 'today', icon: '01', label: '今日作战室' },
  { view: 'tasks', icon: '02', label: '任务战线' },
  { view: 'calendar', icon: '03', label: '时间地图' },
  { view: 'notes', icon: '04', label: '情报档案' },
  { view: 'ai-chat', icon: '05', label: '参谋台' },
  { sep: true },
  { view: 'settings', icon: '06', label: '控制室' },
  { sep: true },
  { view: 'workflows', icon: '07', label: '自动化区' },
];

export default function Sidebar({ current, onNavigate, collapsed }) {
  const { connected, version } = useApp();

  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
      <div className={styles.header}>
        <div className={styles.brandMark}>LCC</div>
        <div className={styles.brandText}>
          <span className={styles.logo}>Local Command Center</span>
          {!collapsed && <span className={styles.brandSub}>Paper Ops Edition</span>}
        </div>
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
        <div className={styles.statusRow}>
          <span className={`${styles.statusDot} ${connected ? styles.connected : ''}`} />
          <span style={{ fontSize: '0.75rem' }}>{connected ? '已连接' : '未连接'}</span>
        </div>
      </div>
    </aside>
  );
}
