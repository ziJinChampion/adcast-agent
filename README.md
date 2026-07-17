# AdCast Agent - AI自动广告投放Agent

AI驱动的自动广告投放系统，自动识别最优广告平台，通过MCP协议智能投放。

## 架构概览

```
                    Campaign Request
                          |
            +-------------v-------------+
            |    投放决策引擎            |
            |  (平台选择 + 预算分配)      |
            +-------------+-------------+
                          |
        +-----------------+-----------------+
        |                 |                 |
   海外平台(MCP)      国内MCP直连       国内API Adapter
        |                 |                 |
  Google Ads       巨量引擎(官方)      腾讯广告
  Meta Ads               |              快手
  Amazon DSP             |              百度
  Adform FLOW            |
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

### 忽略的平台（API有限或价值低）

知乎广告、拼多多广告、阿里妈妈、微博广告（API门槛高或能力有限）

## 项目结构

```
adcast-agent/
├── src/adcast_agent/
│   ├── __init__.py
│   ├── main.py                    # 主入口
│   ├── platform_manager.py        # 平台管理器
│   ├── mcp/                       # MCP客户端层
│   │   ├── client.py              # MCP客户端(stdio/HTTP)
│   │   └── registry.py            # MCP注册表
│   ├── platforms/                 # 平台接入层
│   │   ├── base.py                # 平台基类
│   │   ├── google_ads/            # Google Ads MCP
│   │   ├── meta_ads/              # Meta Ads MCP
│   │   ├── amazon_dsp/            # Amazon DSP MCP
│   │   ├── adform/                # Adform MCP
│   │   ├── oceanengine/           # 巨量引擎 MCP
│   │   ├── tencent_ads/           # 腾讯广告 Adapter
│   │   ├── kuaishou/              # 快手 Adapter
│   │   └── baidu_ads/             # 百度 Adapter
│   ├── core/                      # 核心引擎
│   │   ├── decision_engine.py     # 投放决策引擎
│   │   ├── budget_allocator.py    # 预算分配器
│   │   └── campaign_manager.py    # Campaign管理器
│   └── utils/                     # 工具
│       ├── config.py              # 配置管理
│       ├── logger.py              # 结构化日志
│       └── security.py            # 安全控制
├── config/
│   └── settings.yaml              # 配置文件模板
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
pip install -r requirements.txt
```

### 2. 配置平台凭证

复制配置文件模板：

```bash
cp config/settings.yaml config/settings.yaml
cp .env.example .env
```

编辑 `config/settings.yaml`，启用需要的平台并填入凭证。

### 3. 运行Agent

```bash
# 查看帮助
python -m adcast_agent --help

# 创建一个Campaign
python -m adcast_agent \
  --campaign "夏季促销活动" \
  --objective sales \
  --budget 5000 \
  --daily-budget 200 \
  --market global \
  --strategy roas_maximize
```

### 4. 编程方式使用

```python
import asyncio
from adcast_agent.main import AdCastAgent
from adcast_agent.platforms.base import PlatformAudience

async def main():
    agent = AdCastAgent()
    await agent.initialize()
    
    # 创建受众
    audience = PlatformAudience(
        age_min=25,
        age_max=45,
        genders=["female"],
        geo_locations=["US", "CA"],
        interests=["fashion", "beauty"],
    )
    
    # 运行Campaign
    result = await agent.run_campaign(
        name="新品推广",
        objective="conversions",
        budget=10000,
        daily_budget=500,
        target_market="overseas",
        audience=audience,
        industry="ecommerce",
        strategy="roas_maximize",
    )
    
    print(result)
    
    # 手动激活Campaign
    await agent.activate_campaigns("新品推广")
    
    # 获取报表
    report = await agent.get_report("新品推广")
    print(report)
    
    await agent.shutdown()

asyncio.run(main())
```

## 决策引擎

Agent会自动评估各平台并给出推荐：

1. **受众匹配度** - 平台受众与目标受众的匹配程度
2. **成本效率** - CPM/CPC预估
3. **ROAS潜力** - 预估转化回报率
4. **竞争度** - 市场竞争激烈程度
5. **平台能力** - API/MCP功能完整度

### 投放策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `roas_maximize` | ROAS最大化 | 电商转化 |
| `reach_maximize` | 触达最大化 | 品牌曝光 |
| `conversion_maximize` | 转化最大化 | 线索收集 |
| `balanced` | 均衡策略 | 多目标 |
| `cost_minimize` | 成本最小化 | 预算紧张 |

### 预算分配策略

| 策略 | 说明 |
|------|------|
| `equal` | 等比例分配 |
| `roas_weighted` | 按预估ROAS加权 |
| `matthew` | 马太效应（强者更多） |
| `exploration` | 探索-利用平衡 |

## 安全控制

- **Human-in-the-loop**: 所有写入操作默认需要人工确认
- **预算护栏**: 全局和平台级别预算上限
- **审计日志**: 所有操作完整记录
- **默认暂停**: 新Campaign默认PAUSED状态
- **超支保护**: 超支自动暂停

## 扩展开发

### 添加新平台MCP接入

1. 在 `src/adcast_agent/platforms/` 创建新目录
2. 继承 `MCPAdPlatform` 基类
3. 实现必要的方法（create_campaign, get_report等）
4. 在 `PlatformManager.PLATFORM_FACTORIES` 注册

### 添加新平台API Adapter

1. 继承 `APIAdPlatform` 基类
2. 实现 `_build_headers()` 和 API调用方法
3. 在 `PlatformManager.PLATFORM_FACTORIES` 注册

## 技术栈

- **Python 3.10+** - 核心语言
- **MCP (Model Context Protocol)** - AI与平台通信协议
- **aiohttp** - 异步HTTP客户端
- **YAML** - 配置管理
- **JSON** - 结构化日志

## 许可证

MIT License
