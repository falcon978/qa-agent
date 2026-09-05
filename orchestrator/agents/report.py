import yaml
import os
from pathlib import Path
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.llm import get_llm
from orchestrator.state import AgentState
from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError
from orchestrator.utils import load_prompt

logger = get_logger(__name__)

async def execute_report(state: AgentState) -> Dict[str, Any]:
    """
    Executes the Report Agent to summarize the test plan, files generated, and execution results.
    """
    logger.info("Starting Report Agent execution.")
    
    try:
        llm = get_llm()
        system_prompt = load_prompt("report")
        
        # Build user context
        generated_files = [s.filename for s in state.test_scripts]
        
        failures_summary = "No failures detected! All tests passed."
        if state.test_failures:
            failures_summary = "Failures:\n"
            for f in state.test_failures:
                failures_summary += f"- {f.filename}: Script Defect? {f.is_script_defect}. Action Taken: {f.healer_action_taken}\n"
                
        user_content = f"Test Plan:\n{state.test_plan}\n\n"
        user_content += f"Generated Test Files:\n{', '.join(generated_files)}\n\n"
        user_content += f"Execution Summary:\n{failures_summary}\n\n"
        
        if state.coverage_gaps:
            user_content += "Remaining Coverage Gaps (Untested Flow Risk):\n"
            for gap in state.coverage_gaps:
                user_content += f"- [{gap.severity}] {gap.description}\n"
        else:
            user_content += "Remaining Coverage Gaps (Untested Flow Risk): None detected.\n"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        response = await llm.ainvoke(messages)
        final_report = str(response.content).strip()
        
        # Save report to disk
        try:
            os.makedirs("test-results", exist_ok=True)
            with open("test-results/final_report.md", "w", encoding="utf-8") as f:
                f.write(final_report)
            logger.info("Saved final report to test-results/final_report.md")
        except Exception as e:
            logger.warning(f"Could not save final report to disk: {e}")
            
        logger.info("Report execution completed.")
        return {
            "final_report": final_report
        }
        
    except Exception as e:
        logger.error(f"Report failed: {e}")
        raise LLMExecutionError("Report agent failed") from e
