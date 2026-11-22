"""AutoGen agents that execute the research workflow's distinct roles."""
import json
from typing import Awaitable, Callable, Any

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


class ResearchAgent(BaseChatAgent):
    """A bounded specialist; its handler may use the existing LLM and tools."""

    def __init__(self, name: str, description: str, handler: Callable[[dict], Awaitable[Any]]):
        super().__init__(name=name, description=description)
        self.handler = handler

    @property
    def produced_message_types(self):
        return (TextMessage,)

    async def on_messages(self, messages, cancellation_token: CancellationToken):
        payload = json.loads(messages[-1].content)
        result = await self.handler(payload)
        return Response(chat_message=TextMessage(content=json.dumps(result, ensure_ascii=False), source=self.name))

    async def on_reset(self, cancellation_token: CancellationToken):
        pass


async def run_specialist(name: str, description: str, payload: dict, handler):
    agent = ResearchAgent(name, description, handler)
    result = await agent.run(task=json.dumps(payload, ensure_ascii=False))
    return json.loads(result.messages[-1].content)
