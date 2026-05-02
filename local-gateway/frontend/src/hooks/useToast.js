import { useContext, useCallback } from 'react';
import { ToastContext } from '../contexts/ToastContext';

export function useToast() {
  const addToast = useContext(ToastContext);
  if (!addToast) throw new Error('useToast must be inside ToastProvider');
  return useCallback((msg, type = 'info') => addToast(msg, type), [addToast]);
}
