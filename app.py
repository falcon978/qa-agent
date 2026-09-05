import streamlit as st
import asyncio
import json
import traceback

from run import run_orchestration

st.set_page_config(page_title="Aivar QA Orchestrator", layout="wide", page_icon="🤖")

st.title("🤖 Aivar Autonomous Test Orchestrator")
st.markdown("Automatically explore, plan, and generate robust Playwright tests for any web application.")

# Default test data for SauceDemo
DEFAULT_TEST_DATA = {
    "users": {
        "standard_user": {"username": "standard_user", "password": "secret_sauce"},
        "locked_out_user": {"username": "locked_out_user", "password": "secret_sauce"},
        "problem_user": {"username": "problem_user", "password": "secret_sauce"}
    }
}

with st.sidebar:
    st.header("⚙️ Configuration")
    target_url = st.text_input("Target URL", value="https://www.saucedemo.com/")
    
    prd_context = st.text_area(
        "PRD Context (Optional)", 
        value="", 
        help="Paste Product Requirements Document context here to guide the exploration."
    )
    
    test_data_json = st.text_area(
        "Test Data (JSON)",
        value=json.dumps(DEFAULT_TEST_DATA, indent=4),
        height=300,
        help="JSON blob containing users, passwords, and other test data variables."
    )

    run_btn = st.button("🚀 Run Autonomous QA", type="primary", use_container_width=True)

if run_btn:
    try:
        test_data = json.loads(test_data_json)
    except json.JSONDecodeError:
        st.error("Invalid JSON format in Test Data.")
        st.stop()

    if not target_url:
        st.error("Target URL is required.")
        st.stop()

    st.info("Starting Orchestrator pipeline. This may take a few minutes...")
    
    with st.status("Executing QA Pipeline...", expanded=True) as status:
        st.write("Initializing LangGraph and starting Playwright MCP Server...")
        
        try:
            # We must use asyncio.run to execute the async backend logic
            final_state = asyncio.run(run_orchestration(target_url, prd_context, test_data))
            status.update(label="Orchestration Complete!", state="complete", expanded=False)
            
            # --- Render Results ---
            st.success("Pipeline Executed Successfully!")
            
            import os
            def read_report(filename):
                path = f"test-results/{filename}"
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                return "Report not generated."
            
            tabs = st.tabs([
                "Final Report", 
                "Planner Test Plan", 
                "Generated Test Plan", 
                "Healer Report", 
                "Scripts", 
                "Coverage Gaps"
            ])
            
            with tabs[0]:
                with st.container(height=700):
                    st.markdown(read_report("final_report.md"))
                
            with tabs[1]:
                with st.container(height=700):
                    st.markdown(read_report("planner_test_plan.md"))
                
            with tabs[2]:
                with st.container(height=700):
                    st.markdown(read_report("generated_test_plan.md"))
                
            with tabs[3]:
                with st.container(height=700):
                    st.markdown(read_report("healer_report.md"))
                
            with tabs[4]:
                scripts = final_state.get("test_scripts", [])
                if not scripts:
                    st.write("No scripts generated.")
                else:
                    for script in scripts:
                        st.subheader(script.filename)
                        st.code(script.code, language="typescript")
                        
            with tabs[3]:
                failures = final_state.get("test_failures", [])
                if not failures:
                    st.success("No execution failures! All tests passed.")
                else:
                    for failure in failures:
                        st.error(f"**File:** {failure.filename}")
                        st.code(failure.error_message, language="bash")
                        if failure.healer_action_taken:
                            st.info(f"**Healer Action:** {failure.healer_action_taken}")
                            
            with tabs[5]:
                gaps = final_state.get("coverage_gaps", [])
                if not gaps:
                    st.success("No coverage gaps detected.")
                else:
                    for gap in gaps:
                        color = "red" if gap.severity == "High" else "orange" if gap.severity == "Medium" else "blue"
                        st.markdown(f"- :{color}[**{gap.severity}**]: {gap.description}")

        except Exception as e:
            status.update(label="Pipeline Failed", state="error")
            st.error(f"An error occurred during execution: {str(e)}")
            st.code(traceback.format_exc(), language="python")
