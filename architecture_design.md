# 竞品素材智能监控与分析系统 - 架构设计文档 (TAD)

## 1. 项目背景与目标
随着跨境电商和数字营销的发展，业务部门需要时刻关注竞品在各大渠道（如 Amazon、独立站、社媒等）的最新营销素材和产品卖点。
本项目旨在构建一个**自动化的智能体 (Agent) 系统**，实现：
1. **自动抓取**各大竞品的最新最优素材。
2. **智能分析**素材的核心卖点、目标人群和文案策略，并自动打标。
3. **沉淀资产**并构建企业内部的智能素材库。
4. **自然语言交互**，允许业务人员通过对话形式检索素材并获取营销策略建议。

## 2. 总体架构图 (Data Flow & Architecture)

系统整体基于 **RAG (Retrieval-Augmented Generation, 检索增强生成)** 架构，分为四大核心模块：

```text
┌─────────────────┐       ┌───────────────────┐       ┌─────────────────┐
│                 │       │                   │       │                 │
│  数据采集与监控层 │───────▶│ 多模态 AI 预处理层  │───────▶│ 数据存储与资产层  │
│  (Scraping)     │       │ (AI Processing)   │       │ (Storage)       │
│                 │       │                   │       │                 │
└─────────────────┘       └───────────────────┘       └────────┬────────┘
        ▲                                                      │
        │ 定时调度 (Airflow/Celery)                            │ 向量化 & 同步
        │                                                      ▼
        │                                             ┌─────────────────┐
        │                                             │                 │
        └─────────────────────────────────────────────│ 智能交互与问答层  │
                                                      │ (RAG & Chat UI) │
                                                      │                 │
                                                      └─────────────────┘
```

## 3. 核心模块详细设计

### 3.1 数据采集与监控层 (Data Acquisition)
*   **职责**：从目标渠道（如 Amazon US 等）获取竞品最新的产品标题、A+ 页面文案、主图、评价数据等。
*   **实现策略**：
    *   **短期/MVP阶段**：使用第三方商业 API（如 Rainforest API, 亮数据 BrightData）或 Python `requests` + `BeautifulSoup` 获取结构化数据。
    *   **长期阶段**：构建基于 `Playwright` 或 `Selenium` 的无头浏览器集群，配合代理 IP 池（Proxy Pool）绕过反爬虫机制，实现对动态渲染页面的深度抓取。
*   **调度机制**：使用 `Crontab` 或 `Apache Airflow` 配置定时任务，例如每日凌晨执行竞品 ASIN 列表的巡检。

### 3.2 多模态 AI 预处理层 (AI Processing Pipeline)
*   **职责**：对抓取回来的“生数据”进行清洗、结构化提取和深度分析。
*   **核心逻辑**：
    *   **LLM 自动打标**：将产品标题和文案传入大语言模型（如 MiniMax `abab6.5s-chat`），通过精设的 Prompt 提取关键特征（如：材质、适用场景、技术名词），生成 `ai_tags`。
    *   **营销策略提炼**：要求 LLM 扮演营销专家，生成一段深入的 `ai_analysis`，分析该素材为什么能吸引用户（例如情绪价值、痛点切入等）。
    *   *(未来规划)* **计算机视觉 (CV)**：引入多模态大模型（如 GPT-4o 或 MiniMax-VL），直接对抓取到的商品主图/视频进行解析，提取视觉风格（如：极简风、高饱和度）。

### 3.3 数据存储与资产管理层 (Storage & Vectorization)
*   **职责**：安全、高效地存储结构化业务数据和高维向量数据。
*   **技术选型**：
    *   **关系型数据库 (MySQL / PostgreSQL)**：存储素材的基础元数据（品牌、渠道、文案、评价数、原始 URL）。
    *   **对象存储 (OSS / S3)**：存储抓取回来的图片和视频原文件，确保链路稳定。
    *   **向量数据库 (Vector DB)**：
        *   将拼接后的丰富文本（包含品牌、标签、AI 分析等）通过 Embedding 模型（如 MiniMax `embo-01`）转化为高维向量。
        *   MVP 阶段使用轻量级的本地 `ChromaDB`。
        *   生产阶段建议升级为 `Milvus` 或 `PostgreSQL + pgvector`，以支持亿级数据的毫秒级检索。

### 3.4 智能交互与问答层 (RAG-based Chat UI)
*   **职责**：面向业务终端用户，提供类似 ChatGPT 的对话式查询界面。
*   **交互流程 (RAG 核心)**：
    1.  **意图识别**：用户输入自然语言（如：“推荐适合大户型的冰箱素材”）。
    2.  **向量检索 (Retrieval)**：将用户 Query 向量化，去向量数据库中进行相似度匹配 (Similarity Search)，召回 Top-K 相关的竞品素材。
    3.  **增强生成 (Generation)**：将召回的素材上下文（Context）和用户的原始问题组装成 Prompt，提交给 LLM。
    4.  **结果渲染**：前端将 LLM 生成的策略建议以 Markdown 格式输出，并在下方渲染出对应的竞品图片及来源跳转链接。
*   **前端选型**：MVP 阶段采用 `Streamlit` 快速构建数据面板与聊天流；生产环境可基于 `React` / `Vue` 定制开发接入企业内部系统。

## 4. 关键接口与数据流转约定

### 4.1 核心数据结构 (JSON)
爬虫层传递给 AI 处理层，以及最终存入数据库的标准数据结构约定：
```json
{
  "id": "samsung_tv_001",
  "channel": "Amazon US",
  "brand": "Samsung",
  "category": "TV",
  "title": "SAMSUNG 65-Inch Class OLED 4K S95C Series Quantum HDR Smart TV",
  "original_copy": "Experience the difference of Samsung OLED...",
  "image_url": "https://images.unsplash.com/...",
  "source_url": "https://www.amazon.com/dp/B0BTFBM4C6",
  "metadata": {
    "rating": 4.6,
    "reviews": 1205
  },
  "ai_tags": ["OLED", "4K", "家庭影院", "电竞高刷"],
  "ai_analysis": "该素材针对北美高端电视市场，文案重点突出OLED..."
}
```
*(注：存入 ChromaDB 等向量库时，`metadata` 等嵌套结构需序列化为 JSON 字符串以满足底层限制)*

## 5. 项目演进路线图 (Roadmap)

*   **Phase 1 (MVP 论证 - 已完成)**：跑通基于本地 JSON 数据和 ChromaDB 的 Streamlit 对话交互，验证 MiniMax LLM 的打标和分析能力。
*   **Phase 2 (自动化流水线接入)**：部署独立的爬虫脚本，集成定时任务，实现每日自动抓取特定渠道的 Top 100 新品，并自动流转至 AI 分析层。
*   **Phase 3 (工程化与平台化)**：将底层数据库升级为 MySQL + Milvus，开发企业级前端 Web 界面，增加用户权限管理、API 额度监控、以及内部私有素材库的上传与混排推荐功能。