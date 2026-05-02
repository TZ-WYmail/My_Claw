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

function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentView, setCurrentView] = useState(() => {
    return window.location.hash.slice(1) || 'dashboard';
  });

  const navigate = useCallback((view) => {
    setCurrentView(view);
    window.location.hash = view;
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      setCurrentView(window.location.hash.slice(1) || 'dashboard');
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
      if (meta && !shift && key === 'n') { e.preventDefault(); navigate('tasks'); return; }
      if (meta && shift && key === 'n') { e.preventDefault(); navigate('notes'); return; }
      const vm = { '1': 'dashboard', '2': 'tasks', '3': 'notes', '4': 'habits', '5': 'calendar' };
      if (meta && vm[key]) { e.preventDefault(); navigate(vm[key]); }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [navigate]);

  const renderView = () => {
    switch (currentView) {
      case 'tasks': return <Tasks />;
      case 'notes': return <Notes />;
      case 'habits': return <Habits />;
      case 'calendar': return <Calendar />;
      case 'ai-chat': return <AiChat />;
      case 'workflows': return <Workflows />;
      case 'sync': return <Sync />;
      case 'download': return <Download />;
      case 'sandbox': return <Sandbox />;
      case 'settings': return <Settings />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className={styles.appShell}>
      <Sidebar current={currentView} onNavigate={navigate}
        collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(c => !c)} />
      <main className={styles.mainArea}>
        <TopBar currentView={currentView} onToggleSidebar={() => setSidebarCollapsed(c => !c)} />
        <div className={styles.viewContainer}>
          {renderView()}
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
