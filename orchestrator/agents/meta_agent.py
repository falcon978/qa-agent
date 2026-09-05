import yaml
import json
from pathlib import Path
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.llm import get_llm
from orchestrator.state import AgentState, CoverageGap
from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError, DataValidationError
from orchestrator.utils import load_prompt

logger = get_logger(__name__)

async def execute_meta_evaluator(state: AgentState) -> Dict[str, Any]:
    """
    Executes the Meta Evaluator to review the test plan for coverage gaps.
    """
    logger.info("Starting Meta Evaluator execution.")
    
    if not state.test_plan:
        logger.warning("No test plan found to evaluate.")
        return {"coverage_gaps": []}
        
    try:
        llm = get_llm()
        # We can use structured output if the LLM supports it, but for generic LLM 
        # we'll ask it to return JSON and parse it.
        system_prompt = load_prompt("meta_evaluator")
        system_prompt += "\nOutput your response strictly as a JSON array of objects with keys 'description' and 'severity' (High/Medium/Low)."
        
        user_content = f"URL: {state.url}\n"
        if state.prd_context:
            user_content += f"PRD Context: {state.prd_context}\n"
        user_content += f"Test Plan:\n{state.test_plan}\n"
            
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        response = await llm.ainvoke(messages)
        
        # Naive JSON parsing (in production, use structured output or a robust parser)
        content = str(response.content).strip()
        if content.startswith("```json"):
            content = content[7:-3]
        
        gaps_data = json.loads(content)
        coverage_gaps = [CoverageGap(**gap) for gap in gaps_data]
        
        logger.info(f"Meta Evaluator completed. Found {len(coverage_gaps)} gaps.")
        return {"coverage_gaps": coverage_gaps}
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Meta Evaluator JSON output: {e}")
        # Fail gracefully by not blocking the pipeline if parsing fails
        return {"coverage_gaps": []}
    except Exception as e:
        logger.error(f"Meta Evaluator failed: {e}")
        raise LLMExecutionError("Meta Evaluator agent failed") from e
