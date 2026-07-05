# MCP 协议支持 + 对话分支/编辑 — 实现方案

---

## 一、MCP 协议支持

### 1.1 概述

MCP（Model Context Protocol）是 Anthropic 发布的标准化工具协议。接入后 Agent 可连接社区已有的 MCP Server（文件系统、GitHub、数据库、浏览器、设计工具等），Skill 生态从本地函数扩展为任意网络服务。

### 1.2 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                 Agent 系统 (现有)                        │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ Skill Store  │    │ Tool Executor│                   │
│  │ (本地工具)    │    │ (22个内置工具) │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                           │
│         ▼                   ▼                           │
│  ┌─────────────────────────────────┐                    │
│  │     MCP 桥接层 (新增)            │                    │
│  │                                 │                    │
│  │  ├ MCP Client Manager          │                    │
│  │  │  管理多个 MCP Server 连接    │                    │
│  │  │  生命周期：启动/重连/关闭     │                    │
│  │  │                             │                    │
│  │  ├ Tool 映射器                 │                    │
│  │  │  MCP tool → OpenAI tool格式  │                    │
│  │  │  动态注入 agent_service      │                    │
│  │  │                             │                    │
│  │  └ 协议适配层                   │                    │
│  │     stdio 传输 / SSE 传输       │                    │
│  │     JSON-RPC 2.0 协议封装       │                    │
│  └─────────────────────────────────┘                    │
│                         │                               │
│                         ▼                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │              MCP Server 生态                      │   │
│  │  ┌────────┐ ┌──────┐ ┌────────┐ ┌───────┐       │   │
│  │  │文件系统│ │GitHub│ │ 数据库  │ │浏览器 │  ...   │   │
│  │  └────────┘ └──────┘ └────────┘ └───────┘       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 1.3 新增模块：`mcp_bridge.py`

**文件**: `backend/app/services/mcp_bridge.py`

职责：
1. 启动/管理 MCP Server 子进程（stdio 模式）或 WebSocket 连接（SSE 模式）
2. 通过 JSON-RPC 2.0 协议交换：`tools/list` → 获取工具列表，`tools/call` → 调用工具
3. 将 MCP tool 格式映射为 OpenAI function calling 格式，合并到现有 `tool_map`

核心接口：

```python
class MCPBridge:
    async def connect_stdio(command: str, args: list[str]) -> bool
    async def connect_sse(url: str) -> bool
    async def list_tools() -> list[MCPToolDef]
    async def call_tool(name: str, args: dict) -> str
    async def disconnect()
    async def reconnect()

class MCPToolDef:
    name: str
    description: str
    input_schema: dict  # JSON Schema
```

### 1.4 配置与管理方式

**方式 A（推荐 MVP）**：`mcp_servers.json` 配置文件

```json
{
  "servers": [
    {
      "name": "文件系统",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-file-server", "/path/to/project"]
    },
    {
      "name": "GitHub",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-github-server"]
    }
  ]
}
```

**方式 B（扩展）** ：在 SkillsPopover 中增加 MCP 管理页，可视化管理连接的 Server，在线添加/删除/开关。

### 1.5 与现有系统的集成

| 集成点 | 改动 |
|--------|------|
| `agent_service.py` | 在 `tool_map` 中合并 MCP tools，与内置工具统一调度 |
| `tool_executor.py` | 对 `mcp_*` 前缀的工具路由到 `MCPBridge.call_tool()` |
| `skill_store.py` | `list_skills()` 中增加 MCP Server 状态展示 |
| `store_tool_history()` | MCP 工具调用同样记录到 conversation_memory |
| 前端 SkillsPopover | 增加 MCP Server 连接状态指示灯 |

### 1.6 实现步骤

| 步 | 内容 | 工作量 |
|----|------|--------|
| 1 | 实现 `mcp_bridge.py`（stdio 子进程管理 + JSON-RPC 协议） | ~200 行 |
| 2 | 实现 `mcp_servers.json` 配置读写 | ~50 行 |
| 3 | 在 `agent_service.py` 中合并 MCP tool 到 tool_map | ~30 行 |
| 4 | 在前端 SkillsPopover 增加 MCP 状态管理 UI（列表 + 开关 + 连接状态） | ~150 行 |
| 5 | 启动时自动连接配置中的 MCP Server + 断线重连 | ~80 行 |
| 合计 | | ~500 行 |

---

## 二、对话分支/编辑

### 2.1 功能定义

- **编辑消息**：点击已发送的用户消息，原地编辑后重新生成 AI 回复
- **分叉对话**：从任意一条历史消息创建新分支，保留原对话不变
- **分支管理**：在对话列表中显示分支关系，支持切换分支

### 2.2 数据结构变更

#### MessageDB 新增字段

```python
class MessageDB(Base):
    # ... 现有字段 ...
    edited_at: str | None = None          # 编辑时间戳，非空表示已编辑
    replaces_id: str | None = None        # 被替换的消息 ID（编辑链）
    branch_parent: str | None = None      # 分支父消息 ID（分叉点）
```

#### ConversationDB 新增字段

```python
class ConversationDB(Base):
    # ... 现有字段 ...
    branch_root_id: str | None = None     # 分支根消息 ID
    is_branch: bool = False               # 是否为分支对话
```

#### 前端 Conversation 类型

```typescript
interface Conversation {
  // ... 现有字段 ...
  isBranch?: boolean
  branchRootId?: string | null
  branchLabel?: string   // 分支时间或用户备注，用于显示
}
```

### 2.3 前端交互

#### 编辑消息

```
用户点击已发送消息的编辑按钮
  → 消息内容变为可编辑 textarea
  → 确认后：
      1. 标记原消息为"已编辑"（edited_at + replaces_id）
      2. 重新调用 /api/chat 开始 SSE 流
      3. 原消息后续的所有消息被标记为"已废弃"（deprecated）
      4. SSE 流完成后，新回复替换展示
```

#### 分叉对话

```
用户在任意消息上右键/长按 → "从此处创建分支"
  → 1. 新建 ConversationDB（is_branch=True, branch_root_id=该消息.id）
  → 2. 复制该消息之前的所有消息到新对话
  → 3. 前端自动切换到新对话
  → 4. 用户输入消息 → 正常 SSE 流
```

#### 分支管理 UI

```
ConversationPopover 对话列表中：
  ├ 📄 项目架构设计 (活跃)
  ├ 📄 API 接口讨论
  └ 📂 项目架构设计 ↴          ← 有分支的对话
     ├ 📄 项目架构设计          ← 主分支
     └ 📄 项目架构设计_分支     ← 子分支，缩进 + 分支标签
```

### 2.4 后端变更

| 文件 | 变更 |
|------|------|
| `models/db_models.py` | MessageDB + ConversationDB 新增字段，数据迁移 |
| `crud/history.py` | `edit_message()`, `branch_conversation()`, `get_branch_tree()` |
| `routers/history.py` | `PUT /api/history/{id}/edit`, `POST /api/history/{id}/branch` |
| `routers/chat.py` | 编辑模式：清除后续消息 → 重新 SSE 流 |
| `services/conversation_memory.py` | 分支对话的记忆文件隔离 |

### 2.5 API 新增端点

```
PUT /api/history/{msg_id}/edit
  body: { "new_content": "..." }
  逻辑：
    1. 保存原消息的编辑记录
    2. 删除该消息之后的所有消息（标记 deprecated）
    3. 返回该消息 ID，前端重新开始 SSE 流

POST /api/history/{conv_id}/branch?from_msg_id={msg_id}
  逻辑：
    1. 创建新 Conversation（is_branch=True）
    2. 复制 from_msg_id 之前的所有消息
    3. 返回新 conversation_id

GET /api/history/{conv_id}/branches
  返回：该对话的所有分支树结构
```

### 2.6 前端变更

| 文件 | 变更 |
|------|------|
| `ChatView.tsx` | 编辑模式状态管理，触发重新 SSE 流 |
| `MessageBubble.tsx` | 编辑按钮、"已编辑"标记、分支操作菜单 |
| `ConversationPopover.tsx` | 分支树状显示、分支切换 |
| `ChatInput.tsx` | 编辑状态下表现为"确认修改"模式 |
| `MenuBar.tsx` | ConversationPopover 传入分支数据 |

### 2.7 实现步骤

| 步 | 内容 | 工作量 |
|----|------|--------|
| 1 | 数据库模型变更 + 新增 CRUD 方法 | ~100 行 |
| 2 | 新增 API 端点（edit / branch / tree） | ~100 行 |
| 3 | MessageBubble 编辑按钮 + 编辑态 UI | ~80 行 |
| 4 | ChatView 编辑模式 + 重新 SSE 流 | ~100 行 |
| 5 | ConversationPopover 分支树显示 | ~80 行 |
| 6 | 分叉对话 API 调用 + 前端流程 | ~60 行 |
| 7 | 编辑消息的记忆文件处理 | ~40 行 |
| 合计 | | ~560 行 |

---

## 三、两项功能比较

| 维度 | MCP 协议 | 对话分支/编辑 |
|------|---------|-------------|
| **用户价值** | 生态扩展，连接外部服务 | 日常对话体验提升 |
| **实现复杂度** | 中（需处理子进程/协议） | 中（需处理数据关系） |
| **代码量** | ~500 行 | ~560 行 |
| **风险** | 低（独立模块，不影响核心） | 低（新增字段，向后兼容） |
| **前置依赖** | 无 | 无 |
| **可并行开发** | 是 | 是 |

两项不冲突，可以独立实现。建议先做**对话分支/编辑**（日常使用频率高，价值立竿见影），再做 MCP 协议支持。
