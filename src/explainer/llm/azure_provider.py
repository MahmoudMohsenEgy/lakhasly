from langchain_openai import AzureChatOpenAI
from explainer.config import Config

class AzureOpenAIProvider:
    def __init__(self, config: Config):
        self._config = config

    def chat_model(self, *, temperature: float | None = None):
        c = self._config
        return AzureChatOpenAI(
            azure_endpoint=c.azure_endpoint,
            azure_deployment=c.azure_deployment,
            api_version=c.azure_api_version,
            temperature=0.3 if temperature is None else temperature,
        )
