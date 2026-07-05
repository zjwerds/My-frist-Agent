---
name: 项目脚手架
description: 系统化项目搭建流程：需求分析 → 目录设计 → 逐文件创建 → 依赖安装 → Git初始化 → 启动验证
category: 选蛋
enabled: false
builtin: true
---

# 项目脚手架 Skill

当用户要求你「建一个新项目」或「搭一个脚手架」时，请按照以下流程操作。

## 流程

### 第一步：需求澄清
先向用户确认以下信息（不要一次全问，逐轮确认）：
1. **项目类型**：前端/后端/全栈/Python库/CLI工具/其他？
2. **技术栈偏好**：有指定框架/库吗？没有就按最佳实践推荐
3. **项目名称**：目录名、包名
4. **额外需求**：需要数据库？API？测试？部署？

用户给的信息越少，你要问的问题就越多。不要替用户做假设。

### 第二步：目录结构设计
向用户展示拟建的目录结构（用 tree 格式），**获得确认后**再开始创建。

### 第三步：逐文件创建
按依赖顺序创建文件（先配后码）：
1. **配置文件**：`package.json` / `pyproject.toml` / `tsconfig.json` / `vite.config.ts` 等
2. **入口文件**：`main.py` / `index.ts` / `App.tsx` 等
3. **业务代码**：按模块组织
4. **测试文件**：与业务代码一一对应
5. **文档**：`README.md` 等

每创建几个文件后，用 `git_operation` 做一次 commit。
用 `edit_file` 精确编辑，避免整文件覆写。

### 第四步：安装依赖
创建完所有文件后：
- Node 项目：`npm_install`（无需指定包名，自动安装 `package.json` 中所有依赖）
- Python 项目：`pip_install`（确保有 `requirements.txt`）

### 第五步：Git 初始化
```bash
git init
git add .
git commit -m "🎉 initial scaffold"
```
用 `shell_command` 执行，完成后通知用户。

### 第六步：验证
运行项目检查是否可以启动：
- 前端：`npm run dev`（用 `start_process` 启动后，用 `api_request` 检查端口响应）
- 后端：`python main.py`（同样用 `start_process` + `api_request` 验证）
- 测试：`run_tests runner=auto`

验证通过后汇报结果。

## 注意
- 每步执行前询问用户是否同意
- 文件内容要完整可用，不要留 TODO 占位
- 优先复用现有工具链，避免创建冗余文件
