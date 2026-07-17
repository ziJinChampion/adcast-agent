"""
LLM 客户端模块 - 统一大语言模型调用接口

支持多种LLM提供商：
- OpenAI (GPT-4, GPT-4o, GPT-3.5-turbo)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- 其他兼容OpenAI API的提供商

配置方式（settings.yaml）：
    llm:
      provider: "openai"  # 或 "anthropic"
      model: "gpt-4o"
      api_key: "sk-..."
      base_url: null       # 自定义API地址（如使用代理）
      temperature: 0.3     # 决策需要稳定性
      max_tokens: 4096
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("adcast.llm")


@dataclass
class LLMMessage:
    """LLM消息"""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str = ""
    usage: Dict[str, int] = None
    raw_response: Any = None


class LLMClient:
    """
    LLM客户端 - 统一调用接口
    
    使用OpenAI SDK的统一接口，兼容多家提供商。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.provider = self.config.get("provider", "openai").lower()
        self.model = self.config.get("model", "gpt-4o")
        self.api_key = self.config.get("api_key", "")
        self.base_url = self.config.get("base_url", None)
        self.temperature = self.config.get("temperature", 0.3)
        self.max_tokens = self.config.get("max_tokens", 4096)
        self._client = None

    def _get_client(self):
        """获取或创建OpenAI客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                client_kwargs = {"api_key": self.api_key}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url

                self._client = AsyncOpenAI(**client_kwargs)
                logger.info(f"LLMClient initialized: {self.provider}/{self.model}")

            except ImportError:
                logger.error("openai package is required. Install: pip install openai")
                raise

        return self._client

    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> LLMResponse:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            temperature: 采样温度（覆盖默认值）
            max_tokens: 最大token数（覆盖默认值）
            tools: 可用工具定义（function calling）
            tool_choice: 工具选择策略
        """
        client = self._get_client()

        # 转换消息格式
        formatted_messages = []
        for msg in messages:
            formatted_msg = {"role": msg.role, "content": msg.content}
            if msg.name:
                formatted_msg["name"] = msg.name
            formatted_messages.append(formatted_msg)

        # 构建请求参数
        kwargs = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        try:
            response = await client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            # 处理tool_calls
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                # 将tool_calls序列化到content中
                tool_calls_data = []
                for tc in tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    })
                content = json.dumps({
                    "content": content,
                    "tool_calls": tool_calls_data,
                }, ensure_ascii=False)

            logger.debug(f"LLM chat: {usage['total_tokens']} tokens")

            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                raw_response=response,
            )

        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            raise

    async def chat_json(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        发送聊天请求，返回JSON解析后的结果

        自动在system prompt中添加JSON格式要求。
        """
        # 在消息列表开头添加JSON格式要求
        json_system = LLMMessage(
            role="system",
            content="You must respond with valid JSON only. No markdown, no explanation text. "
                    "Ensure the response is a valid JSON object that can be parsed.",
        )

        all_messages = [json_system] + messages

        response = await self.chat(all_messages, temperature, max_tokens)

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning(f"LLM response is not valid JSON, attempting to extract JSON")
            # 尝试从文本中提取JSON
            content = response.content.strip()
            # 找到第一个{和最后一个}
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start:end+1])
                except json.JSONDecodeError:
                    pass
            return {"error": "Failed to parse JSON", "raw": response.content}

    async def decide_platform(
        self,
        campaign_request: Dict[str, Any],
        platform_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        决策：选择最佳投放平台

        将Campaign需求和各平台数据发给LLM，获取决策建议。
        """
        system_prompt = """You are an expert digital advertising strategist with deep knowledge of all major advertising platforms (Google Ads, Meta Ads, TikTok, Amazon DSP, etc.).

Your task is to analyze the campaign requirements and platform data, then recommend the best platforms with detailed reasoning.

Consider:
1. Audience alignment between platform and campaign target
2. Cost efficiency (CPM, CPC trends)
3. Platform strengths for the specific objective
4. Budget fit
5. Creative format support
6. Historical performance patterns

Respond ONLY with a JSON object in this exact format:
{
    "reasoning": "string - detailed analysis of why these platforms were chosen",
    "platforms": [
        {
            "name": "platform_name",
            "score": 0-100,
            "reasoning": "why this platform",
            "budget_allocation_pct": 0-100,
            "confidence": "high|medium|low"
        }
    ],
    "overall_strategy": "string - summary of the recommended approach",
    "risk_factors": ["string - list of potential risks"]
}"""

        user_prompt = f"""Campaign Request:
{json.dumps(campaign_request, ensure_ascii=False, indent=2, default=str)}

Available Platforms Data:
{json.dumps(platform_data, ensure_ascii=False, indent=2, default=str)}

Please analyze and recommend the best platforms for this campaign."""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        return await self.chat_json(messages, temperature=0.3)

    async def analyze_performance(
        self,
        campaign_data: Dict[str, Any],
        platform_reports: Dict[str, List[Dict]],
    ) -> Dict[str, Any]:
        """
        分析：分析Campaign表现并给出优化建议

        将Campaign数据和各平台报表发给LLM，获取分析结果。
        """
        system_prompt = """You are an expert performance marketing analyst. Analyze campaign data and provide actionable optimization recommendations.

Respond ONLY with a JSON object:
{
    "summary": "string - performance summary",
    "platform_analysis": {
        "platform_name": {
            "grade": "A|B|C|D|F",
            "strengths": ["string"],
            "issues": ["string"],
            "recommendations": ["string"]
        }
    },
    "actions": [
        {
            "action": "scale|pause|reduce_budget|increase_budget|adjust_targeting|none",
            "platform": "platform_name",
            "reason": "string",
            "budget_adjustment_pct": -50 to 100
        }
    ],
    "budget_reallocation": {
        "platform_name": percentage
    },
    "confidence": "high|medium|low"
}"""

        user_prompt = f"""Campaign Overview:
{json.dumps(campaign_data, ensure_ascii=False, indent=2, default=str)}

Platform Performance Reports:
{json.dumps(platform_reports, ensure_ascii=False, indent=2, default=str)}

Analyze performance and recommend optimizations."""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        return await self.chat_json(messages, temperature=0.2)

    async def generate_creative_brief(
        self,
        campaign_request: Dict[str, Any],
        platform_scores: List[Dict],
    ) -> Dict[str, Any]:
        """
        生成创意brief
        """
        system_prompt = """You are a creative strategist. Generate platform-specific creative briefs.

Respond with JSON:
{
    "creative_briefs": {
        "platform_name": {
            "headlines": ["string"],
            "descriptions": ["string"],
            "cta_options": ["string"],
            "visual_direction": "string",
            "audience_messaging": "string"
        }
    }
}"""

        user_prompt = f"""Campaign: {json.dumps(campaign_request, ensure_ascii=False)}
Platforms: {json.dumps(platform_scores, ensure_ascii=False)}

Generate creative briefs."""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        return await self.chat_json(messages, temperature=0.7)


# 全局LLM客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client(config: Optional[Dict[str, Any]] = None) -> LLMClient:
    """获取LLM客户端（单例）"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(config)
    return _llm_client
