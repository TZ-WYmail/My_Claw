import { useState, useCallback } from 'react';

export async function apiGet(endpoint) {
  const resp = await fetch(endpoint);
  return resp.json();
}

export async function apiPost(endpoint, body) {
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return resp.json();
}

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const request = useCallback(async (fn) => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e.message || '请求失败');
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, request, setError };
}
