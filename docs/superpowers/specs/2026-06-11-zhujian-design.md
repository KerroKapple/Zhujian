# 筑见 BuildView · 全面重构设计基线

> 单一事实源。所有重构 agent 以此为准。日期 2026-06-11。

## 1. 产品

- **名称**：筑见（中文）/ BuildView（英文）/ slug `zhujian`
- **定位**：建筑工程「行业知识库 + 项目智能分析」双核平台
- **用户**：多角色（项目 / 造价 / 安全 / 技术），统一「工作台 + 角色切换」组织
- **双核**：
  - 知识核：规范/合同/项目文档 RAG 问答 + 施工图理解 + 知识图谱
  - 项目核：造价 / 进度 / 安全 / 风险 / 周报 五类 Agent 分析

## 2. 后端策略：契约优先 + 真实实现 + 优雅降级

- 外部依赖（Milvus / Neo4j / PostgreSQL / Redis / 嵌入模型 / LLM）缺失时**优雅降级**：返回明确的「服务不可用 / 降级」语义（HTTP 503 + 统一错误体，或带 `degraded:true` 的空结果），**绝不返回假数据**。
- 无 infra 也能跑（本机开发），有 infra 全功能。

### 2.1 分层与依赖注入（抽象层）

```
app/api/v1/*.py   路由层：仅做 HTTP 入参校验 + 调 service + 返回
services/<域>/*    服务层：业务编排，纯类，构造注入依赖；抛领域异常；降级处理
repository/*        数据访问层：DB/向量/图查询
services/.../client 基础设施单例：milvus_client / neo4j_client / redis_client
```

- **禁止**路由层直接 `new` repository / 直接拼业务；统一经 `core/deps.py` 的 `Depends(get_xxx_service)` 注入。
- 服务类位于 `services/<域>/<域>_service.py`，构造函数接收 repo/client（或内部惰性获取），方法返回 DTO/dict，失败抛 `core/exceptions` 的领域异常。

### 2.2 统一基础设施（基座 · BF agent 负责）

- `core/exceptions.py`：`AppException(code, message, http_status, detail=None)` 基类 + 子类 `NotFoundError(404)`、`ValidationError(422)`、`ServiceUnavailableError(503)`、`UnauthorizedError(401)`、`ConflictError(409)`；`register_exception_handlers(app)` 统一映射为错误体。
- **统一错误体**：`{"success": false, "error": {"code": str, "message": str, "detail": any}}`。
- `app/schemas/common.py`：`Page[T]`（`{items, total, page, page_size}`）、`ErrorResponse`、`OkResponse`。
- `core/deps.py`：`get_db()`（DB 会话，yield+close）、各 `get_xxx_service()`（函数内惰性 import 服务类，构造并返回）。

### 2.3 API 响应契约（前后端共同遵守）

- 列表类：返回 `Page` 形 `{items, total, page, page_size}`。
- 详情/动作类：返回资源对象，或 `{success:true, ...}`。
- 错误：走异常处理器，统一错误体（见上），前端 axios 拦截器据此提示。
- 前端 `request.js` 拦截器返回 `response.data`（即上面的 body）。

### 2.4 各域补全（占位 → 真实 + 降级）

- **qa**：`/qa/chat`、`/qa/ask`、`/qa/ask/stream` 接 `services.rag.pipeline`（RAG 编排）；无向量/LLM 时降级为「仅返回检索片段」或 503，并在 `metadata.degraded` 标注。`/qa/feedback/{id}` 落 `QueryFeedback` 表（无 DB 则 503）。
- **document**：list/detail/status 接 `DocumentRepository`（真实分页/查询）；upload 落库 + 触发处理；无 DB 降级 503。
- **drawing**：处理状态从进程内存 dict 迁到 Redis/DB（无则单进程内存兜底并告警）。
- **admin**：统计接真实来源（psutil 系统指标 + repo 计数 + 各 client.ping），不再假数据。
- **projects**：全部经 `ProjectService`，真实分页 count。
- **agents**：保持现有真实实现，统一错误处理与响应契约。

## 3. 前端设计系统：工程蓝 Console（FF agent 负责基座）

### 3.1 设计 Token（`src/styles/tokens.css`，CSS 变量）

- 主操作色 `--c-primary:#1f6feb`；深工程蓝（侧栏/品牌）`--c-ink:#16335c` / `--c-ink-2:#0f274d`
- 语义色：成功 `#2da44e`、警告 `#d29922`、危险 `#cf222e`、信息 `#1f6feb`
- 中性：页底 `--c-bg:#eef1f5`、卡片 `--c-surface:#fff`、边框 `--c-border:#e3e8ef`、主文 `#1f2733`、次文 `#5b6675`
- 圆角 `--r-sm:6px / --r-md:10px / --r-lg:14px`；阴影 `--shadow-card:0 1px 3px rgba(20,40,80,.06)`；间距 4 的倍数；侧栏宽 220（收起 64）
- 暗色看板专用 token（风险/安全大屏）：底 `#0d1117`、面 `#161c27`、高亮青 `#2dd4bf` / 橙 `#f59e0b`

### 3.2 应用骨架（`MainLayout.vue`）

- 左：**深色侧栏**（筑见 logo + 双核分组导航：知识/项目 + 角色切换器 + 收起按钮）
- 顶：浅色 bar（全局搜索、通知、用户菜单、当前角色）
- 中：浅灰内容区（白卡片）
- Element Plus 主题：用 CSS 变量覆盖 primary 等

### 3.3 共享组件（`src/components/`）

`AppPage`(页头：标题/描述/操作位 + 内容插槽)、`AppCard`、`StatTile`(指标卡，带语义色)、`StatusTag`、`EmptyState`、`SkeletonBlock`、`SectionTitle`。

### 3.4 图表（`src/charts/theme.js`）

注册 ECharts「zhujian」主题（工程蓝色板 + 暗色看板变体），统一通过 `BaseChart.vue` 或 `useChart` 使用并在卸载时 `dispose()`。

### 3.5 角色（Pinia `stores/user.js`）

`role` ∈ {全部, 项目, 造价, 安全, 技术}；工作台据 role 聚合不同卡片。

### 3.6 页面（FF 基座后并行重做）

工作台（多角色聚合：待办/项目概览/快捷问答/预警）、智能问答（对话+引用+流式）、文档管理、施工图、知识图谱（暗色看板）、项目、智能分析（Agent 暗色看板）、系统管理。

## 4. 命名落地

`APP_NAME`/描述（config）、前端 `<title>`+logo+品牌位、README、部署文档全部改「筑见 BuildView」。`pyproject.toml` 包名按全局规则不手改，保持内部名。GitHub 远端仓库重命名需用户自行操作。

## 5. 不变量（每个 agent 收尾必须保证）

- 后端：`uv run python scripts/_smoke_imports.py` 0 失败；`uv run pytest -q` 全过；`uv run python -c "import app.main"` OK。
- 前端：`npm run build` 通过。
- 全局规则：uv-only、中文极简注释、不向后兼容、重构干净不打补丁、懒加载重型依赖、Pydantic2/SQLAlchemy2/时区感知。
