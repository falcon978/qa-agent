import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from orchestrator.llm import get_llm
from orchestrator.state import AgentState
from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError
from orchestrator.utils import load_prompt
from orchestrator.mcp_client import execute_playwright_commands_via_mcp, reset_browser_via_mcp
from orchestrator.config import settings

logger = get_logger(__name__)

@tool
async def explore_ui(commands: List[Dict[str, Any]]) -> str:
    """
    Executes a sequence of atomic Playwright commands in the browser and returns the resulting DOM context.
    Commands should be a list of dictionaries. Allowed actions are 'goto', 'fill', 'click', 'extract_dom'.
    Example:
    [
        {"action": "goto", "url": "https://www.saucedemo.com/"},
        {"action": "fill", "selector": "#user-name", "value": "standard_user"},
        {"action": "fill", "selector": "#password", "value": "secret_sauce"},
        {"action": "click", "selector": "#login-button"},
        {"action": "extract_dom"}
    ]
    """
    base_url = str(commands[0].get("url")) if commands and commands[0].get("action") == "goto" else "https://www.saucedemo.com/"
    logger.info(f"Executing {len(commands)} Playwright commands via MCP:")
    for i, cmd in enumerate(commands):
        logger.info(f"  [{i+1}] {cmd}")
    return await execute_playwright_commands_via_mcp(base_url, commands)

@tool
async def reset_browser_session() -> str:
    """
    Resets the browser to a completely blank, clean state. 
    Use this if you need to test a different user login, or if the browser gets stuck in an error state.
    """
    logger.info("Executing reset_browser_session via MCP")
    return await reset_browser_via_mcp()

async def execute_planner(state: AgentState) -> Dict[str, Any]:
    """
    Executes the Planner Agent to generate a structured test plan.
    Uses the ReAct pattern to dynamically explore the UI using the explore_ui tool.
    """
    logger.info("Starting Planner Agent execution (ReAct mode).")
    
    try:
        # Guarantee a completely clean browser session before the planner starts
        await reset_browser_via_mcp()
        
        llm = get_llm()
        system_prompt = load_prompt("planner")
        
        # We create the react agent specifically for exploration
        exploration_agent = create_react_agent(llm, tools=[explore_ui, reset_browser_session])  # type: ignore
        
        instruction = f"You are a QA Planner. Your goal is to explore the target URL: {state.url}\\n"
        if state.test_data:
            instruction += f"You have been provided the following test data and credentials: {state.test_data}\\n\\n"
            
        instruction += "CRITICAL RULES:\\n"
        instruction += "1. The browser is STATEFUL. You do not need to restart from `goto` on every tool call unless you want to start fresh.\\n"
        
        if state.test_data:
            instruction += "2. You MUST explore the flows for ALL the different users provided in the test_data (e.g., standard_user, locked_out_user, problem_user). Use the `reset_browser_session` tool to quickly log out and start a fresh session for the next user.\\n"
            instruction += "3. After thoroughly exploring all user flows, write a comprehensive Test Plan in Markdown covering all findings.\\n\\n"
        else:
            instruction += "2. Thoroughly explore the application's key flows. Use the `explore_ui` tool to navigate and interact.\\n"
            instruction += "3. Write a comprehensive Test Plan in Markdown covering all findings.\\n\\n"

        if state.prd_context:
            instruction += f"PRD Context: {state.prd_context}\n"
            
        if getattr(state, 'coverage_gaps', None):
            instruction += "\nCRITICAL FEEDBACK FROM PREVIOUS RUN:\n"
            instruction += "The Meta-Evaluator reviewed your previous test plan and found the following missing coverage gaps. You MUST address these specific scenarios in this new exploration:\n"
            for gap in state.coverage_gaps:
                instruction += f"- [{gap.severity}] {gap.description}\n"
            instruction += "\n"
            
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=instruction)
        ]
        
        logger.info("Invoking ReAct exploration loop...")
        agent_response = await exploration_agent.ainvoke(
            {"messages": messages}, 
            config={"recursion_limit": settings.agent_recursion_limit}
        )
        
        # The final message from the agent should be the test plan
        final_message = agent_response["messages"][-1].content
        
        # Save the test plan to disk so the user can inspect it
        try:
            os.makedirs("test-results", exist_ok=True)
            with open("test-results/planner_test_plan.md", "w", encoding="utf-8") as f:
                f.write(final_message)
            logger.info("Saved test plan to test-results/planner_test_plan.md")
        except Exception as e:
            logger.warning(f"Could not save test plan to disk: {e}")
            
        logger.info("Planner Agent successfully generated test plan.")
        
        # Increment planner attempts to prevent infinite evaluation loops
        return {
            "test_plan": final_message,
            "planner_attempts": state.planner_attempts + 1,
            "dom_context": "DOM extracted dynamically during exploration." # Placeholder since it's dynamic
        }
        
    except Exception as e:
        logger.error(f"Planner failed to generate a plan: {e}")
        raise LLMExecutionError("Planner agent failed") from e
