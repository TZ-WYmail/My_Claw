# Phase 5: 专业深化 - 详细实现文档

> 目标: 企业级功能，深度智能化
> 预计工期: 12-16周
> 版本目标: v2.0.0 (专业版)
> 依赖: Phase 1-4完成

---

## 一、本阶段目标

### 1.1 核心交付物

| 类别 | 交付物 | 验收标准 |
|------|--------|----------|
| 智能 | 知识图谱 | 实体关系可视化，智能关联 |
| 分析 | 深度数据分析 | 多维度报表，趋势预测 |
| 扩展 | 插件系统 | 完整的插件开发SDK，应用市场 |
| 协作 | 团队功能 | 多人协作，权限管理 |
| 性能 | 优化重构 | 支持10万+任务，秒级响应 |

### 1.2 用户价值

完成Phase 5后，用户可以：
- 构建个人知识图谱，发现知识间的隐藏关联
- 获得深度工作效率分析和改进建议
- 安装社区插件扩展功能
- 与团队成员协作管理项目和任务
- 享受企业级的性能和安全保障

---

## 二、知识图谱系统

### 2.1 架构设计

```
知识抽取层
    ├── 实体识别 (NER) - 人名、地点、项目、技术
    ├── 关系抽取 - 从文本中提取实体关系
    └── 知识融合 - 实体消歧，合并相似实体

知识存储层
    ├── 图数据库 (Neo4j) - 存储实体和关系
    └── 向量数据库 (Milvus) - 存储语义向量

知识应用层
    ├── 知识可视化 - 交互式图谱展示
    ├── 知识问答 - 基于图谱的问答
    └── 智能推荐 - 相关内容推荐
```

### 2.2 数据模型

```cypher
// Neo4j图模型

// 实体类型
(:Entity {
  id: string,
  type: 'person' | 'project' | 'technology' | 'concept' | 'document',
  name: string,
  aliases: [string],
  properties: map,
  embedding: vector
})

// 关系类型
(:Entity)-[:RELATES_TO {
  type: 'works_on' | 'uses' | 'mentions' | 'similar_to',
  weight: float,
  source: string
}]->(:Entity)

// 与本地数据关联
(:Task)-[:ABOUT]->(:Entity)
(:Note)-[:MENTIONS]->(:Entity)
(:File)-[:CONTAINS]->(:Entity)
```

### 2.3 知识抽取

```python
# services/knowledge/extraction.py

from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification

class KnowledgeExtractor:
    def __init__(self):
        # 中文NER模型
        self.ner_model = pipeline(
            "ner",
            model="shibing624/macbert4cner-base-chinese",
            tokenizer="shibing624/macbert4cner-base-chinese",
            aggregation_strategy="simple"
        )
        
        # 关系抽取模型
        self.relation_model = pipeline(
            "text2text-generation",
            model="chensemantic/SS-IE-base"
        )
    
    async def extract_from_text(self, text: str, source_id: str) -> ExtractionResult:
        """从文本中抽取知识"""
        # 1. 实体识别
        entities = self.ner_model(text)
        
        # 2. 关系抽取
        relations = []
        for i, ent1 in enumerate(entities):
            for ent2 in entities[i+1:]:
                relation = self._extract_relation(text, ent1, ent2)
                if relation:
                    relations.append(relation)
        
        # 3. 生成向量嵌入
        embeddings = await self._generate_embeddings(entities)
        
        return ExtractionResult(
            entities=[Entity(
                id=generate_id(),
                name=e['word'],
                type=self._normalize_entity_type(e['entity_group']),
                embedding=embeddings.get(e['word'])
            ) for e in entities],
            relations=relations,
            source_id=source_id
        )
    
    async def extract_from_task(self, task: Task) -> ExtractionResult:
        """从任务中抽取知识"""
        text = f"{task.name} {task.description or ''}"
        result = await self.extract_from_text(text, f"task:{task.task_id}")
        
        # 关联任务到实体
        for entity in result.entities:
            entity.source_tasks.append(task.task_id)
        
        return result
    
    async def extract_from_note(self, note: Note) -> ExtractionResult:
        """从笔记中抽取知识"""
        # 去除Markdown标记
        text = markdown_to_text(note.content)
        return await self.extract_from_text(text, f"note:{note.note_id}")
```

### 2.4 知识存储

```python
# services/knowledge/graph_store.py

from neo4j import GraphDatabase

class KnowledgeGraphStore:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    async def merge_entity(self, entity: Entity):
        """合并实体（存在则更新，不存在则创建）"""
        with self.driver.session() as session:
            session.run("""
                MERGE (e:Entity {id: $id})
                ON CREATE SET 
                    e.name = $name,
                    e.type = $type,
                    e.created_at = datetime(),
                    e.aliases = $aliases
                ON MATCH SET
                    e.name = $name,
                    e.aliases = coalesce(e.aliases, []) + $new_aliases,
                    e.updated_at = datetime()
                SET e.embedding = $embedding
            """, {
                'id': entity.id,
                'name': entity.name,
                'type': entity.type,
                'aliases': entity.aliases,
                'new_aliases': [a for a in entity.aliases if a != entity.name],
                'embedding': entity.embedding
            })
    
    async def create_relationship(self, from_id: str, to_id: str, rel_type: str, properties: dict):
        """创建关系"""
        with self.driver.session() as session:
            session.run(f"""
                MATCH (a:Entity {{id: $from_id}})
                MATCH (b:Entity {{id: $to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $properties,
                    r.updated_at = datetime()
            """, {
                'from_id': from_id,
                'to_id': to_id,
                'properties': properties
            })
    
    async def find_related(self, entity_id: str, depth: int = 2) -> List[EntityPath]:
        """查找相关实体"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (start:Entity {id: $entity_id})-[:RELATES_TO*1..$depth]-(related)
                WHERE start <> related
                RETURN related, path,
                       reduce(weight = 1.0, r in relationships(path) | weight * r.weight) as total_weight
                ORDER BY total_weight DESC
                LIMIT 20
            """, {'entity_id': entity_id, 'depth': depth})
            
            return [self._parse_path(record) for record in result]
    
    async def semantic_search(self, query: str, embedding: List[float]) -> List[Entity]:
        """语义搜索"""
        with self.driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes('entity-embeddings', 10, $embedding)
                YIELD node, score
                RETURN node, score
            """, {'embedding': embedding})
            
            return [Entity.from_node(record['node'], score=record['score']) 
                    for record in result]
```

### 2.5 可视化

```typescript
// static/components/knowledge-graph.js
import * as d3 from 'd3';

class KnowledgeGraphVisualization {
    constructor(container, data) {
        this.container = container;
        this.data = data;
        this.width = container.clientWidth;
        this.height = container.clientHeight;
        this.simulation = null;
    }
    
    render() {
        const svg = d3.select(this.container)
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height);
        
        // 力导向图模拟
        this.simulation = d3.forceSimulation(this.data.nodes)
            .force('link', d3.forceLink(this.data.links).id(d => d.id))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2));
        
        // 绘制连线
        const link = svg.append('g')
            .selectAll('line')
            .data(this.data.links)
            .join('line')
            .attr('stroke-width', d => Math.sqrt(d.weight))
            .attr('stroke', '#999');
        
        // 绘制节点
        const node = svg.append('g')
            .selectAll('g')
            .data(this.data.nodes)
            .join('g')
            .call(this.drag());
        
        // 节点圆圈 - 按类型着色
        node.append('circle')
            .attr('r', d => d.importance * 5 + 5)
            .attr('fill', d => this.getColorByType(d.type));
        
        // 节点标签
        node.append('text')
            .text(d => d.name)
            .attr('x', 12)
            .attr('y', 4);
        
        // 交互
        node.on('click', (e, d) => this.onNodeClick(d));
        node.on('dblclick', (e, d) => this.expandNode(d));
        
        // 更新位置
        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });
    }
    
    getColorByType(type) {
        const colors = {
            'person': '#3498db',
            'project': '#e74c3c',
            'technology': '#2ecc71',
            'concept': '#f39c12',
            'document': '#9b59b6'
        };
        return colors[type] || '#95a5a6';
    }
    
    async expandNode(node) {
        // 加载更多关联节点
        const related = await api.getRelatedEntities(node.id);
        this.data.nodes.push(...related.nodes);
        this.data.links.push(...related.links);
        this.update();
    }
}
```

---

## 三、深度数据分析

### 3.1 数据仓库

```sql
-- 分析型数据库 (ClickHouse或SQLite扩展)

-- 任务事实表
CREATE TABLE fact_tasks (
    task_id String,
    date Date,
    user_id String,
    project_id String,
    tag_ids Array(String),
    
    -- 度量
    estimated_minutes Int32,
    actual_minutes Int32,
    pomodoro_count Int8,
    interruption_count Int8,
    
    -- 状态
    is_completed UInt8,
    is_overdue UInt8,
    
    -- 时间维度
    created_hour UInt8,
    completed_hour UInt8,
    day_of_week UInt8,
    week_of_year UInt8,
    
    -- 性能指标
    completion_speed Float32  -- 实际/预估
) ENGINE = MergeTree()
ORDER BY (date, user_id);

-- 时间追踪事实表
CREATE TABLE fact_time_tracking (
    date Date,
    user_id String,
    hour UInt8,
    
    -- 活动分类时间（分钟）
    time_deep_work Int32,
    time_meetings Int32,
    time_communication Int32,
    time_learning Int32,
    time_admin Int32,
    
    -- 效率指标
    focus_score Float32,
    energy_level UInt8
) ENGINE = MergeTree()
ORDER BY (date, user_id);
```

### 3.2 分析引擎

```python
# services/analytics/analytics_engine.py

import pandas as pd
import numpy as np
from scipy import stats

class AnalyticsEngine:
    def __init__(self, data_warehouse):
        self.dw = data_warehouse
    
    async def productivity_trend(self, user_id: str, period: str = '30d') -> TrendReport:
        """生产力趋势分析"""
        query = f"""
        SELECT 
            date,
            countIf(is_completed = 1) as completed_tasks,
            countIf(is_overdue = 1) as overdue_tasks,
            avg(completion_speed) as avg_speed,
            sum(pomodoro_count) as pomodoros
        FROM fact_tasks
        WHERE user_id = '{user_id}'
          AND date >= now() - INTERVAL {period}
        GROUP BY date
        ORDER BY date
        """
        
        df = await self.dw.query(query)
        
        # 计算趋势
        x = np.arange(len(df))
        slope_completed, _, r_value, _, _ = stats.linregress(x, df['completed_tasks'])
        
        # 检测异常
        mean = df['completed_tasks'].mean()
        std = df['completed_tasks'].std()
        anomalies = df[abs(df['completed_tasks'] - mean) > 2 * std]
        
        return TrendReport(
            period=period,
            trend='up' if slope_completed > 0 else 'down',
            correlation=r_value ** 2,
            anomalies=anomalies.to_dict('records'),
            recommendations=self._generate_recommendations(df)
        )
    
    async def peak_hours_analysis(self, user_id: str) -> PeakHoursReport:
        """高效时段分析"""
        query = f"""
        SELECT 
            completed_hour as hour,
            avg(completion_speed) as efficiency,
            count() as task_count
        FROM fact_tasks
        WHERE user_id = '{user_id}'
          AND is_completed = 1
        GROUP BY hour
        ORDER BY hour
        """
        
        df = await self.dw.query(query)
        
        # 找出效率最高的时段
        peak_hours = df.nlargest(3, 'efficiency')['hour'].tolist()
        
        # 统计显著性检验
        morning = df[df['hour'].between(8, 12)]['efficiency']
        afternoon = df[df['hour'].between(13, 18)]['efficiency']
        evening = df[df['hour'].between(19, 23)]['efficiency']
        
        _, p_value = stats.f_oneway(morning, afternoon, evening)
        
        return PeakHoursReport(
            peak_hours=peak_hours,
            low_hours=df.nsmallest(3, 'efficiency')['hour'].tolist(),
            statistical_significance=p_value < 0.05,
            recommendations=[
                f"建议在 {peak_hours[0]}:00-{peak_hours[0]+2}:00 安排重要任务"
            ]
        )
    
    async def procrastination_analysis(self, user_id: str) -> ProcrastinationReport:
        """拖延分析"""
        query = f"""
        SELECT 
            project_id,
            tag_ids,
            avg(dateDiff('hour', created_at, completed_at)) as avg_delay_hours,
            countIf(is_overdue = 1) as overdue_count,
            count() as total_count
        FROM fact_tasks
        WHERE user_id = '{user_id}'
          AND is_completed = 1
        GROUP BY project_id, tag_ids
        """
        
        df = await self.dw.query(query)
        
        # 识别拖延模式
        high_procrastination = df[df['avg_delay_hours'] > df['avg_delay_hours'].mean() + df['avg_delay_hours'].std()]
        
        return ProcrastinationReport(
            overall_delay_rate=df['overdue_count'].sum() / df['total_count'].sum(),
            high_risk_projects=high_procrastination['project_id'].tolist(),
            patterns=self._analyze_patterns(df)
        )
```

### 3.3 预测模型

```python
# services/analytics/prediction.py

from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import joblib

class WorkloadPredictor:
    """工作量预测"""
    
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100)
        self.is_trained = False
    
    def train(self, historical_data: pd.DataFrame):
        """训练预测模型"""
        features = [
            'day_of_week', 'week_of_year', 'pending_task_count',
            'avg_task_complexity', 'upcoming_deadlines', 'historical_completion_rate'
        ]
        
        X = historical_data[features]
        y = historical_data['actual_workload_hours']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # 保存模型
        joblib.dump(self.model, 'models/workload_predictor.pkl')
    
    def predict(self, features: dict) -> Prediction:
        """预测未来工作量"""
        if not self.is_trained:
            self.model = joblib.load('models/workload_predictor.pkl')
        
        X = pd.DataFrame([features])
        prediction = self.model.predict(X)[0]
        
        # 置信区间
        predictions = []
        for estimator in self.model.estimators_:
            predictions.append(estimator.predict(X)[0])
        
        confidence_lower = np.percentile(predictions, 5)
        confidence_upper = np.percentile(predictions, 95)
        
        return Prediction(
            value=prediction,
            confidence_interval=(confidence_lower, confidence_upper),
            risk='high' if prediction > features['available_hours'] * 1.2 else 'normal'
        )

class DeadlineRiskPredictor:
    """截止日期风险预测"""
    
    def __init__(self):
        self.model = GradientBoostingClassifier()
    
    def train(self, historical_tasks: pd.DataFrame):
        """训练风险预测模型"""
        features = [
            'days_until_deadline',
            'task_complexity',
            'estimated_hours',
            'historical_completion_speed',
            'current_workload',
            'concurrent_tasks'
        ]
        
        X = historical_tasks[features]
        y = historical_tasks['is_overdue']
        
        self.model.fit(X, y)
    
    def predict_risk(self, task: Task, context: dict) -> RiskAssessment:
        """预测任务延期风险"""
        features = {
            'days_until_deadline': (task.due_time - datetime.now()).days,
            'task_complexity': self._estimate_complexity(task),
            'estimated_hours': task.estimated_minutes / 60,
            'historical_completion_speed': context['avg_completion_speed'],
            'current_workload': context['weekly_workload'],
            'concurrent_tasks': context['concurrent_high_priority_tasks']
        }
        
        X = pd.DataFrame([features])
        risk_probability = self.model.predict_proba(X)[0][1]  # 延期概率
        
        return RiskAssessment(
            risk_level='high' if risk_probability > 0.7 else 'medium' if risk_probability > 0.3 else 'low',
            probability=risk_probability,
            factors=self._identify_risk_factors(features),
            suggestions=self._generate_suggestions(features, risk_probability)
        )
```

---

## 四、插件系统

### 4.1 架构设计

```
插件核心层
    ├── 插件管理器 - 加载、卸载、生命周期
    ├── API注册表 - 暴露给插件的API
    ├── 事件总线 - 插件间通信
    └── 沙箱 - 安全隔离

插件类型
    ├── 数据源插件 - 添加新的数据来源
    ├── 动作插件 - 扩展工作流动作
    ├── UI插件 - 添加界面组件
    ├── AI插件 - 自定义AI模型/提示
    └── 集成插件 - 连接新服务
```

### 4.2 插件SDK

```typescript
// plugins/sdk/index.ts

export interface PluginContext {
  // 数据API
  api: {
    tasks: TaskAPI;
    notes: NoteAPI;
    habits: HabitAPI;
  };
  
  // 事件系统
  events: EventBus;
  
  // UI扩展
  ui: {
    registerPanel: (config: PanelConfig) => void;
    registerCommand: (command: Command) => void;
    registerSetting: (setting: SettingConfig) => void;
  };
  
  // 存储
  storage: {
    get: (key: string) => Promise<any>;
    set: (key: string, value: any) => Promise<void>;
  };
  
  // 日志
  logger: Logger;
}

export interface Plugin {
  id: string;
  name: string;
  version: string;
  
  activate(context: PluginContext): void | Promise<void>;
  deactivate(): void | Promise<void>;
}

// 基类
export abstract class BasePlugin implements Plugin {
  abstract id: string;
  abstract name: string;
  abstract version: string;
  
  protected context: PluginContext;
  
  async activate(context: PluginContext): Promise<void> {
    this.context = context;
    await this.onActivate();
  }
  
  async deactivate(): Promise<void> {
    await this.onDeactivate();
  }
  
  abstract onActivate(): void | Promise<void>;
  abstract onDeactivate(): void | Promise<void>;
}

// 装饰器
export function Command(name: string, description?: string) {
  return function(target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    target._commands = target._commands || [];
    target._commands.push({
      name,
      description,
      handler: descriptor.value
    });
  };
}
```

### 4.3 示例插件

```typescript
// plugins/example-todoist-sync/index.ts

import { BasePlugin, Command, PluginContext } from '@lcc/sdk';
import { TodoistClient } from './todoist-client';

export default class TodoistSyncPlugin extends BasePlugin {
  id = 'todoist-sync';
  name = 'Todoist Sync';
  version = '1.0.0';
  
  private client: TodoistClient;
  private syncInterval: NodeJS.Timer;
  
  async onActivate(): Promise<void> {
    // 注册设置
    this.context.ui.registerSetting({
      id: 'api_token',
      name: 'Todoist API Token',
      type: 'password',
      required: true
    });
    
    // 注册命令
    this.context.ui.registerCommand({
      id: 'sync-now',
      name: 'Sync with Todoist',
      handler: () => this.sync()
    });
    
    // 注册面板
    this.context.ui.registerPanel({
      id: 'todoist-panel',
      title: 'Todoist',
      location: 'sidebar',
      render: () => this.renderPanel()
    });
    
    // 监听事件
    this.context.events.on('task.completed', (task) => {
      this.syncToTodoist(task);
    });
    
    // 自动同步
    const token = await this.context.storage.get('api_token');
    if (token) {
      this.client = new TodoistClient(token);
      this.syncInterval = setInterval(() => this.sync(), 5 * 60 * 1000);
    }
  }
  
  @Command('manual-sync', '手动同步Todoist')
  async sync(): Promise<void> {
    this.context.logger.info('Starting Todoist sync...');
    
    // 获取Todoist任务
    const todoistTasks = await this.client.getTasks();
    
    // 获取本地任务
    const localTasks = await this.context.api.tasks.list();
    
    // 双向同步
    for (const tt of todoistTasks) {
      const existing = localTasks.find(t => t.externalId === `todoist:${tt.id}`);
      if (!existing) {
        await this.context.api.tasks.create({
          name: tt.content,
          dueTime: tt.due?.date,
          externalId: `todoist:${tt.id}`
        });
      }
    }
    
    this.context.logger.info('Todoist sync completed');
  }
  
  async syncToTodoist(task: Task): Promise<void> {
    if (task.externalId?.startsWith('todoist:')) {
      const todoistId = task.externalId.replace('todoist:', '');
      await this.client.closeTask(todoistId);
    }
  }
  
  onDeactivate(): void {
    clearInterval(this.syncInterval);
  }
}
```

### 4.4 插件市场

```python
# services/plugin/marketplace.py

class PluginMarketplace:
    """插件市场服务"""
    
    def __init__(self, registry_url: str):
        self.registry = registry_url
    
    async def search(self, query: str, category: str = None) -> List[PluginInfo]:
        """搜索插件"""
        params = {'q': query}
        if category:
            params['category'] = category
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.registry}/api/plugins", params=params)
            return [PluginInfo(**p) for p in response.json()['plugins']]
    
    async def install(self, plugin_id: str, version: str = None) -> InstallResult:
        """安装插件"""
        # 1. 下载插件包
        download_url = await self._get_download_url(plugin_id, version)
        package_path = await self._download(download_url)
        
        # 2. 验证签名
        if not self._verify_signature(package_path):
            raise SecurityError("Plugin signature verification failed")
        
        # 3. 解压到插件目录
        plugin_dir = Path(f"./plugins/{plugin_id}")
        await self._extract(package_path, plugin_dir)
        
        # 4. 加载插件
        plugin = await self._load_plugin(plugin_dir)
        
        # 5. 执行安装脚本
        if (plugin_dir / 'install.js').exists():
            await self._run_install_script(plugin_dir)
        
        return InstallResult(
            success=True,
            plugin=plugin,
            message=f"Plugin {plugin_id} installed successfully"
        )
    
    async def uninstall(self, plugin_id: str):
        """卸载插件"""
        # 1. 停用插件
        await self.deactivate(plugin_id)
        
        # 2. 执行卸载脚本
        plugin_dir = Path(f"./plugins/{plugin_id}")
        if (plugin_dir / 'uninstall.js').exists():
            await self._run_uninstall_script(plugin_dir)
        
        # 3. 删除文件
        shutil.rmtree(plugin_dir)
        
        # 4. 清理数据
        await self._cleanup_data(plugin_id)
```

---

## 五、团队协作

### 5.1 权限模型

```yaml
# 角色定义
roles:
  owner:
    permissions: ['*']
    
  admin:
    permissions:
      - task:manage
      - project:manage
      - member:manage
      - settings:manage
      
  member:
    permissions:
      - task:read
      - task:create
      - task:update:own
      - task:delete:own
      - note:read
      - note:create
      
  viewer:
    permissions:
      - task:read
      - note:read
      - project:read

# 资源级权限
resource_permissions:
  task:
    - read
    - create
    - update
    - delete
    - assign
    - comment
    
  project:
    - read
    - create
    - update
    - delete
    - archive
    - invite
```

### 5.2 协作功能

```python
# services/collaboration/team_service.py

class TeamService:
    async def create_project(self, name: str, owner_id: str, members: List[str]) -> Project:
        """创建团队项目"""
        project = Project(
            id=generate_id(),
            name=name,
            owner_id=owner_id,
            created_at=datetime.now()
        )
        
        # 添加成员
        for member_id in members:
            await self.add_member(project.id, member_id, role='member')
        
        return project
    
    async def assign_task(self, task_id: str, assignee_id: str, assigner_id: str):
        """分配任务"""
        task = await self.get_task(task_id)
        
        # 检查权限
        if not await self.has_permission(assigner_id, task.project_id, 'task:assign'):
            raise PermissionError()
        
        task.assignee_id = assignee_id
        task.assigned_at = datetime.now()
        await self.save_task(task)
        
        # 发送通知
        await self.notify(assignee_id, {
            'type': 'task.assigned',
            'task_id': task_id,
            'task_name': task.name,
            'assigned_by': assigner_id
        })
    
    async def add_comment(self, task_id: str, user_id: str, content: str, mentions: List[str] = None):
        """添加评论"""
        comment = Comment(
            id=generate_id(),
            task_id=task_id,
            author_id=user_id,
            content=content,
            mentions=mentions or [],
            created_at=datetime.now()
        )
        
        await self.save_comment(comment)
        
        # 通知被@的人
        for mention in mentions:
            await self.notify(mention, {
                'type': 'comment.mention',
                'task_id': task_id,
                'comment_id': comment.id
            })
        
        # 通知任务相关人
        task = await self.get_task(task_id)
        if task.assignee_id and task.assignee_id != user_id:
            await self.notify(task.assignee_id, {
                'type': 'task.commented',
                'task_id': task_id
            })
    
    async def get_activity_feed(self, project_id: str, limit: int = 50) -> List[Activity]:
        """获取项目动态"""
        activities = await self.db.query("""
            SELECT * FROM activities
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (project_id, limit))
        
        return [Activity.from_row(row) for row in activities]
```

### 5.3 实时协作

```python
# services/collaboration/realtime.py

from fastapi import WebSocket
import json

class RealtimeCollaboration:
    """实时协作服务"""
    
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, project_id: str, websocket: WebSocket, user_id: str):
        """客户端连接"""
        await websocket.accept()
        
        if project_id not in self.connections:
            self.connections[project_id] = []
        
        self.connections[project_id].append({
            'ws': websocket,
            'user_id': user_id
        })
        
        # 发送当前在线用户
        await self.broadcast_user_list(project_id)
    
    async def disconnect(self, project_id: str, websocket: WebSocket):
        """断开连接"""
        if project_id in self.connections:
            self.connections[project_id] = [
                c for c in self.connections[project_id] 
                if c['ws'] != websocket
            ]
        
        await self.broadcast_user_list(project_id)
    
    async def broadcast(self, project_id: str, message: dict, exclude_user: str = None):
        """广播消息"""
        if project_id not in self.connections:
            return
        
        message_json = json.dumps(message)
        
        for conn in self.connections[project_id]:
            if exclude_user and conn['user_id'] == exclude_user:
                continue
            
            try:
                await conn['ws'].send_text(message_json)
            except:
                # 处理断开连接
                pass
    
    async def handle_message(self, project_id: str, user_id: str, data: dict):
        """处理客户端消息"""
        msg_type = data.get('type')
        
        if msg_type == 'cursor.move':
            # 广播光标位置
            await self.broadcast(project_id, {
                'type': 'user.cursor',
                'user_id': user_id,
                'position': data['position']
            }, exclude_user=user_id)
            
        elif msg_type == 'task.update':
            # 广播任务更新
            await self.broadcast(project_id, {
                'type': 'task.updated',
                'task_id': data['task_id'],
                'changes': data['changes'],
                'updated_by': user_id
            })
```

---

## 六、性能优化

### 6.1 数据库优化

```sql
-- 索引优化
CREATE INDEX idx_tasks_status_due ON tasks(status, due_time);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id) WHERE assignee_id IS NOT NULL;
CREATE INDEX idx_activities_project_time ON activities(project_id, created_at);

-- 分区表（大数据量时）
CREATE TABLE tasks_partitioned (
    -- 相同结构
) PARTITION BY RANGE (created_at);

CREATE TABLE tasks_2026_q1 PARTITION OF tasks_partitioned
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
```

### 6.2 缓存策略

```python
# services/cache/cache_manager.py

import redis
from functools import wraps

class CacheManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.local_cache = {}  # L1缓存
    
    async def get(self, key: str, fetch_func=None, ttl=300):
        """获取缓存"""
        # L1缓存
        if key in self.local_cache:
            return self.local_cache[key]
        
        # L2缓存 (Redis)
        value = await self.redis.get(key)
        if value:
            decoded = json.loads(value)
            self.local_cache[key] = decoded
            return decoded
        
        # 回源
        if fetch_func:
            value = await fetch_func()
            await self.set(key, value, ttl)
            return value
        
        return None
    
    async def set(self, key: str, value: any, ttl: int = 300):
        """设置缓存"""
        self.local_cache[key] = value
        await self.redis.setex(key, ttl, json.dumps(value))
    
    async def invalidate(self, pattern: str):
        """失效缓存"""
        # 清除本地缓存
        for key in list(self.local_cache.keys()):
            if pattern in key:
                del self.local_cache[key]
        
        # 清除Redis缓存
        keys = await self.redis.keys(f"*{pattern}*")
        if keys:
            await self.redis.delete(*keys)

# 装饰器
def cached(key_template: str, ttl: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            
            # 生成缓存key
            key = key_template.format(*args, **kwargs)
            
            return await cache.get(key, lambda: func(*args, **kwargs), ttl)
        return wrapper
    return decorator

# 使用
class TaskService:
    @cached("tasks:user:{user_id}:week:{week}", ttl=60)
    async def get_weekly_tasks(self, user_id: str, week: str) -> List[Task]:
        # 查询数据库
        return await self.db.query(...)
```

### 6.3 查询优化

```python
# 数据库连接池
from databases import Database

database = Database(
    "sqlite+aiosqlite:///data/app.db",
    min_size=5,
    max_size=20
)

# 分页优化
async def paginated_query(
    query: str,
    params: tuple,
    page: int = 1,
    page_size: int = 20
) -> PaginatedResult:
    # 使用游标分页代替OFFSET
    cursor = await get_cursor(params)
    
    items = await db.fetchall(
        f"{query} WHERE cursor > ? LIMIT ?",
        (*params, cursor, page_size)
    )
    
    next_cursor = items[-1]['cursor'] if items else None
    
    return PaginatedResult(
        items=items,
        next_cursor=next_cursor,
        has_more=len(items) == page_size
    )
```

---

## 七、实现时间表

| 周次 | 任务 | 输出 |
|------|------|------|
| W1-2 | 知识图谱架构<br>实体抽取 | NER模型集成<br>基础图谱 |
| W3-4 | 知识存储<br>可视化 | Neo4j部署<br>图谱展示 |
| W5-6 | 数据分析引擎<br>报表系统 | 分析API<br>仪表盘 |
| W7-8 | 预测模型<br>智能建议 | 预测服务<br>主动建议 |
| W9-10 | 插件系统架构<br>SDK开发 | 插件框架<br>开发者文档 |
| W11-12 | 插件市场<br>示例插件 | 市场上线<br>10+示例插件 |
| W13-14 | 团队协作<br>权限系统 | 团队功能<br>实时协作 |
| W15-16 | 性能优化<br>Bug修复<br>v2.0发布 | 稳定版本 |

---

*本文档将持续更新*
