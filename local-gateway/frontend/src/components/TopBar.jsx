import { useTheme } from '../contexts';
import styles from './TopBar.module.css';

const VIEW_NAMES = {
  dashboard: '仪表盘', tasks: '任务', notes: '笔记', habits: '习惯',
  calendar: '日历', 'ai-chat': 'AI 对话', workflows: '工作流',
  sync: '同步', download: '下载', sandbox: '沙盒', settings: '设置',
};

export default function TopBar({ currentView, onToggleSidebar }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className={styles.topBar}>
      <div className={styles.left}>
        <button className={styles.toggle} onClick={onToggleSidebar} title="⌘B 折叠侧边栏">☰</button>
        <h2>{VIEW_NAMES[currentView] || currentView}</h2>
      </div>
      <div className={styles.right}>
        <input id="global-search" className={styles.search} type="text"
          placeholder="⌘K 搜索..." autoComplete="off" />
        <button className="btn btn-ghost btn-sm" onClick={toggleTheme}
          title={theme === 'dark' ? '切换亮色主题' : '切换暗色主题'}>
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </div>
    </div>
  );
}
