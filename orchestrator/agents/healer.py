import os
import yaml
import re
from pathlib import Path
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.llm import get_llm
from orchestrator.state import AgentState, TestScript, TestFailure
from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError
from orchestrator.utils import load_prompt

logger = get_logger(__name__)

async def execute_healer(state: AgentState) -> Dict[str, Any]:
    """
    Executes the Healer Agent to fix test scripts that failed during execution.
    """
    logger.info("Starting Healer execution.")
    
    if not state.test_failures:
        logger.info("No failures to heal.")
        return {"healer_attempts": state.healer_attempts}
        
    try:
        llm = get_llm()
        system_prompt = load_prompt("healer")
        system_prompt += "\nOutput your response starting with 'DEFECT_TYPE: SCRIPT' or 'DEFECT_TYPE: APP'. If SCRIPT, provide the fixed code block."
        
        for failure in state.test_failures:
            # Find corresponding script
            script_to_heal = next((s for s in state.test_scripts if s.filename == failure.filename), None)
            
            if not script_to_heal:
                logger.warning(f"Could not find source script for {failure.filename}")
                continue
                
            user_content = f"Failed Script ({failure.filename}):\n{script_to_heal.code}\n\nError Trace:\n{failure.error_message}\n"
                
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content)
            ]
            
            response = await llm.ainvoke(messages)
            content = str(response.content).strip()
            
            is_script_defect = "DEFECT_TYPE: SCRIPT" in content
            failure.is_script_defect = is_script_defect
            
            if is_script_defect:
                code_match = re.search(r'```(?:typescript|ts)?\n(.*?)```', content, re.DOTALL)
                if code_match:
                    script_to_heal.code = code_match.group(1).strip()
                    failure.healer_action_taken = f"Modified test script {failure.filename} based on error trace."
                    logger.info(f"Healed script {script_to_heal.filename}.")
                else:
                    failure.healer_action_taken = "Identified as script defect but could not parse fixed code."
                    logger.warning(f"Could not parse fixed code from healer response for {failure.filename}.")
            else:
                failure.healer_action_taken = "Identified as a genuine application bug."
                logger.info(f"Healer classified failure in {failure.filename} as an application bug.")
            
        # Save healer report
        try:
            os.makedirs("test-results", exist_ok=True)
            healer_report = f"# Healer Report (Attempt {state.healer_attempts + 1})\n\n"
            for fail in state.test_failures:
                healer_report += f"### File: `{fail.filename}`\n"
                healer_report += f"- **Defect Classification**: {'Script Defect' if fail.is_script_defect else 'Genuine App Defect'}\n"
                healer_report += f"- **Healer Action Taken**: {fail.healer_action_taken}\n"
                healer_report += f"- **Error Trace**:\n```\n{fail.error_message}\n```\n\n"
            
            with open("test-results/healer_report.md", "w", encoding="utf-8") as f:
                f.write(healer_report)
            logger.info("Saved healer report to test-results/healer_report.md")
        except Exception as e:
            logger.warning(f"Could not save healer report: {e}")
            
        return {
            "test_scripts": state.test_scripts,
            "test_failures": state.test_failures,
            "healer_attempts": state.healer_attempts + 1
        }
        
    except Exception as e:
        logger.error(f"Healer failed: {e}")
        raise LLMExecutionError("Healer agent failed") from e
