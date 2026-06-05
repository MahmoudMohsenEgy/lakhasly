import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    azure_endpoint: str
    azure_deployment: str
    azure_api_version: str = "2024-10-21"
    output_dir: str = "output"
    font_family: str = "Cairo"
    questions_per_section: int = 4
    step_budget: int = 40
    search_backend: str = "tavily"  # "tavily" | "duckduckgo"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            output_dir=os.getenv("OUTPUT_DIR", "output"),
            font_family=os.getenv("FONT_FAMILY", "Cairo"),
            questions_per_section=int(os.getenv("QUESTIONS_PER_SECTION", "4")),
            step_budget=int(os.getenv("STEP_BUDGET", "40")),
            search_backend=os.getenv("SEARCH_BACKEND", "tavily"),
        )
