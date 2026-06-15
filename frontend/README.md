# 企业级 RAG 前端

基于 **Vue 3 + Vite + Element Plus + Pinia + ECharts** 的管理与问答前端。

## 功能

- 智能问答：多轮对话，展示答案与引用来源
- 文档管理：上传 / 列表 / 删除 / 状态
- 施工图处理：上传解析、查看提取实体
- 知识图谱：ECharts 力导向图可视化
- 项目管理：项目 CRUD
- 智能分析：成本 / 进度 / 安全 / 风险 / 周报 + 项目看板
- 系统管理：状态监控、索引重建、缓存清理

## 开发

```bash
npm install
npm run dev      # 默认 5173 端口，/api 代理到后端 http://localhost:8000
```

## 构建

```bash
npm run build    # 产物输出到 dist/
```

后端接口前缀为 `/api/v1`，可通过 `.env.development` 的 `VITE_API_BASE` 调整。
