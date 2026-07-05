# My-frist-Agent

这个仓库放置我的第一个Agent，边动手边学习，欢迎大家来使用我的Agent！

一款基于 DeepSeek API 的 AI 智能助手平台，支持对话、工具调用、技能管理等功能。

## 截图

![煎蛋状态](screenshots/煎蛋状态.png)
*主界面与 API 连接状态*

![思维发散控制](screenshots/思维发散控制.png)
*AI 温度/发散程度调节*

![skill管理](screenshots/skill管理.png)
*技能管理与工具选择*

![API配置](screenshots/API配置.png)
*API Key 与模型配置*

![主题与背景](screenshots/主题与背景.png)
*主题切换与背景设置*

## 特色功能

### 多功能工具箱
内置 **20+ 工具**，AI 自动调用：

| 工具类别 | 包含 |
|---------|------|
| 文件操作 | 读写、搜索、编辑、行读取 |
| 代码执行 | Shell 命令、运行测试、npm/pip 安装 |
| 网络 | 网页搜索、网页抓取、API 请求 |
| 开发辅助 | Git 操作、代码审查、正则测试、JSON 格式化 |
| 实用工具 | OCR 图片识别、翻译、文件监控、环境变量管理 |
| 数据库 | SQL 查询 |
| 进程管理 | 后台进程启停、日志查看 |

### 技能系统
可扩展的技能模板，内置多种预设场景，支持自定义 prompt 和工具绑定。

### 智能对话
基于 DeepSeek API 的流式对话，支持上下文记忆压缩、温度调节。

### 对话历史管理
会话记录持久化，支持切换、搜索和删除。

### 项目文件管理
内置文件浏览器，支持在对话中直接读写项目文件。

### 一站式配置
API Key、Base URL、模型均在应用内配置，支持连接测试。

### 桌面应用
Electron 打包，支持 Windows 原生窗口控制和系统托盘。

## 快速开始

### 前置要求

- Python 3.9+
- Node.js 18+
- DeepSeek API Key

### 安装

```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install
```

### 配置

在 `backend/config.json` 中配置 API Key，或在应用内点击顶部栏 API 状态图标进行配置。

### 启动开发服务器

```bash
cd frontend
npm run dev:server
```

启动后访问 http://localhost:5173

### 打包桌面应用

```bash
cd frontend
npm run build
npm run pack
```

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy + OpenAI SDK |
| 桌面 | Electron + electron-builder |
| 数据库 | SQLite |

## 交流反馈

![微信](screenshots/微信好友二维码.jpg)

## 许可证

[MIT](LICENSE)
