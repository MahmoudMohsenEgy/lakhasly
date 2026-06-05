from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

class ScriptedToolModel(GenericFakeChatModel):
    def __init__(self, script):
        super().__init__(messages=iter([]))
        object.__setattr__(self, "_script", script)
        object.__setattr__(self, "_i", 0)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        i = self._i
        object.__setattr__(self, "_i", i + 1)
        step = self._script[min(i, len(self._script) - 1)]
        if step.get("final"):
            msg = AIMessage(content=step["text"])
        else:
            msg = AIMessage(content="", tool_calls=[{
                "name": step["name"], "args": step["args"], "id": f"call_{i}"}])
        return ChatResult(generations=[ChatGeneration(message=msg)])

class ScriptedProvider:
    def __init__(self, model): self._model = model
    def chat_model(self): return self._model
