import { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AppContext = createContext();

export function AppProvider({ children }) {
  const [connected, setConnected] = useState(false);
  const [version, setVersion] = useState('');
  const [refreshToken, setRefreshToken] = useState(0);

  const checkHealth = async () => {
    try {
      const data = await fetch('/health').then(r => r.json());
      setConnected(true);
      setVersion(data.version || '');
    } catch {
      setConnected(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 30000);
    return () => clearInterval(id);
  }, []);

  const notifyDataChange = useCallback(() => {
    setRefreshToken(token => token + 1);
  }, []);

  return <AppContext.Provider value={{ connected, version, refreshToken, notifyDataChange }}>{children}</AppContext.Provider>;
}

export const useApp = () => useContext(AppContext);
