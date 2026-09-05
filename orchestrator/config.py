import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Load the .env file so that LangChain/LangSmith automatically picks up 
# LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, and LANGCHAIN_PROJECT
load_dotenv()

class Settings(BaseSettings):
    """
    Centralized configuration settings for the Orchestrator.
    These can be overridden by environment variables or a .env file.
    """
    # LLM Settings
    llm_api_base: str = Field(default="https://openrouter.ai/api/v1", alias="LLM_API_BASE")
    llm_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    llm_model_name: str = Field(default="google/gemini-1.5-pro", alias="LLM_MODEL_NAME")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    
    # Orchestrator Settings
    max_healer_retries: int = Field(default=3, alias="MAX_HEALER_RETRIES")
    max_planner_retries: int = Field(default=3, alias="MAX_PLANNER_RETRIES")
    agent_recursion_limit: int = Field(default=50, alias="AGENT_RECURSION_LIMIT")
    
    # MCP Settings
    mcp_command: str = Field(default="node", alias="MCP_COMMAND")
    # Using a string to simplify .env overrides, then we'll split it in the client
    mcp_args: str = Field(default="playwright-mcp/build/index.js", alias="MCP_ARGS")
    
    # LangSmith Observability Settings
    langchain_tracing_v2: str = Field(default="true", alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="QA-Agent", alias="LANGCHAIN_PROJECT")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
