import asyncio
import json
from orchestrator.graph import app
from orchestrator.state import AgentState

async def run_orchestration(target_url: str, prd_context: str, test_data: dict) -> AgentState:
    """
    Executes the Aivar Autonomous Test Orchestrator pipeline.
    This function is decoupled from the CLI so it can be called by UI frontends (like Streamlit).
    """
    initial_state = AgentState(
        url=target_url,
        prd_context=prd_context,
        test_data=test_data
    )
    
    return await app.ainvoke(initial_state)

import argparse

async def main():
    parser = argparse.ArgumentParser(description="Aivar Autonomous Test Orchestrator CLI")
    parser.add_argument("--url", type=str, default="https://www.saucedemo.com/", help="Target URL to explore")
    parser.add_argument("--prd", type=str, default="", help="Optional PRD Context")
    parser.add_argument("--test-data", type=str, default="", help="Optional JSON string containing test data")
    args = parser.parse_args()

    print("🚀 Starting Aivar Autonomous Test Orchestrator...\n")
    print(f"🔗 Target URL: {args.url}")
    
    if args.test_data:
        try:
            test_data = json.loads(args.test_data)
            print("📦 Custom Test Data Loaded.\n")
        except json.JSONDecodeError:
            print("❌ Invalid JSON format in --test-data argument. Exiting.")
            return
    else:
        print("📦 Using default SauceDemo Test Data.\n")
        test_data = {
            "users": {
                "standard_user": {"username": "standard_user", "password": "secret_sauce"},
                "locked_out_user": {"username": "locked_out_user", "password": "secret_sauce"},
                "problem_user": {"username": "problem_user", "password": "secret_sauce"}
            }
        }
    
    if args.prd:
        print(f"📄 PRD Context Loaded: {args.prd}\n")
    else:
        print("📄 No PRD Context Provided.\n")

    print("🧠 Invoking LangGraph workflow (Planner -> Meta-Evaluator -> Generator -> Executor -> Healer/Report)...\n")
    
    # Run the graph
    try:
        final_state = await run_orchestration(args.url, args.prd, test_data)
    except Exception as e:
        print(f"❌ Orchestrator failed with error: {e}")
        return

    print("\n" + "="*50)
    print("✅ ORCHESTRATION COMPLETE")
    print("="*50 + "\n")
    
    report = final_state.get("final_report", "No report generated.")
    print(report)
    print("\n" + "="*50)
    
    print("📝 1. TEST PLAN (Saved to test-results/planner_test_plan.md):")
    test_plan_content = final_state.get("test_plan", "No test plan generated.")
    # The agent already saves it, but we can print it here
    print(test_plan_content)
    
    print("\n🔍 2. COVERAGE GAPS:")
    gaps = final_state.get("coverage_gaps", [])
    if not gaps:
        print("None detected.")
    else:
        for gap in gaps:
            print(f" - [{gap.severity}] {gap.description}")
            
    print("\n💻 3. GENERATED SCRIPTS:")
    scripts = final_state.get("test_scripts", [])
    if not scripts:
        print("No scripts generated.")
    else:
        for script in scripts:
            print(f"\n--- {script.filename} ---")
            print(script.code[:200] + "\n... (truncated for display)")

    print("\n🚨 4. EXECUTION FAILURES (After Healing):")
    failures = final_state.get("test_failures", [])
    if not failures:
        print("No failures! All tests passed.")
    else:
        for failure in failures:
            print(f" - [File: {failure.filename}] Error: {failure.error_message}")
            
    print("\n📊 5. FINAL REPORT:")
    print(final_state.get("final_report", "No report generated."))

if __name__ == "__main__":
    asyncio.run(main())
