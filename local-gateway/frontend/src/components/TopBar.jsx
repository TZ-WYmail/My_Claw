import { useTheme } from '../contexts';
import styles from './TopBar.module.css';

const VIEW_NAMES = {
  today: '今日展开页',
  tasks: '排程折页',
  notes: '档案剪报',
  habits: '训练轨迹板',
  calendar: '月度地图',
  'ai-chat': '参谋手稿台',
  workflows: '装配步骤册',
  sync: '回传收发台',
  download: '港口调度页',
  sandbox: '试验托盘',
  settings: '接线检定页',
};

const VIEW_NOTES = {
  today: '主线、风险与今日动作',
  tasks: '周内排程与任务档案',
  notes: '记录、线索与关联任务',
  habits: '连续行为与训练刻痕',
  calendar: '时间地块与事件图钉',
  'ai-chat': '保留现有工作台，仅做母体适配',
  workflows: '触发器、动作与执行记录',
  sync: '设备状态、同步动作与离线回传',
  download: '下载队列、分类与带宽控制',
  sandbox: '代码试验、运行与输出观察',
  settings: 'AI 参数、通知与连通测试',
};

export default function TopBar({ currentView, onToggleSidebar, onCreateTask, onCreateNote, onOpenAi }) {
  const { theme, toggleTheme } = useTheme();
  const today = new Date();
  const dateLabel = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(today.getDate()).padStart(2, '0')}`;

  return (
    <div className={styles.topBar}>
      <div className={styles.left}>
        <button className={styles.toggle} onClick={onToggleSidebar} title="⌘B 折叠侧边栏">☰</button>
        <div>
          <div className={styles.kicker}>Atlas Desk Chapter</div>
          <h2>{VIEW_NAMES[currentView] || currentView}</h2>
          <div className={styles.metaLine}>
            <span className={styles.metaPill}>页签 {currentView}</span>
            <span className={styles.metaPill}>{dateLabel}</span>
            <span className={styles.metaPill}>{VIEW_NOTES[currentView] || '章节视图'}</span>
          </div>
        </div>
      </div>
      <div className={styles.right}>
        <input id="global-search" className={styles.search} type="text"
          placeholder="⌘K 检索页签、任务、记录..." autoComplete="off" />
        <button className="btn btn-ghost btn-sm" onClick={onCreateTask}>+ 任务</button>
        <button className="btn btn-ghost btn-sm" onClick={onCreateNote}>+ 笔记</button>
        <button className="btn btn-primary btn-sm" onClick={onOpenAi}>AI 参谋</button>
        <button className="btn btn-ghost btn-sm" onClick={toggleTheme}
          title={theme === 'dark' ? '切换亮色主题' : '切换暗色主题'}>
          {theme === 'dark' ? '日' : '夜'}
        </button>
      </div>
    </div>
  );
}
