import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # LLM Provider: "anthropic" or "openai"
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic").lower()

    # Anthropic settings
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    default_model: str = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-6")
    escalation_model: str = os.getenv("ESCALATION_MODEL", "claude-opus-4-6")

    # OpenAI settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_default_model: str = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o")
    openai_escalation_model: str = os.getenv("OPENAI_ESCALATION_MODEL", "gpt-4o")

    enable_model_escalation: bool = os.getenv("ENABLE_MODEL_ESCALATION", "false").lower() == "true"
    max_evaluation_attempts: int = int(os.getenv("MAX_EVALUATION_ATTEMPTS", "2"))
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    results_dir: str = os.getenv("RESULTS_DIR", "results")

    # Arize Tracing
    arize_space_id: str = os.getenv("ARIZE_SPACE_ID", "")
    arize_api_key: str = os.getenv("ARIZE_API_KEY", "")
    arize_project_name: str = os.getenv("ARIZE_PROJECT_NAME", "ats-resume-evaluator")

    # Test mode (used by test_pipeline.py)
    resume_folder: str = os.getenv("RESUME_FOLDER", "resumes")
    jd_text: str = os.getenv("JD_TEXT", "")

    @property
    def arize_enabled(self) -> bool:
        return bool(self.arize_space_id) and bool(self.arize_api_key)

    @property
    def is_anthropic(self) -> bool:
        return self.llm_provider == "anthropic"

    @property
    def is_openai(self) -> bool:
        return self.llm_provider == "openai"

    @property
    def active_api_key(self) -> str:
        if self.is_anthropic:
            return self.anthropic_api_key
        return self.openai_api_key

    @property
    def active_default_model(self) -> str:
        if self.is_anthropic:
            return self.default_model
        return self.openai_default_model

    @property
    def active_escalation_model(self) -> str:
        if self.is_anthropic:
            return self.escalation_model
        return self.openai_escalation_model

    class Config:
        env_file = ".env"


settings = Settings()
