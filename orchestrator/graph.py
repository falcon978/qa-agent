import asyncio
from langgraph.graph import StateGraph, END
from typing import Dict, Any

from orchestrator.state import AgentState
from orchestrator.logger import get_logger
from orchestrator.exceptions import LLMExecutionError

from orchestrator.agents import execute_planner, execute_meta_evaluator, execute_generator, execute_healer, execute_report
from orchestrator.mcp_client import run_mcp_tests
from orchestrator.state import TestFailure
from orchestrator.config import settings
import json
import time

logger = get_logger(__name__)

# Planner, Meta Evaluator, Generator, and Healer are now imported from the agents module.

async def executor_node(state: AgentState) -> Dict[str, Any]:
    """Sends the test scripts to the MCP server for execution and collects failures."""
    logger.info("Executing Executor Node (MCP Runner).")
    try:
        if not state.test_scripts:
            logger.warning("No test scripts to run.")
            return {"test_failures": []}
            
        scripts_payload = [{"filename": ts.filename, "code": ts.code} for ts in state.test_scripts]
        
        # Generate a run ID so we can tell the user exactly where the files are
        run_id = f"run_{int(time.time())}"
        logger.info(f"Saving and executing test scripts in: playwright-mcp/test-result/{run_id}/")
        
        # Run via MCP
        mcp_output = await run_mcp_tests(scripts_payload, run_id=run_id)
        
        # Simple parsing for the hackathon: Check if the output has Playwright failures
        failures = []
        try:
            report = json.loads(mcp_output)
            # If the report contains errors (Playwright JSON structure varies, but we check for any non-empty errors array)
            if "errors" in report and report["errors"]:
                failures.append(TestFailure(
                    filename=state.test_scripts[0].filename, # Simplification
                    error_message=json.dumps(report["errors"]),
                    is_script_defect=False
                ))
        except json.JSONDecodeError:
            # If it's not JSON, it might be a raw error string from Playwright crashing
            if "Error:" in mcp_output or "failed" in mcp_output.lower():
                failures.append(TestFailure(
                    filename=state.test_scripts[0].filename,
                    error_message=mcp_output,
                    is_script_defect=False
                ))
                
        return {"test_failures": failures}
    except Exception as e:
        logger.error(f"Executor Node encountered an error: {e}")
        raise LLMExecutionError("Executor execution failed") from e



def route_after_evaluation(state: AgentState) -> str:
    """Decides whether to replan or proceed to generation based on coverage gaps."""
    logger.info("Routing after evaluation.")
    
    # Break infinite loops if the planner has exhausted retries
    if state.planner_attempts >= settings.max_planner_retries:
        logger.warning(f"Planner hit max retries ({settings.max_planner_retries}). Forcing route to Generator despite gaps.")
        return "generator"

    if state.coverage_gaps and any(gap.severity == "High" for gap in state.coverage_gaps):
        logger.info("High severity coverage gaps found, routing to Planner.")
        return "planner"
    return "generator"

def route_after_execution(state: AgentState) -> str:
    """Decides if the system needs healing or can proceed to final report generation."""
    logger.info("Routing after execution.")
    failures = state.test_failures
    if failures and state.healer_attempts < settings.max_healer_retries:
        logger.info("Failures detected and healer attempts remaining, routing to Healer.")
        return "healer"
    if failures:
        logger.warning("Max healer attempts reached. Proceeding to report with failures.")
    return "report"

# Build the Graph
workflow = StateGraph(AgentState)

# Wire up the real agent functions
workflow.add_node("planner", execute_planner)
workflow.add_node("meta_evaluator", execute_meta_evaluator)
workflow.add_node("generator", execute_generator)
workflow.add_node("healer", execute_healer)

# Wire up the remaining nodes
workflow.add_node("executor", executor_node)
workflow.add_node("report", execute_report)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "meta_evaluator")

workflow.add_conditional_edges(
    "meta_evaluator",
    route_after_evaluation,
    {
        "generator": "generator",
        "planner": "planner"
    }
)

workflow.add_edge("generator", "executor")

workflow.add_conditional_edges(
    "executor",
    route_after_execution,
    {
        "healer": "healer",
        "report": "report"
    }
)

workflow.add_edge("healer", "executor")
workflow.add_edge("report", END)

app = workflow.compile()
