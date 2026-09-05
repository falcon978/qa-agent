import os
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError
from orchestrator.config import settings
logger = get_logger(__name__)
load_dotenv()

def get_llm() -> BaseChatModel:
    """
    Instantiates and returns an LLM agnostic Chat Model.
    Uses ChatOpenAI as a universal client for OpenRouter (supporting Gemini, Claude, OpenAI, etc).
    
    Raises:
        LLMExecutionError: If the API keys or required environment variables are missing.
        
    Returns:
        BaseChatModel: A configured ChatOpenAI instance.
    """
    if not settings.llm_api_key:
        logger.error("API Key is missing for the LLM client.")
        raise LLMExecutionError("No valid API key found. Set OPENROUTER_API_KEY.")
    
    try:
        model = ChatOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base,
            model=settings.llm_model_name,
            temperature=settings.llm_temperature,
        )
        logger.info("LLM client successfully instantiated.")
        return model
    except Exception as e:
        logger.error(f"Failed to initialize LLM client: {e}")
        raise LLMExecutionError("Could not initialize the LLM client.") from e
