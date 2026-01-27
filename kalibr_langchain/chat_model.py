"""
Kalibr LangChain Chat Model - Routes requests through Kalibr.
"""

from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class KalibrChatModel(BaseChatModel):
    """
    LangChain chat model that routes through Kalibr.

    Example:
        from kalibr import Router

        router = Router(goal="summarize", paths=["gpt-4o", "claude-3"])
        llm = router.as_langchain()

        chain = prompt | llm | parser
        result = chain.invoke({"text": "..."})
    """

    router: Any  # Kalibr Router instance

    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self) -> str:
        return "kalibr"

    @property
    def _identifying_params(self) -> dict:
        return {"goal": self.router.goal}

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using Kalibr routing."""

        # Convert LangChain messages to OpenAI format
        openai_messages = []
        for m in messages:
            role = self._get_role(m)
            openai_messages.append({"role": role, "content": m.content})

        # Add stop sequences if provided
        if stop:
            kwargs["stop"] = stop

        # Call router
        response = self.router.completion(messages=openai_messages, **kwargs)

        # Convert response to LangChain format
        content = response.choices[0].message.content or ""

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=content),
                    generation_info={
                        "model": response.model,
                        "finish_reason": response.choices[0].finish_reason,
                    },
                )
            ],
            llm_output={
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if hasattr(response, "usage") else {},
            },
        )

    def _get_role(self, message: BaseMessage) -> str:
        """Convert LangChain message type to OpenAI role."""
        from langchain_core.messages import (
            HumanMessage,
            AIMessage,
            SystemMessage,
            FunctionMessage,
            ToolMessage,
        )

        if isinstance(message, HumanMessage):
            return "user"
        elif isinstance(message, AIMessage):
            return "assistant"
        elif isinstance(message, SystemMessage):
            return "system"
        elif isinstance(message, (FunctionMessage, ToolMessage)):
            return "function"
        else:
            return "user"
