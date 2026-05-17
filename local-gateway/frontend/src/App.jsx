import { useState, useEffect, useCallback } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { AppProvider } from './contexts/AppContext';
import { ToastProvider } from './contexts/ToastContext';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Dashboard from './pages/Dashboard';
import Tasks from './pages/Tasks';
import Notes from './pages/Notes';
import Habits from './pages/Habits';
import Calendar from './pages/Calendar';
import AiChat from './pages/AiChat';
import Workflows from './pages/Workflows';
import Sync from './pages/Sync';
import Download from './pages/Download';
import Sandbox from './pages/Sandbox';
import Settings from './pages/Settings';
import styles from './App.module.css';

function normalizeView(view) {
  if (!view || view === 'dashboard') return 'today';
  return view;
}

function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentView, setCurrentView] = useState(() => {
    return normalizeView(window.location.hash.slice(1));
  });
  const [quickAction, setQuickAction] = useState(null);

  const navigate = useCallback((view, action = null) => {
    const nextView = normalizeView(view);
    setCurrentView(nextView);
    setQuickAction(action ? { ...action, id: Date.now() } : null);
    window.location.hash = nextView;
  }, []);

  const openCreateTask = useCallback((prefill = null) => {
    navigate('tasks', { type: 'create_task', prefill });
  }, [navigate]);

  const openCreateNote = useCallback(() => {
    navigate('notes', { type: 'create_note' });
  }, [navigate]);

  const openCreateNoteFromTask = useCallback((task) => {
    navigate('notes', { type: 'create_note_from_task', task });
  }, [navigate]);

  const openTaskDetail = useCallback((task) => {
    navigate('tasks', { type: 'focus_task', task });
  }, [navigate]);

  const openAiIntent = useCallback((intent = null) => {
    navigate('ai-chat', intent ? { type: 'ai_intent', ...intent } : null);
  }, [navigate]);

  useEffect(() => {
    const onHashChange = () => {
      setCurrentView(normalizeView(window.location.hash.slice(1)));
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      const key = e.key.toLowerCase();
      const meta = e.metaKey || e.ctrlKey;
      const shift = e.shiftKey;
      if (meta && key === 'b') { e.preventDefault(); setSidebarCollapsed(c => !c); return; }
      if (meta && key === 'k') { e.preventDefault(); document.getElementById('global-search')?.focus(); return; }
      if (meta && key === 'j') { e.preventDefault(); navigate('ai-chat'); return; }
      if (meta && !shift && key === 'n') { e.preventDefault(); navigate('tasks', { type: 'create_task' }); return; }
      if (meta && shift && key === 'n') { e.preventDefault(); navigate('notes', { type: 'create_note' }); return; }
      const vm = { '1': 'today', '2': 'tasks', '3': 'calendar', '4': 'notes', '5': 'ai-chat' };
      if (meta && vm[key]) { e.preventDefault(); navigate(vm[key]); }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [navigate]);

  const renderView = () => {
    switch (currentView) {
      case 'today': return (
        <Dashboard
          onCreateTask={() => openCreateTask()}
          onCreateNote={openCreateNote}
          onOpenAi={openAiIntent}
          onOpenTasks={() => navigate('tasks')}
          onOpenCalendar={() => navigate('calendar')}
          onOpenNotes={() => navigate('notes')}
          onCreateTaskNote={openCreateNoteFromTask}
          onOpenTaskDetail={openTaskDetail}
        />
      );
      case 'tasks': return (
        <Tasks
          quickAction={quickAction}
          clearQuickAction={() => setQuickAction(null)}
          onCreateNoteFromTask={openCreateNoteFromTask}
        />
      );
      case 'notes': return (
        <Notes
          quickAction={quickAction}
          clearQuickAction={() => setQuickAction(null)}
          onOpenTask={openTaskDetail}
        />
      );
      case 'habits': return <Habits />;
      case 'calendar': return (
        <Calendar
          onCreateTaskForDate={(date) => openCreateTask({ date })}
          onCreateNoteFromTask={openCreateNoteFromTask}
          onOpenTasks={() => navigate('tasks')}
          onOpenTask={openTaskDetail}
        />
      );
      case 'ai-chat': return (
        <AiChat
          quickAction={quickAction}
          clearQuickAction={() => setQuickAction(null)}
        />
      );
      case 'workflows': return <Workflows />;
      case 'sync': return <Sync />;
      case 'download': return (
        <Download
          quickAction={quickAction}
          clearQuickAction={() => setQuickAction(null)}
          onOpenNotifyNetwork={() => navigate('settings', { type: 'open_notify_network' })}
          onOpenAi={openAiIntent}
          onOpenTask={openTaskDetail}
          onCreateNoteFromTask={openCreateNoteFromTask}
        />
      );
      case 'sandbox': return <Sandbox />;
      case 'settings': return <Settings quickAction={quickAction} clearQuickAction={() => setQuickAction(null)} />;
      default: return (
        <Dashboard
          onCreateTask={() => openCreateTask()}
          onCreateNote={openCreateNote}
          onOpenAi={openAiIntent}
          onOpenTasks={() => navigate('tasks')}
          onOpenCalendar={() => navigate('calendar')}
          onOpenNotes={() => navigate('notes')}
          onCreateTaskNote={openCreateNoteFromTask}
          onOpenTaskDetail={openTaskDetail}
        />
      );
    }
  };

  return (
    <div className={styles.appShell}>
      <Sidebar current={currentView} onNavigate={navigate}
        collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(c => !c)} />
      <main className={styles.mainArea}>
        <div className={`atlas-spread ${styles.spreadFrame}`} />
        <div className={styles.spreadInner}>
          <TopBar
            currentView={currentView}
            onToggleSidebar={() => setSidebarCollapsed(c => !c)}
            onCreateTask={() => openCreateTask()}
            onCreateNote={openCreateNote}
            onOpenAi={() => openAiIntent()}
          />
          <div className={styles.viewContainer}>
            {renderView()}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppProvider>
        <ToastProvider>
          <AppShell />
        </ToastProvider>
      </AppProvider>
    </ThemeProvider>
  );
}
