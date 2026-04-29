# Phase 4: 多端统一 - 详细实现文档

> 目标: 支持多设备，数据无缝同步
> 预计工期: 10-12周
> 版本目标: v1.0.0 (正式版)
> 依赖: Phase 1-3完成

---

## 一、本阶段目标

### 1.1 核心交付物

| 类别 | 交付物 | 验收标准 |
|------|--------|----------|
| 移动端 | Flutter App | iOS/Android双平台，核心功能可用 |
| 数据同步 | 同步协议 | 离线可用，自动合并冲突 |
| PWA | 可安装Web应用 | 离线缓存，推送通知 |
| 桌面端 | 打包分发 | Windows/Mac/Linux安装包 |
| 安全 | 端到端加密 | 同步数据加密存储 |

### 1.2 用户价值

完成Phase 4后，用户可以：
- 在手机端查看和管理任务
- 离线时仍可创建任务，联网后自动同步
- 将Web应用安装到桌面/手机主屏
- 跨设备无缝切换工作场景

---

## 二、移动端App (Flutter)

### 2.1 技术选型

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 原生 (Swift/Kotlin) | 性能最好 | 两套代码 | 不考虑 |
| Flutter | 跨平台、UI统一 | 包体积较大 | **推荐** |
| React Native | 生态丰富 | 性能一般 | 备选 |
| 小程序 | 无需安装 | 功能受限 | 未来扩展 |

**选择: Flutter 3.x**
- 单一代码库，iOS/Android/Web
- 性能接近原生
- 丰富的组件库

### 2.2 项目结构

```
mobile/
├── lib/
│   ├── main.dart                 # 入口
│   ├── app.dart                  # 应用根组件
│   ├── core/                     # 核心基础设施
│   │   ├── api_client.dart       # API客户端
│   │   ├── sync_engine.dart      # 同步引擎
│   │   ├── local_db.dart         # SQLite本地数据库
│   │   └── auth.dart             # 认证管理
│   ├── models/                   # 数据模型
│   │   ├── task.dart
│   │   ├── habit.dart
│   │   └── note.dart
│   ├── providers/                # 状态管理 (Riverpod)
│   │   ├── task_provider.dart
│   │   └── sync_provider.dart
│   ├── screens/                  # 页面
│   │   ├── home_screen.dart
│   │   ├── task_list_screen.dart
│   │   ├── task_detail_screen.dart
│   │   ├── calendar_screen.dart
│   │   └── settings_screen.dart
│   ├── widgets/                  # 通用组件
│   │   ├── task_card.dart
│   │   ├── pomodoro_timer.dart
│   │   └── habit_heatmap.dart
│   └── services/                 # 业务服务
│       ├── notification_service.dart
│       └── background_sync.dart
├── android/                      # Android配置
├── ios/                          # iOS配置
├── test/                         # 测试
└── pubspec.yaml                  # 依赖
```

### 2.3 核心功能实现

#### 2.3.1 同步引擎

```dart
// lib/core/sync_engine.dart

class SyncEngine {
  final ApiClient _api;
  final LocalDatabase _db;
  final ConflictResolver _resolver;
  
  StreamController<SyncStatus> _statusController = StreamController.broadcast();
  Stream<SyncStatus> get statusStream => _statusController.stream;
  
  // 推送本地变更到服务器
  Future<void> push() async {
    _statusController.add(SyncStatus.pushing);
    
    // 获取待同步记录
    final pending = await _db.getPendingChanges();
    
    for (var change in pending) {
      try {
        switch (change.operation) {
          case 'create':
            await _api.create(change.table, change.data);
            break;
          case 'update':
            await _api.update(change.table, change.id, change.data);
            break;
          case 'delete':
            await _api.delete(change.table, change.id);
            break;
        }
        
        // 标记为已同步
        await _db.markAsSynced(change.id);
      } catch (e) {
        // 冲突处理
        if (e is ConflictException) {
          await _handleConflict(change, e.serverVersion);
        }
      }
    }
    
    _statusController.add(SyncStatus.idle);
  }
  
  // 从服务器拉取变更
  Future<void> pull() async {
    _statusController.add(SyncStatus.pulling);
    
    final lastSyncAt = await _db.getLastSyncTime();
    final changes = await _api.getChanges(since: lastSyncAt);
    
    for (var change in changes) {
      // 检查本地是否有冲突
      final localVersion = await _db.getById(change.table, change.id);
      
      if (localVersion != null && localVersion.modifiedAt > change.serverModifiedAt) {
        // 有冲突，需要解决
        final resolved = await _resolver.resolve(localVersion, change);
        await _db.save(change.table, resolved);
      } else {
        // 无冲突，直接应用
        await _db.save(change.table, change.data);
      }
    }
    
    await _db.updateLastSyncTime(DateTime.now());
    _statusController.add(SyncStatus.idle);
  }
  
  // 双向同步
  Future<void> sync() async {
    await push();
    await pull();
  }
}
```

#### 2.3.2 本地数据库 (SQLite)

```dart
// lib/core/local_db.dart

class LocalDatabase {
  Database _db;
  
  Future<void> init() async {
    final path = await getDatabasesPath();
    _db = await openDatabase(
      join(path, 'local_command_center.db'),
      version: 1,
      onCreate: (db, version) async {
        // 创建表
        await db.execute('''
          CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT,
            priority INTEGER,
            due_time TEXT,
            created_at TEXT,
            updated_at TEXT,
            sync_status TEXT DEFAULT 'pending', -- pending/synced/conflict
            server_version INTEGER DEFAULT 0
          )
        ''');
        
        await db.execute('''
          CREATE TABLE sync_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT,
            record_id TEXT,
            operation TEXT, -- create/update/delete
            data TEXT,
            created_at TEXT
          )
        ''');
      },
    );
  }
  
  // 插入时记录变更
  Future<void> insertTask(Task task) async {
    await _db.insert('tasks', task.toMap());
    
    await _db.insert('sync_changes', {
      'table_name': 'tasks',
      'record_id': task.id,
      'operation': 'create',
      'data': jsonEncode(task.toMap()),
      'created_at': DateTime.now().toIso8601String(),
    });
  }
}
```

#### 2.3.3 主界面设计

```dart
// lib/screens/home_screen.dart

class HomeScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedIndex = ref.watch(bottomNavProvider);
    
    return Scaffold(
      body: IndexedStack(
        index: selectedIndex,
        children: [
          TodayView(),      // 今日视图
          TaskListView(),   // 任务列表
          CalendarView(),   // 日历
          HabitsView(),     // 习惯追踪
          NotesView(),      // 笔记
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: selectedIndex,
        onTap: (index) => ref.read(bottomNavProvider.notifier).state = index,
        type: BottomNavigationBarType.fixed,
        items: [
          BottomNavigationBarItem(icon: Icon(Icons.today), label: '今日'),
          BottomNavigationBarItem(icon: Icon(Icons.check_circle), label: '任务'),
          BottomNavigationBarItem(icon: Icon(Icons.calendar_today), label: '日历'),
          BottomNavigationBarItem(icon: Icon(Icons.local_fire_department), label: '习惯'),
          BottomNavigationBarItem(icon: Icon(Icons.note), label: '笔记'),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showQuickAdd(context),
        child: Icon(Icons.add),
      ),
    );
  }
}
```

### 2.4 推送通知

```dart
// lib/services/notification_service.dart

class NotificationService {
  final FlutterLocalNotificationsPlugin _notifications = FlutterLocalNotificationsPlugin();
  
  Future<void> init() async {
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings();
    
    await _notifications.initialize(
      InitializationSettings(android: androidSettings, iOS: iosSettings),
      onDidReceiveNotificationResponse: _onNotificationTap,
    );
  }
  
  Future<void> scheduleTaskReminder(Task task) async {
    await _notifications.zonedSchedule(
      task.id.hashCode,
      '任务提醒',
      task.name,
      tz.TZDateTime.from(task.dueTime, tz.local),
      NotificationDetails(
        android: AndroidNotificationDetails(
          'task_reminders',
          '任务提醒',
          importance: Importance.high,
        ),
        iOS: DarwinNotificationDetails(),
      ),
      androidAllowWhileIdle: true,
      uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime,
    );
  }
  
  Future<void> showPomodoroComplete() async {
    await _notifications.show(
      0,
      '番茄钟完成',
      '休息一下吧！',
      NotificationDetails(
        android: AndroidNotificationDetails(
          'pomodoro',
          '番茄钟',
        ),
      ),
    );
  }
}
```

---

## 三、数据同步协议

### 3.1 同步策略

**选择: 操作转换 (Operational Transformation) + CRDT 简化版**

```
同步流程:
1. 本地操作记录为变更日志
2. 推送时上传变更日志
3. 服务器应用变更并返回新状态
4. 拉取时获取服务器变更
5. 冲突时：时间戳优先 + 字段级合并
```

### 3.2 变更日志格式

```typescript
interface ChangeLog {
  id: string;           // 变更ID
  table: string;        // 表名
  recordId: string;     // 记录ID
  operation: 'create' | 'update' | 'delete';
  data?: object;        // 新数据
  previousData?: object; // 旧数据（用于冲突检测）
  timestamp: number;    // 时间戳
  deviceId: string;     // 设备标识
  checksum: string;     // 数据校验
}

interface UpdateChange extends ChangeLog {
  operation: 'update';
  changedFields: string[];  // 变更的字段
}
```

### 3.3 冲突解决

```python
# services/sync/conflict_resolver.py

class ConflictResolver:
    def resolve(self, local: dict, server: dict, base: dict = None) -> dict:
        """
        三路合并解决冲突
        local: 本地版本
        server: 服务器版本
        base: 共同祖先版本（可选）
        """
        if base is None:
            # 无共同祖先，使用时间戳优先
            return server if server['updated_at'] > local['updated_at'] else local
        
        result = {}
        all_fields = set(local.keys()) | set(server.keys())
        
        for field in all_fields:
            local_val = local.get(field)
            server_val = server.get(field)
            base_val = base.get(field)
            
            if local_val == server_val:
                result[field] = local_val
            elif local_val == base_val:
                # 本地未变，服务器变了
                result[field] = server_val
            elif server_val == base_val:
                # 服务器未变，本地变了
                result[field] = local_val
            else:
                # 双方都变了，需要字段级合并
                result[field] = self._merge_field(field, local_val, server_val)
        
        return result
    
    def _merge_field(self, field: str, local_val, server_val):
        """字段级合并策略"""
        # 列表类型：合并去重
        if isinstance(local_val, list) and isinstance(server_val, list):
            return list(set(local_val + server_val))
        
        # 数值类型：取最大（如进度、计数）
        if field in ['progress', 'pomodoro_count']:
            return max(local_val, server_val)
        
        # 默认：时间戳优先
        return server_val
```

### 3.4 离线队列

```dart
// lib/core/offline_queue.dart

class OfflineQueue {
  final LocalDatabase _db;
  final Connectivity _connectivity;
  
  StreamSubscription? _connectionSubscription;
  
  void startListening() {
    _connectionSubscription = _connectivity.onConnectivityChanged.listen((result) {
      if (result != ConnectivityResult.none) {
        // 恢复网络，开始同步
        _processQueue();
      }
    });
  }
  
  Future<void> enqueue(Operation operation) async {
    // 保存到本地队列
    await _db.insertQueue(operation);
    
    // 检查网络
    final hasNetwork = await _checkNetwork();
    if (hasNetwork) {
      await _processQueue();
    }
  }
  
  Future<void> _processQueue() async {
    final pending = await _db.getPendingOperations();
    
    for (var op in pending) {
      try {
        await _executeOperation(op);
        await _db.removeFromQueue(op.id);
      } catch (e) {
        // 网络错误，停止处理
        if (e is NetworkException) break;
        // 其他错误，记录并继续
        await _db.markQueueError(op.id, e.toString());
      }
    }
  }
}
```

---

## 四、PWA支持

### 4.1 Service Worker

```javascript
// static/sw.js

const CACHE_NAME = 'lcc-v1.0.0';
const urlsToCache = [
  '/',
  '/static/index.html',
  '/static/style.css',
  '/static/app.js',
  '/static/icons/icon-192.png',
];

// 安装时缓存
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  );
});

// 拦截请求
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // 缓存命中直接返回
        if (response) {
          return response;
        }
        
        // 网络请求并缓存
        return fetch(event.request).then((response) => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
          
          return response;
        });
      })
  );
});

// 推送通知
self.addEventListener('push', (event) => {
  const data = event.data.json();
  
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/icons/icon-192.png',
      data: data.url,
    })
  );
});
```

### 4.2 Manifest

```json
{
  "name": "LocalCommandCenter",
  "short_name": "LCC",
  "description": "本地智能任务管理中心",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#16213e",
  "icons": [
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

---

## 五、桌面端打包

### 5.1 方案选择

| 方案 | 工具 | 输出 |
|------|------|------|
| Windows | Inno Setup / WiX | .exe, .msi |
| macOS | electron-builder / create-dmg | .dmg, .app |
| Linux | electron-builder / fpm | .deb, .rpm, AppImage |

### 5.2 Electron封装

```javascript
// electron/main.js

const { app, BrowserWindow, Tray, Menu } = require('electron');
const path = require('path');

let mainWindow;
let tray;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'assets/icon.png'),
  });

  // 加载本地服务或远程
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:8900');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产环境使用打包的服务
    const { startServer } = require('./server');
    startServer().then((port) => {
      mainWindow.loadURL(`http://localhost:${port}`);
    });
  }

  // 最小化到托盘
  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow.hide();
  });
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'assets/tray-icon.png'));
  
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示', click: () => mainWindow.show() },
    { label: '新建任务', click: () => {
      mainWindow.show();
      mainWindow.webContents.send('shortcut-new-task');
    }},
    { type: 'separator' },
    { label: '退出', click: () => app.quit() }
  ]);
  
  tray.setContextMenu(contextMenu);
  tray.setToolTip('LocalCommandCenter');
}

app.whenReady().then(() => {
  createWindow();
  createTray();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
```

---

## 六、安全与加密

### 6.1 端到端加密

```python
# services/crypto/e2e_encryption.py

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class E2EEncryption:
    """端到端加密服务"""
    
    def __init__(self, master_password: str, salt: bytes = None):
        self.salt = salt or os.urandom(16)
        self.key = self._derive_key(master_password, self.salt)
        self.fernet = Fernet(self.key)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """加密数据"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, token: str) -> str:
        """解密数据"""
        return self.fernet.decrypt(token.encode()).decode()
    
    def encrypt_object(self, obj: dict) -> dict:
        """加密对象中的敏感字段"""
        sensitive_fields = ['title', 'description', 'content']
        encrypted = {}
        
        for key, value in obj.items():
            if key in sensitive_fields and isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value
        
        return encrypted
```

---

## 七、实现时间表

| 周次 | 任务 | 输出 |
|------|------|------|
| W1 | Flutter项目搭建<br>基础架构 | 项目框架<br>导航结构 |
| W2 | API客户端<br>本地数据库 | 数据层<br>模型定义 |
| W3 | 任务模块<br>番茄钟 | 任务功能可用 |
| W4 | 日历模块<br>习惯模块 | 日历<br>习惯功能 |
| W5 | 笔记模块<br<br>设置 | 笔记功能 |
| W6 | 同步引擎<br>离线支持 | 同步功能 |
| W7 | PWA支持<br>推送通知 | Web应用 |
| W8 | 桌面打包<br>安装程序 | 桌面端 |
| W9 | 测试优化<br>Bug修复 | 稳定版本 |
| W10 | 文档完善 | 用户手册 |
| W11 | 内测反馈 | 迭代优化 |
| W12 | v1.0.0发布 | 正式版 |

---

*本文档将持续更新*
