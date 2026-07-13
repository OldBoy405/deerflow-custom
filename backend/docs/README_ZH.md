# 文档

本目录包含 DeerFlow 后端的详细文档。

## 快速链接

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构概览 |
| [API.md](API.md) | 完整 API 参考 |
| [CONFIGURATION_ZH.md](CONFIGURATION_ZH.md) | 配置项说明 |
| [SETUP.md](SETUP.md) | 快速安装指南 |

## 功能文档

| 文档 | 说明 |
|------|------|
| [STREAMING.md](STREAMING.md) | 令牌级流式传输设计：Gateway 与 DeerFlowClient 两条路径、`stream_mode` 语义、按 id 去重 |
| [FILE_UPLOAD.md](FILE_UPLOAD.md) | 文件上传功能 |
| [PATH_EXAMPLES.md](PATH_EXAMPLES.md) | 路径类型与使用示例 |
| [summarization.md](summarization.md) | 上下文摘要功能 |
| [plan_mode_usage.md](plan_mode_usage.md) | 结合 TodoList 的计划模式 |
| [AUTO_TITLE_GENERATION.md](AUTO_TITLE_GENERATION.md) | 自动生成标题 |

## 开发

| 文档 | 说明 |
|------|------|
| [TODO.md](TODO.md) | 计划中的功能与已知问题 |

## 入门指引

1. **初次使用 DeerFlow？** 从 [SETUP.md](SETUP.md) 开始快速安装  
2. **需要配置系统？** 参阅 [CONFIGURATION_ZH.md](CONFIGURATION_ZH.md)  
3. **想理解架构？** 阅读 [ARCHITECTURE.md](ARCHITECTURE.md)  
4. **要做集成开发？** 查看 [API.md](API.md) 获取 API 参考  

## 文档结构

```
docs/
├── README.md                  # 英文索引
├── README_ZH.md               # 本文件（简体中文索引）
├── ARCHITECTURE.md            # 系统架构
├── API.md                     # API 参考
├── CONFIGURATION.md           # 配置指南（英文）
├── CONFIGURATION_ZH.md        # 配置指南（简体中文）
├── SETUP.md                   # 安装说明
├── FILE_UPLOAD.md             # 文件上传功能
├── PATH_EXAMPLES.md           # 路径使用示例
├── summarization.md           # 摘要功能
├── plan_mode_usage.md         # 计划模式功能
├── STREAMING.md               # 令牌级流式传输设计
├── AUTO_TITLE_GENERATION.md   # 标题生成
├── TITLE_GENERATION_IMPLEMENTATION.md  # 标题实现细节
└── TODO.md                    # 路线图与问题跟踪
```
