/**
 * Service Worker for LocalCommandCenter PWA
 * 支持离线缓存、后台同步、推送通知
 */

const CACHE_NAME = 'lcc-cache-v1';
const STATIC_ASSETS = [
  '/',
  '/static/index.html',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
];

// API 缓存配置
const API_CACHE_NAME = 'lcc-api-cache-v1';
const API_ROUTES = [
  '/api/task',
  '/api/tasks/all',
  '/api/advanced/tags',
  '/api/notes',
  '/api/habits',
];

// ============================================================
// 安装阶段 — 缓存静态资源
// ============================================================
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
      .catch((err) => console.error('[SW] Cache failed:', err))
  );
});

// ============================================================
// 激活阶段 — 清理旧缓存
// ============================================================
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');

  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
            .map((name) => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => self.clients.claim())
  );
});

// ============================================================
// 拦截请求 — 缓存策略
// ============================================================
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 跳过非 GET 请求
  if (request.method !== 'GET') {
    return;
  }

  // API 请求 — 网络优先，失败时回退到缓存
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // 静态资源 — 缓存优先
  event.respondWith(cacheFirst(request));
});

// 缓存优先策略
async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);

  if (cached) {
    // 后台更新缓存
    fetch(request)
      .then((response) => {
        if (response.ok) {
          cache.put(request, response.clone());
        }
      })
      .catch(() => {});

    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    console.error('[SW] Fetch failed:', err);
    return new Response('Offline', { status: 503 });
  }
}

// 网络优先策略
async function networkFirst(request) {
  const cache = await caches.open(API_CACHE_NAME);

  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      // 更新缓存
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (err) {
    console.log('[SW] Network failed, trying cache:', request.url);
    const cached = await cache.match(request);

    if (cached) {
      return cached;
    }

    return new Response(
      JSON.stringify({ error: 'Offline', status: 'error' }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}

// ============================================================
// 后台同步 — 离线操作队列
// ============================================================
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync:', event.tag);

  if (event.tag === 'sync-offline-operations') {
    event.waitUntil(syncOfflineOperations());
  }
});

// 同步离线操作
async function syncOfflineOperations() {
  try {
    const response = await fetch('/api/sync/offline/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    const result = await response.json();
    console.log('[SW] Offline sync result:', result);

    // 通知客户端
    const clients = await self.clients.matchAll();
    clients.forEach((client) => {
      client.postMessage({
        type: 'SYNC_COMPLETE',
        result,
      });
    });

    return result;
  } catch (err) {
    console.error('[SW] Offline sync failed:', err);
    throw err;
  }
}

// ============================================================
// 推送通知
// ============================================================
self.addEventListener('push', (event) => {
  console.log('[SW] Push received:', event);

  let data = {};
  try {
    data = event.data.json();
  } catch {
    data = { title: 'LocalCommandCenter', body: event.data.text() };
  }

  const options = {
    body: data.body || '您有新的通知',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    tag: data.tag || 'default',
    requireInteraction: data.requireInteraction || false,
    actions: data.actions || [],
    data: data.data || {},
  };

  event.waitUntil(
    self.registration.showNotification(
      data.title || 'LocalCommandCenter',
      options
    )
  );
});

// 点击通知
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification click:', event);

  event.notification.close();

  const notificationData = event.notification.data;
  let targetUrl = '/';

  if (notificationData?.taskId) {
    targetUrl = `/?task=${notificationData.taskId}`;
  } else if (notificationData?.noteId) {
    targetUrl = `/?note=${notificationData.noteId}`;
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window' })
      .then((clientList) => {
        // 如果有打开的窗口，聚焦它
        for (const client of clientList) {
          if (client.url === targetUrl && 'focus' in client) {
            return client.focus();
          }
        }
        // 否则打开新窗口
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
      })
  );
});

// ============================================================
// 消息处理 — 与页面通信
// ============================================================
self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);

  const { type, payload } = event.data;

  switch (type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;

    case 'SYNC_NOW':
      syncOfflineOperations();
      break;

    case 'CACHE_OFFLINE_OPERATION':
      cacheOfflineOperation(payload);
      break;

    default:
      console.log('[SW] Unknown message type:', type);
  }
});

// 缓存离线操作
async function cacheOfflineOperation(operation) {
  try {
    const cache = await caches.open('offline-operations');
    const request = new Request('/offline-operation/' + Date.now(), {
      method: 'POST',
      body: JSON.stringify(operation),
    });
    await cache.put(request, new Response(JSON.stringify({ cached: true })));

    // 注册后台同步
    if ('sync' in self.registration) {
      await self.registration.sync.register('sync-offline-operations');
    }
  } catch (err) {
    console.error('[SW] Cache operation failed:', err);
  }
}

console.log('[SW] Service Worker loaded');
