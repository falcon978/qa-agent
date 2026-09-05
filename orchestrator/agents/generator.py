import os
import yaml
import re
from pathlib import Path
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.llm import get_llm
from orchestrator.state import AgentState, TestScript
from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError
from orchestrator.utils import load_prompt
from orchestrator.config import settings
from orchestrator.mcp_client import reset_browser_via_mcp
from langgraph.prebuilt import create_react_agent
from orchestrator.agents.planner import explore_ui, reset_browser_session

logger = get_logger(__name__)

async def execute_generator(state: AgentState) -> Dict[str, Any]:
    """
    Executes the Generator Agent to convert the test plan into Playwright test scripts.
    """
    logger.info("Starting Generator execution.")
    
    if not state.test_plan:
        logger.warning("No test plan found to generate scripts for.")
        return {"test_scripts": []}
        
    try:
        # Guarantee a completely clean browser session before the generator starts
        await reset_browser_via_mcp()
        
        llm = get_llm()
        system_prompt = load_prompt("generator")
        system_prompt += "\nPlease provide the filename on the first line (e.g., # filename: app.spec.ts), followed by the code block."
        
        # We create a ReAct agent equipped with the explore_ui tool
        generator_agent = create_react_agent(llm, tools=[explore_ui, reset_browser_session])  # type: ignore
        
        user_content = f"Target URL: {state.url}\nTest Plan:\n{state.test_plan}\n"
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        logger.info("Invoking ReAct generation loop for live selector validation...")
        response = await generator_agent.ainvoke(
            {"messages": messages}, 
            config={"recursion_limit": settings.agent_recursion_limit}
        )
        
        content = str(response["messages"][-1].content).strip()
        
        test_scripts = []
        # Find all occurrences of "# filename: <name>" followed by a code block
        pattern = r'# filename:\s*(\S+).*?```(?:typescript|ts)?\n(.*?)```'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            filename = match.group(1)
            code = match.group(2).strip()
            test_scripts.append(TestScript(filename=filename, code=code))
            logger.info(f"Generated script: {filename}")
            
        if not test_scripts:
            # Fallback if the LLM didn't format correctly
            logger.warning("Could not extract multiple files. Falling back to single file.")
            code = content
            code_match = re.search(r'```(?:typescript|ts)?\n(.*?)```', content, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
            test_scripts.append(TestScript(filename="saucedemo.spec.ts", code=code))
        
        # Save mapping report
        try:
            os.makedirs("test-results", exist_ok=True)
            mapping_report = "# Generated Test Plan Mapping\n\nThe following executable test scripts were generated based on the Planner's test plan:\n\n"
            for ts in test_scripts:
                mapping_report += f"### `{ts.filename}`\n"
                mapping_report += f"**Purpose**: Translates the corresponding section of the test plan into Playwright assertions.\n\n"
            
            with open("test-results/generated_test_plan.md", "w", encoding="utf-8") as f:
                f.write(mapping_report)
        except Exception as e:
            logger.warning(f"Could not save generated test plan: {e}")
            
        logger.info(f"Generator execution completed. Generated {len(test_scripts)} file(s).")
        return {
            "test_scripts": test_scripts
        }
        
    except Exception as e:
        logger.error(f"Generator failed: {e}")
        raise LLMExecutionError("Generator agent failed") from e
