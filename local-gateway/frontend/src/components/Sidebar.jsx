import { useApp } from '../contexts';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { view: 'today', icon: '01', label: '今日展开页' },
  { view: 'tasks', icon: '02', label: '排程折页' },
  { view: 'calendar', icon: '03', label: '月度地图' },
  { view: 'notes', icon: '04', label: '档案剪报' },
  { view: 'ai-chat', icon: '05', label: '参谋手稿' },
  { sep: true },
  { view: 'workflows', icon: '07', label: '自动化区' },
  { view: 'sync', icon: '08', label: '回传台账' },
  { view: 'download', icon: '09', label: '转运页' },
  { view: 'sandbox', icon: '10', label: '试验托盘' },
  { view: 'habits', icon: '11', label: '训练轨迹' },
  { sep: true },
  { view: 'settings', icon: '12', label: '接线检定' },
];

export default function Sidebar({ current, onNavigate, collapsed }) {
  const { connected, version } = useApp();

  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
      <div className={styles.header}>
        <div className={styles.brandMark}>LCC</div>
        <div className={styles.brandText}>
          <span className={styles.logo}>Atlas Desk</span>
          {!collapsed && <span className={styles.brandSub}>Local Command Center</span>}
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
          <span style={{ fontSize: '0.75rem' }}>{connected ? '节点在线' : '节点离线'}</span>
        </div>
      </div>
    </aside>
  );
}
