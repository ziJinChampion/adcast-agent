# AdCast Agent - AI自动广告投放Agent

AI驱动的自动广告投放系统，基于 **LangGraph** 实现 Observe-Analyze-Act 智能闭环，自动识别最优广告平台，通过MCP协议智能投放。

## 核心架构

```
  +------------+    LangGraph StateGraph    +-------------+
  |  OBSERVE   | -- 收集平台数据+历史表现 --> |  ANALYZE    |
  |   观察     |                             |   LLM分析   |
  +-----+------+                             +------+------+
        ^                                           |
        |  [循环Loop]                                 v
        |                                    +------+------+
        |                                    |   DECIDE    |
        |                                    |   AI决策     |
        |                                    +------+------+
        |                                           |
        v                                    +------v------+
  +------------+    Checkpoint 持久化       |   EXECUTE   |
  |  REFLECT   | <--- 保存状态(内存/PG) --- |   执行投放   |
  |   反思优化  |                             +------+------+
  +------------+                                    |
        ^                                           v
        |                              +------------+-----------+
        +--- 学习笔记 --> 长期记忆 ---- |  定时循环(可调间隔)      |
                                      +------------------------+
```

## 支持的平台

### 海外平台（官方MCP）

| 平台 | MCP类型 | 状态 | 能力 |
|------|---------|------|------|
| **Google Ads** | 官方MCP | 只读(可配置写入) | 搜索/展示/购物/视频 |
| **Meta Ads** | 官方MCP (Beta) | 读写 | FB/IG全功能 |
| **Amazon DSP** | 官方MCP | 读写 | DSP库存/预测 |
| **Adform FLOW** | 官方MCP | 读写 | 全栈800+能力 |

### 国内平台

| 平台 | 接入方式 | 状态 | 能力 |
|------|---------|------|------|
| **巨量引擎** | 官方MCP | 读写 | 抖音/头条全功能 |
| **腾讯广告** | 自研Adapter | 读写 | 朋友圈/视频号 |
| **快手磁力引擎** | 自研Adapter | 读写 | 快手/极速版 |
| **百度营销** | 自研Adapter | 读写 | 搜索/信息流 |

## 项目结构

```
adcast-agent/
├── src/adcast_agent/
│   ├── __init__.py
│   ├── main.py                    # 主入口 (AI Loop + One-shot)
│   ├── platform_manager.py        # 平台管理器
│   ├── mcp/                       # MCP客户端层
│   │   ├── client.py              # MCP客户端(stdio/HTTP)
│   │   └── registry.py            # MCP注册表
│   ├── platforms/                 # 平台接入层
│   │   ├── base.py                # 平台基类(MCP+API)
│   │   ├── google_ads/
│   │   ├── meta_ads/
│   │   ├── amazon_dsp/
│   │   ├── adform/
│   │   ├── oceanengine/
│   │   ├── tencent_ads/
│   │   ├── kuaishou/
│   │   └── baidu_ads/
│   ├── core/                      # ===== AI引擎核心 =====
│   │   ├── agent_graph.py         # LangGraph StateGraph (O-A-A闭环)
│   │   ├── campaign_loop.py       # Loop生命周期管理
│   │   ├── decision_engine.py     # 规则引擎(降级方案)
│   │   ├── budget_allocator.py    # 预算分配器
│   │   ├── campaign_manager.py    # Campaign管理器
│   │   ├── checkpoint.py          # Checkpoint双后端(Memory/PG)
│   │   ├── llm_client.py          # LLM客户端(OpenAI/Anthropic)
│   │   └── long_term_memory.py    # 长期记忆(预留接口)
│   └── utils/
│       ├── config.py              # 配置管理(LLM/CK/LP)
│       ├── logger.py              # 结构化日志
│       └── security.py            # 安全控制
├── config/
│   └── settings.yaml              # 配置文件
├── .env.example                   # 环境变量模板
├── requirements.txt
├── setup.py
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/ziJinChampion/adcast-agent.git
cd adcast-agent

# 安装基础依赖
pip install -r requirements.txt

# 如果需要PostgreSQL checkpoint后端
pip install asyncpg
```

### 2. 配置

```bash
cp config/settings.yaml config/settings.yaml
cp .env.example .env
```

编辑 `config/settings.yaml`：

```yaml
# LLM配置
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "sk-your-key-here"

# Checkpoint配置 (memory 或 postgres)
checkpoint:
  backend: "memory"          # 开发用memory，生产用postgres
  postgres:
    host: "localhost"
    port: 5432
    database: "adcast"
    user: "adcast"
    password: "your-password"

# Loop配置
loop:
  interval_minutes: 60       # 每次优化间隔
  max_iterations: 10         # 最大迭代次数

# 启用需要的平台...
platforms:
  google_ads:
    enabled: true
    ...
```

### 3. AI Loop 模式（推荐）

```bash
# 启动AI Loop（LLM智能决策 + 定时优化）
python -m adcast_agent run \
  --name "夏季促销" \
  --objective sales \
  --budget 10000 \
  --daily-budget 500 \
  --market global \
  --interval 60

# 持续运行模式（后台定时循环）
python -m adcast_agent run \
  --name "持续投放" \
  --objective conversions \
  --budget 50000 \
  --daily-budget 1000 \
  --continuous \
  --interval 120

# 查看状态
python -m adcast_agent status --name "夏季促销"

# 暂停/恢复
python -m adcast_agent pause --name "夏季促销"
python -m adcast_agent resume --name "夏季促销"
```

### 4. One-shot 模式（传统）

```bash
python -m adcast_agent oneshot \
  --name "快速测试" \
  --objective conversions \
  --budget 1000 \
  --auto-activate
```

### 5. 编程方式使用

```python
import asyncio
from adcast_agent.main import AdCastAgent
from adcast_agent.platforms.base import PlatformAudience

async def main():
    agent = AdCastAgent()
    await agent.initialize()

    # ===== AI Loop 模式 =====
    # LLM自动分析选择平台 + 定时优化闭环
    result = await agent.run_ai_loop(
        name="智能投放测试",
        objective="conversions",
        budget=10000,
        daily_budget=500,
        target_market="overseas",
        industry="ecommerce",
        interval_minutes=60,       # 每60分钟优化一次
        max_iterations=10,
    )
    # 输出AI决策结果：选中的平台、预算分配、AI推理理由
    print(result["selected_platforms"])
    print(result["budget_allocation"])

    # 恢复Loop（人工审批后继续）
    result = await agent.resume_loop("智能投放测试")

    # 推送报表数据（外部定时任务调用）
    await agent.update_loop_reports("智能投放测试", {
        "google_ads": [{"date": "2024-01-01", "spend": 100, "conversions": 5}],
        "meta_ads": [{"date": "2024-01-01", "spend": 80, "conversions": 3}],
    })

    # ===== One-shot 模式 =====
    result = await agent.run_campaign(
        name="单次投放",
        objective="sales",
        budget=5000,
        target_market="domestic",
    )

    await agent.shutdown()

asyncio.run(main())
```

## AI Loop 工作原理

### 1. OBSERVE - 收集
- 拉取各平台实时数据（预测、受众规模）
- 从长期记忆获取历史投放经验
- 获取当前Campaign的报表数据

### 2. ANALYZE - LLM分析
- 将Campaign需求 + 平台数据发送给LLM
- LLM分析：受众匹配度、成本效率、ROAS潜力
- 输出各平台评分和推荐理由

### 3. DECIDE - AI决策
- 综合LLM分析和规则引擎
- 确定平台选择和预算分配
- 高风险操作自动暂停等待审批

### 4. EXECUTE - 执行
- 在各平台创建Campaign（默认PAUSED）
- 设置预算和受众定向
- 记录执行结果

### 5. REFLECT - 反思
- 分析投放表现
- 提取学习笔记
- 写入长期记忆
- 决定是否继续循环

### 循环控制
- 达到 `max_iterations` 自动结束
- 人工审批后 `resume_loop()` 继续
- 超支自动暂停（安全控制）
- 每次迭代后自动Checkpoint

## Checkpoint 配置

| 后端 | 适用场景 | 配置 |
|------|---------|------|
| **memory** | 开发/测试，快速迭代 | `checkpoint.backend: "memory"` |
| **postgres** | 生产环境，持久化 | `checkpoint.backend: "postgres"` |

环境变量快速切换：
```bash
export ADCAST_CHECKPOINT_BACKEND=postgres
export ADCAST_PG_PASSWORD=your_password
export ADCAST_LLM_API_KEY=sk-your-key
```

## 安全控制

- **Human-in-the-loop**: AI决策高风险时自动暂停，等待人工 `resume_loop()`
- **预算护栏**: 全局和平台级别预算上限
- **审计日志**: 所有操作完整记录
- **默认暂停**: 新Campaign默认PAUSED，确认后才激活
- **超支保护**: 超支自动暂停

## 技术栈

- **Python 3.10+**
- **LangGraph 0.2+** - AI Agent状态图和Loop控制
- **MCP (Model Context Protocol)** - AI与广告平台通信
- **OpenAI API** - LLM决策（兼容Anthropic等）
- **PostgreSQL** - Checkpoint持久化（可选）
- **aiohttp** - 异步HTTP客户端

## 许可证

MIT License
