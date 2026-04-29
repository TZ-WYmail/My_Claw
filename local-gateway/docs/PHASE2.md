# Phase 2: 智能增强 - 详细实现文档

> 目标: 引入AI能力，实现智能规划，提升自动化水平
> 预计工期: 8-10周
> 版本目标: v0.8.0
> 依赖: Phase 1完成

---

## 一、本阶段目标

### 1.1 核心交付物

| 类别 | 交付物 | 验收标准 |
|------|--------|----------|
| 功能 | AI任务拆解 | 自然语言创建任务自动拆解为子任务 |
| 功能 | 智能时间规划 | AI根据任务类型、历史数据推荐时间 |
| 功能 | 语音输入 | 支持语音创建任务和指令 |
| 功能 | 习惯养成系统 | 完整的习惯追踪、统计、提醒 |
| 功能 | 笔记基础 | Markdown编辑器、笔记关联任务 |
| 功能 | 智能建议 | 基于数据的主动建议 |
| 性能 | AI响应优化 | 平均响应<3秒，支持流式输出 |

### 1.2 用户价值

完成Phase 2后，用户可以：
- 用自然语言快速创建复杂任务（AI自动拆解）
- 语音快速记录想法和任务
- 建立习惯追踪，培养良好作息
- 在笔记中记录想法并关联任务
- 获得AI的个性化效率建议

---

## 二、模块详细设计

### 2.1 AI任务拆解与规划

#### 2.1.1 架构设计

```
用户输入自然语言
    ↓
意图识别 (Intent Classification)
    ↓
实体提取 (NER) → 任务名称、时间、优先级
    ↓
任务拆解 (Task Decomposition)
    ↓
时间估算 (Time Estimation)
    ↓
冲突检测 (Conflict Detection)
    ↓
生成执行计划
```

#### 2.1.2 Prompt设计

```python
# services/ai/prompts/task_planning.py

TASK_DECOMPOSITION_PROMPT = """你是一个任务规划专家。请将用户的任务描述拆解为可执行的子任务。

用户输入: {user_input}
当前时间: {current_time}

请按以下JSON格式输出:
{
    "task_name": "主任务名称",
    "priority": "high/medium/low",
    "estimated_hours": 总预估小时数,
    "subtasks": [
        {
            "title": "子任务1",
            "estimated_minutes": 30,
            "order": 1,
            "dependencies": []  // 依赖的其他子任务索引
        }
    ],
    "suggested_schedule": [
        {
            "day": "2026-04-27",
            "time": "09:00",
            "subtask_indices": [0, 1]
        }
    ],
    "reasoning": "拆解思路说明"
}

规则:
1. 子任务应该具体、可执行、有明确的完成标准
2. 预估时间要合理，不要太乐观
3. 考虑任务间的依赖关系
4. 如果任务可以并行，标注出来
5. 建议的执行时间要考虑用户的作息规律
"""
```

#### 2.1.3 API设计

```python
# AI规划相关
POST /api/ai/plan
Body: {
    "input": "准备下周的产品发布会",
    "context": {
        "deadline": "2026-05-01",
        "available_hours_per_day": 4
    }
}
Response: {
    "plan": {
        "task_name": "产品发布会准备",
        "subtasks": [...],
        "schedule": [...]
    },
    "preview_id": "preview_xxx"  // 用于确认后创建
}

# 确认创建
POST /api/ai/plan/{preview_id}/confirm
Body: {
    "modifications": {  // 可选的修改
        "subtasks_to_remove": [2],
        "time_adjustments": {...}
    }
}
Response: {
    "created_tasks": [{"task_id": "...", "title": "..."}],
    "calendar_events": [...]
}
```

#### 2.1.4 本地缓存与历史学习

```python
# services/ai/learning.py

class UserLearningModel:
    """学习用户的工作模式"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db = get_db()
    
    async def record_task_completion(
        self, 
        task_type: str,
        estimated_minutes: int,
        actual_minutes: int
    ):
        """记录任务完成时间，用于优化预估"""
        await self.db.execute("""
            INSERT INTO task_time_estimates 
            (user_id, task_type, estimated, actual, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (self.user_id, task_type, estimated, actual, now()))
    
    async def get_adjustment_factor(self, task_type: str) -> float:
        """获取该任务类型的时间调整系数"""
        # 查询历史数据，计算实际/预估的比值
        # 例如用户总是低估30%，返回1.3
        rows = await self.db.fetchall("""
            SELECT actual * 1.0 / estimated as ratio
            FROM task_time_estimates
            WHERE user_id = ? AND task_type = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (self.user_id, task_type))
        
        if not rows:
            return 1.0
        return sum(r['ratio'] for r in rows) / len(rows)
```

---

### 2.2 语音输入集成

#### 2.2.1 技术选型

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| Web Speech API | 免费、浏览器原生 | 精度一般、浏览器差异 | 首选 |
| Whisper (本地) | 精度高、隐私好 | 需要GPU资源 | 备选 |
| 讯飞/百度API | 中文好、有免费额度 | 网络依赖 | 云端增强 |

#### 2.2.2 实现架构

```
浏览器录音 (Web Audio API)
    ↓
实时转文字 (Web Speech API)
    ↓
意图识别 (本地NLP / AI服务)
    ↓
生成任务/指令
```

#### 2.2.3 前端实现

```javascript
// static/components/voice-input.js
class VoiceInput {
    constructor() {
        this.recognition = null;
        this.isRecording = false;
        this.transcript = '';
    }
    
    init() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.lang = 'zh-CN';
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            
            this.recognition.onresult = (event) => {
                let interim = '';
                let final = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        final += transcript;
                    } else {
                        interim += transcript;
                    }
                }
                
                this.onResult(final, interim);
            };
        }
    }
    
    start() {
        if (this.recognition) {
            this.recognition.start();
            this.isRecording = true;
        }
    }
    
    stop() {
        if (this.recognition) {
            this.recognition.stop();
            this.isRecording = false;
            return this.processCommand(this.transcript);
        }
    }
    
    async processCommand(transcript) {
        // 发送到后端进行意图识别
        const response = await fetch('/api/ai/voice-command', {
            method: 'POST',
            body: JSON.stringify({ text: transcript })
        });
        return response.json();
    }
}
```

#### 2.2.4 语音指令类型

| 指令类型 | 示例 | 动作 |
|----------|------|------|
| 创建任务 | "提醒我明天下午三点开会" | 创建任务+设置提醒 |
| 查询 | "我本周有什么任务" | 查询任务列表 |
| 控制 | "开始番茄钟" | 启动25分钟计时 |
| 笔记 | "记一下：想法..." | 创建快速笔记 |
| 搜索 | "找一下关于AI的论文" | 搜索文件 |

---

### 2.3 习惯养成系统

#### 2.3.1 数据库Schema

```sql
-- 习惯定义表
CREATE TABLE habits (
    habit_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT, -- emoji或图标名
    color TEXT DEFAULT '#3498db',
    
    -- 频率设置
    frequency_type TEXT NOT NULL, -- daily/weekly/monthly/custom
    frequency_config TEXT, -- JSON: {"days": [1,3,5]} 周一周三周五
    target_count INTEGER DEFAULT 1, -- 每日/每周目标次数
    
    -- 提醒设置
    reminder_time TEXT, -- "09:00"
    reminder_days TEXT, -- JSON: [1,2,3,4,5] 工作日
    
    -- 关联
    linked_task_id TEXT, -- 可选关联任务
    
    created_at TEXT DEFAULT (datetime('now')),
    archived_at TEXT, -- 归档时间，NULL表示活跃
    
    FOREIGN KEY (linked_task_id) REFERENCES tasks(task_id)
);

-- 习惯打卡记录
CREATE TABLE habit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id TEXT NOT NULL,
    check_in_date TEXT NOT NULL, -- YYYY-MM-DD
    check_in_time TEXT, -- HH:MM:SS
    count INTEGER DEFAULT 1, -- 本次打卡次数（支持多次）
    note TEXT,
    mood INTEGER, -- 1-5心情评分
    
    FOREIGN KEY (habit_id) REFERENCES habits(habit_id) ON DELETE CASCADE,
    UNIQUE(habit_id, check_in_date)
);

-- 习惯统计（物化视图或冗余表）
CREATE TABLE habit_stats (
    habit_id TEXT PRIMARY KEY,
    current_streak INTEGER DEFAULT 0, -- 当前连续天数
    longest_streak INTEGER DEFAULT 0, -- 最长连续天数
    total_checkins INTEGER DEFAULT 0,
    completion_rate REAL DEFAULT 0, -- 完成率
    last_checkin_date TEXT,
    
    FOREIGN KEY (habit_id) REFERENCES habits(habit_id) ON DELETE CASCADE
);
```

#### 2.3.2 核心算法

**连续天数计算**:
```python
def calculate_streak(checkin_dates: List[str]) -> int:
    """计算连续打卡天数"""
    if not checkin_dates:
        return 0
    
    dates = sorted([datetime.strptime(d, '%Y-%m-%d').date() 
                    for d in checkin_dates], reverse=True)
    
    streak = 1
    today = date.today()
    
    # 如果今天没打卡，从昨天开始算
    if dates[0] != today and dates[0] != today - timedelta(days=1):
        return 0
    
    for i in range(1, len(dates)):
        if dates[i] == dates[i-1] - timedelta(days=1):
            streak += 1
        else:
            break
    
    return streak
```

**完成率计算**:
```python
def calculate_completion_rate(habit_id: str, days: int = 30) -> float:
    """计算最近N天的完成率"""
    # 查询习惯频率设置
    habit = get_habit(habit_id)
    
    # 计算应该完成的次数
    expected = calculate_expected_count(habit, days)
    
    # 查询实际完成次数
    actual = query_actual_count(habit_id, days)
    
    return actual / expected if expected > 0 else 0
```

#### 2.3.3 API设计

```python
# 习惯CRUD
POST   /api/habits
GET    /api/habits                    # 支持筛选: active/archived/all
GET    /api/habits/{habit_id}
PUT    /api/habits/{habit_id}
DELETE /api/habits/{habit_id}

# 打卡
POST   /api/habits/{habit_id}/checkin
Body: { "count": 1, "note": "", "mood": 5 }

# 取消打卡
DELETE /api/habits/{habit_id}/checkin/{date}

# 统计
GET    /api/habits/{habit_id}/stats
GET    /api/habits/{habit_id}/calendar?month=2026-04  # 月度日历视图

# 批量操作
POST   /api/habits/checkin-batch  # 批量打卡（补卡）
```

#### 2.3.4 可视化组件

**习惯热力图**:
```javascript
// static/components/habit-heatmap.js
class HabitHeatmap {
    constructor(container, data) {
        this.container = container;
        this.data = data; // { '2026-04-01': 2, '2026-04-02': 0, ... }
    }
    
    render() {
        // GitHub风格的贡献图
        // 52周 x 7天网格
        // 颜色深浅表示完成强度
    }
}
```

---

### 2.4 笔记系统

#### 2.4.1 数据模型

```sql
-- 笔记表
CREATE TABLE notes (
    note_id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT NOT NULL, -- Markdown格式
    
    -- 类型
    note_type TEXT DEFAULT 'note', -- note/task_note/daily_journal
    
    -- 关联
    linked_task_id TEXT,
    linked_project_id TEXT,
    
    -- 组织
    folder_id TEXT,
    tags TEXT, -- JSON数组
    
    -- 元数据
    is_pinned BOOLEAN DEFAULT 0,
    is_archived BOOLEAN DEFAULT 0,
    
    -- 时间戳
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    
    FOREIGN KEY (linked_task_id) REFERENCES tasks(task_id)
);

-- 笔记文件夹
CREATE TABLE note_folders (
    folder_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT, -- 支持嵌套
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 每日日志（自动创建）
CREATE TABLE daily_journals (
    date TEXT PRIMARY KEY, -- YYYY-MM-DD
    content TEXT,
    mood INTEGER,
    energy_level INTEGER,
    highlights TEXT, -- JSON: 今日亮点
    improvements TEXT, -- JSON: 待改进
    created_at TEXT,
    updated_at TEXT
);
```

#### 2.4.2 Markdown编辑器

选择: **Toast UI Editor** 或 **Milkdown**
- 轻量、开源、支持Vue/React/Vanilla
- 实时预览、工具栏、插件系统

```javascript
// static/components/markdown-editor.js
class MarkdownEditor {
    constructor(element, options = {}) {
        this.element = element;
        this.editor = new toastui.Editor({
            el: element,
            initialEditType: 'markdown',
            previewStyle: 'vertical',
            height: '500px',
            initialValue: options.content || '',
            placeholder: '开始记录...',
            toolbarItems: [
                ['heading', 'bold', 'italic', 'strike'],
                ['hr', 'quote'],
                ['ul', 'ol', 'task'],
                ['table', 'link'],
                ['code', 'codeblock'],
            ],
            hooks: {
                addImageBlobHook: this.handleImageUpload.bind(this)
            }
        });
    }
    
    async handleImageUpload(blob, callback) {
        // 上传到本地存储
        const formData = new FormData();
        formData.append('image', blob);
        
        const response = await fetch('/api/notes/upload-image', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        callback(result.url, 'image');
    }
    
    getContent() {
        return this.editor.getMarkdown();
    }
    
    setContent(content) {
        this.editor.setMarkdown(content);
    }
}
```

#### 2.4.3 API设计

```python
# 笔记CRUD
POST   /api/notes
GET    /api/notes                    # 列表，支持搜索/筛选
GET    /api/notes/{note_id}
PUT    /api/notes/{note_id}
DELETE /api/notes/{note_id}

# 文件夹
POST   /api/notes/folders
GET    /api/notes/folders
PUT    /api/notes/folders/{folder_id}
DELETE /api/notes/folders/{folder_id}

# 快速笔记
POST   /api/notes/quick              # 快速创建，最小化参数

# 关联任务
POST   /api/notes/{note_id}/link-task/{task_id}

# 图片上传
POST   /api/notes/upload-image

# 每日日志
GET    /api/journals/today
PUT    /api/journals/{date}
GET    /api/journals?month=2026-04   # 获取月度日志
```

---

### 2.5 智能建议系统

#### 2.5.1 建议类型

| 类型 | 触发条件 | 建议内容 |
|------|----------|----------|
| 每日计划 | 每天早上 | 基于今日截止和优先级推荐重点 |
| 最佳下一步 | 完成一个任务后 | 推荐下一个该做的任务 |
| 遗漏提醒 | 检测到可能遗漏 | "你有3个已过期的任务" |
| 习惯提醒 | 习惯未打卡 | "今天还没喝水打卡" |
| 效率建议 | 分析历史数据 | "你上午效率更高，建议把困难任务放在上午" |
| 专注建议 | 检测到分心模式 | "你已经连续工作2小时，建议休息" |

#### 2.5.2 建议生成引擎

```python
# services/ai/suggestion_engine.py

class SuggestionEngine:
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    async def generate_daily_plan(self) -> Suggestion:
        """生成每日计划建议"""
        # 1. 获取今日截止任务
        # 2. 获取高优先级未完成任务
        # 3. 获取习惯打卡情况
        # 4. 分析历史完成模式
        # 5. 生成建议
        
        tasks = await self.get_today_tasks()
        habits = await self.get_pending_habits()
        
        prompt = f"""
基于以下信息生成今日计划建议:

今日截止任务: {json.dumps(tasks)}
待完成习惯: {json.dumps(habits)}
历史效率高峰: {await self.get_peak_hours()}

请给出:
1. 今日最重要的3件事
2. 建议的时间安排
3. 任何需要提醒的风险
"""
        
        response = await self.llm.complete(prompt)
        return Suggestion(
            type="daily_plan",
            content=response,
            priority="high",
            actions=[...]
        )
    
    async def detect_anomalies(self) -> List[Suggestion]:
        """检测异常并生成提醒"""
        suggestions = []
        
        # 检测过期任务
        overdue = await self.get_overdue_tasks()
        if overdue:
            suggestions.append(Suggestion(
                type="overdue_reminder",
                content=f"你有{len(overdue)}个已过期的任务",
                actions=[
                    Action(label="查看", url="/tasks?filter=overdue"),
                    Action(label="全部延期到今天", action="postpone_all")
                ]
            ))
        
        # 检测习惯中断
        broken_habits = await self.get_broken_habits()
        for habit in broken_habits:
            suggestions.append(Suggestion(
                type="habit_reminder",
                content=f"习惯'{habit.name}'已经{habit.days_missed}天没打卡了",
                priority="medium"
            ))
        
        return suggestions
```

#### 2.5.3 主动推送

```python
# services/notification/scheduler.py

class SuggestionScheduler:
    """定时生成和推送建议"""
    
    def setup(self):
        # 每天早上8点生成每日计划
        scheduler.add_job(
            self.push_daily_plan,
            CronTrigger(hour=8, minute=0)
        )
        
        # 每小时检查异常
        scheduler.add_job(
            self.check_anomalies,
            IntervalTrigger(hours=1)
        )
        
        # 工作日下午3点效率提醒
        scheduler.add_job(
            self.push_efficiency_tip,
            CronTrigger(day_of_week='mon-fri', hour=15, minute=0)
        )
    
    async def push_daily_plan(self):
        for user in await get_active_users():
            engine = SuggestionEngine(user.id)
            suggestion = await engine.generate_daily_plan()
            await self.notify(user, suggestion)
```

---

## 三、AI基础设施

### 3.1 提示词管理

```
services/ai/prompts/
├── __init__.py
├── base.py                    # 提示词基类
├── task_planning.py          # 任务规划
├── voice_command.py          # 语音指令解析
├── suggestion.py             # 建议生成
├── note_assist.py            # 笔记辅助
└── templates/                # Jinja2模板
    ├── task_decomposition.j2
    ├── daily_plan.j2
    └── ...
```

### 3.2 模型配置

```python
# config.py AI配置扩展

AI_CONFIG = {
    # 功能开关
    "features": {
        "task_decomposition": True,
        "voice_input": True,
        "smart_suggestions": True,
    },
    
    # 模型路由 - 不同功能使用不同模型
    "models": {
        "task_planning": "glm-4-flash",      # 快速、便宜
        "voice_recognition": "whisper-1",     # 语音识别
        "suggestions": "glm-4-flash",
        "chat": "glm-4-air",                  # 平衡
    },
    
    # 性能优化
    "caching": {
        "enabled": True,
        "ttl": 3600,  # 缓存1小时
    },
    "streaming": True,  # 流式输出
}
```

### 3.3 缓存策略

```python
# services/ai/cache.py
import hashlib
from functools import wraps

def ai_cache(ttl=3600):
    """AI响应缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = f"ai:{func.__name__}:{hashlib.md5(str(args).encode()).hexdigest()}"
            
            # 尝试从缓存获取
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # 调用原始函数
            result = await func(*args, **kwargs)
            
            # 缓存结果
            await redis.setex(cache_key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

# 使用
class AIService:
    @ai_cache(ttl=1800)
    async def decompose_task(self, description: str) -> dict:
        # 耗时操作
        ...
```

---

## 四、实现时间表

### 4.1 任务分解

| 周次 | 任务 | 输出 |
|------|------|------|
| W1 | AI服务架构<br>Prompt管理系统 | AI服务框架<br>Prompt模板 |
| W2 | 任务拆解API<br>时间估算学习 | 智能规划API<br>学习模型 |
| W3 | 语音输入前端<br>语音指令解析 | VoiceInput组件<br>命令解析API |
| W4 | 习惯系统后端<br>统计计算 | Habit API<br>热力图数据 |
| W5 | 习惯前端组件<br>笔记后端 | Habit UI<br>Note API |
| W6 | Markdown编辑器<br>笔记前端 | 编辑器组件<br>笔记界面 |
| W7 | 智能建议引擎<br>定时任务 | Suggestion API<br>Scheduler |
| W8 | 建议UI<br>集成测试 | 建议卡片<br>测试报告 |
| W9 | 性能优化<br>缓存调优 | 优化报告 |
| W10 | Bug修复<br>文档<br>v0.8.0发布 | 发布版本 |

---

## 五、附录

### 5.1 数据库Migration v1.2

```sql
-- Phase 2数据库变更
-- 习惯相关表
CREATE TABLE habits (...);
CREATE TABLE habit_logs (...);
CREATE TABLE habit_stats (...);

-- 笔记相关表
CREATE TABLE notes (...);
CREATE TABLE note_folders (...);
CREATE TABLE daily_journals (...);

-- AI学习数据
CREATE TABLE task_time_estimates (...);
CREATE TABLE user_patterns (...);
```

### 5.2 配置示例

```yaml
# config/ai.yaml
ai:
  provider: zhipu
  api_key: ${ZHIPU_API_KEY}
  
  models:
    default: glm-4-flash
    planning: glm-4-flash
    chat: glm-4-air
  
  features:
    task_decomposition:
      enabled: true
      max_subtasks: 10
      
    voice:
      enabled: true
      engine: web_speech  # web_speech / whisper / xunfei
      
    suggestions:
      enabled: true
      daily_plan_time: "08:00"
```

---

*本文档将在开发过程中持续更新*
