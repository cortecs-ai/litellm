"""
Translates from OpenAI's `/v1/chat/completions` to DashScope's `/v1/chat/completions`
"""

from typing import Any, Coroutine, Dict, List, Literal, Optional, Tuple, Union, overload

from litellm.constants import (
    DEFAULT_REASONING_EFFORT_HIGH_THINKING_BUDGET,
    DEFAULT_REASONING_EFFORT_LOW_THINKING_BUDGET,
    DEFAULT_REASONING_EFFORT_MEDIUM_THINKING_BUDGET,
)
from litellm.secret_managers.main import get_secret_str
from litellm.types.llms.openai import AllMessageValues, ChatCompletionToolParam

from ...openai.chat.gpt_transformation import OpenAIGPTConfig


class DashScopeChatConfig(OpenAIGPTConfig):
    def remove_cache_control_flag_from_messages_and_tools(
        self,
        model: str,
        messages: List[AllMessageValues],
        tools: Optional[List[ChatCompletionToolParam]] = None,
    ) -> Tuple[List[AllMessageValues], Optional[List[ChatCompletionToolParam]]]:
        """
        Override to preserve cache_control for DashScope.
        DashScope supports cache_control - don't strip it.
        """
        return messages, tools

    def get_supported_openai_params(self, model: str) -> list:
        params = super().get_supported_openai_params(model)
        if "reasoning_effort" not in params:
            params.append("reasoning_effort")
        # Also accept the Anthropic-style 'thinking' param for custom budget
        if "thinking" not in params:
            params.append("thinking")
        return params

    @staticmethod
    def _map_reasoning_effort_to_dashscope(
        reasoning_effort: str,
    ) -> Dict[str, Any]:
        """
        Map reasoning_effort to DashScope's enable_thinking + thinking_budget.

        DashScope Qwen models use:
        - enable_thinking: bool  (enables/disables reasoning)
        - thinking_budget: int   (optional, limits reasoning tokens)

        Returns:
            Dict with enable_thinking and optionally thinking_budget.
        """
        if reasoning_effort in ("none", "disable"):
            return {"enable_thinking": False}
        elif reasoning_effort == "low":
            return {
                "enable_thinking": True,
                "thinking_budget": DEFAULT_REASONING_EFFORT_LOW_THINKING_BUDGET,
            }
        elif reasoning_effort == "medium":
            return {
                "enable_thinking": True,
                "thinking_budget": DEFAULT_REASONING_EFFORT_MEDIUM_THINKING_BUDGET,
            }
        elif reasoning_effort in ("high", "max"):
            return {
                "enable_thinking": True,
                "thinking_budget": DEFAULT_REASONING_EFFORT_HIGH_THINKING_BUDGET,
            }
        else:
            # Default: just enable thinking without a specific budget
            return {"enable_thinking": True}

    def map_openai_params(
        self,
        non_default_params: dict,
        optional_params: dict,
        model: str,
        drop_params: bool,
    ) -> dict:
        """
        Translate reasoning_effort and thinking params to DashScope's
        enable_thinking/thinking_budget via extra_body.
        """
        # Handle reasoning_effort -> enable_thinking + thinking_budget
        reasoning_effort = non_default_params.pop("reasoning_effort", None)
        thinking_param = non_default_params.pop("thinking", None)

        dashscope_thinking: Optional[Dict[str, Any]] = None

        if reasoning_effort is not None:
            effort_value: Optional[str] = None
            if isinstance(reasoning_effort, str):
                effort_value = reasoning_effort
            elif isinstance(reasoning_effort, dict):
                effort_value = reasoning_effort.get("effort")

            if effort_value is not None:
                dashscope_thinking = self._map_reasoning_effort_to_dashscope(
                    effort_value
                )
        elif thinking_param is not None and isinstance(thinking_param, dict):
            if thinking_param.get("type") == "enabled":
                dashscope_thinking = {"enable_thinking": True}
                budget = thinking_param.get("budget_tokens")
                if budget is not None and isinstance(budget, int):
                    dashscope_thinking["thinking_budget"] = budget
            else:
                dashscope_thinking = {"enable_thinking": False}

        # Merge into extra_body
        if dashscope_thinking is not None:
            extra_body = optional_params.get("extra_body", {})
            if not isinstance(extra_body, dict):
                extra_body = {}
            extra_body.update(dashscope_thinking)
            optional_params["extra_body"] = extra_body

        # Delegate remaining params to parent
        return super().map_openai_params(
            non_default_params=non_default_params,
            optional_params=optional_params,
            model=model,
            drop_params=drop_params,
        )

    @overload
    def _transform_messages(
        self, messages: List[AllMessageValues], model: str, is_async: Literal[True]
    ) -> Coroutine[Any, Any, List[AllMessageValues]]: ...

    @overload
    def _transform_messages(
        self,
        messages: List[AllMessageValues],
        model: str,
        is_async: Literal[False] = False,
    ) -> List[AllMessageValues]: ...

    def _transform_messages(
        self, messages: List[AllMessageValues], model: str, is_async: bool = False
    ) -> Union[List[AllMessageValues], Coroutine[Any, Any, List[AllMessageValues]]]:
        if is_async:
            return super()._transform_messages(messages=messages, model=model, is_async=True)
        else:
            return super()._transform_messages(messages=messages, model=model, is_async=False)

    def _get_openai_compatible_provider_info(
        self, api_base: Optional[str], api_key: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        api_base = (
            api_base or get_secret_str("DASHSCOPE_API_BASE") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )  # type: ignore
        dynamic_api_key = api_key or get_secret_str("DASHSCOPE_API_KEY")
        return api_base, dynamic_api_key

    def get_complete_url(
        self,
        api_base: Optional[str],
        api_key: Optional[str],
        model: str,
        optional_params: dict,
        litellm_params: dict,
        stream: Optional[bool] = None,
    ) -> str:
        """
        If api_base is not provided, use the default DashScope /chat/completions endpoint.
        """
        if not api_base:
            api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        if not api_base.endswith("/chat/completions"):
            api_base = f"{api_base}/chat/completions"

        return api_base
