# Aivar Autonomous Test Orchestrator

**Bessemer Tech Catalyst Hackathon (AI/ML Track)**

An end-to-end, autonomous test orchestration agent that takes a web application URL and drives the full testing lifecycle—planning, generation, execution, and healing—without human intervention.

## 🌟 The Vision

Software testing consumes massive engineering time. The core bottleneck is not execution, but **decision-making**. 
This project introduces a **LangGraph-based Orchestrator** that intelligently coordinates a pipeline of specialized AI agents. It evaluates coverage quality, navigates stateful browser sessions in real-time, generates Playwright scripts, and self-heals broken locators, delivering a fully functional test suite from nothing but a URL.

---

## 🏗 Architecture & Agent Pipeline

The system is built on an event-driven **LangGraph** state machine.

1. **Planner Agent (ReAct)**: Uses Model Context Protocol (MCP) to live-explore the target URL in a persistent, stateful browser. It clicks, types, and reads the DOM dynamically to build a comprehensive Test Plan in Markdown.
2. **Meta-Evaluator**: Analyzes the generated test plan against optional PRD context to identify coverage gaps (e.g., missing error states, edge cases). If high-severity gaps exist, it forces the Planner to re-explore.
3. **Generator Agent (ReAct)**: Converts the test plan into executable Playwright TypeScript code. Crucially, it performs **Live Selector Validation** by querying the live DOM via MCP to guarantee that every locator (ID, role, text) actually exists before writing the code.
4. **Executor Node**: Seamlessly triggers the Node.js MCP server to run the generated Playwright test suite and captures the JSON error reports.
5. **Healer Agent**: If tests fail due to UI changes or flakiness, the Healer analyzes the Playwright trace, dynamically re-explores the DOM, and patches the broken script.
6. **Report Node**: Synthesizes the execution data into a final QA report containing coverage metrics and failure classifications.

### Stateful Browser MCP
At the core of the agents' capability is the **Playwright MCP Server**. Unlike traditional stateless LLM tools, our Node.js MCP server maintains a global Chromium browser session. This allows the ReAct agents to click through the application naturally, one step at a time, exactly like a human tester.

---

## 🛠 Tech Stack

* **Orchestrator**: Python, LangGraph, LangChain
* **LLM**: Anthropic / OpenAI (Configurable via `orchestrator.llm`)
* **Browser Automation**: Playwright
* **Tooling Protocol**: Model Context Protocol (MCP) via stdio (TypeScript)

---

## 🚀 Setup Instructions

### 1. Python Environment
Ensure you have Python 3.11+ installed.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Node & Playwright MCP
The MCP server executes the browser automation locally.
```bash
cd playwright-mcp
npm install
npm run build
```

### 3. Environment Variables
Copy the `.env.example` file and configure your LLM API keys:
```bash
cp .env.example .env
```
*(Add your `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to the `.env` file).*

---

## 🎮 How to Run

Simply execute the main orchestrator script. By default, it runs against [SauceDemo](https://www.saucedemo.com/).

```bash
python run.py
```

### What happens when you run it?
1. The orchestrator boots up a background Playwright MCP server.
2. You will see the Planner Agent navigating the browser live, extracting DOM, and writing the `test_plan.md`.
3. The Meta-Evaluator checks the plan.
4. The Generator produces `test-result/run_<timestamp>/saucedemo.spec.ts`.
5. The Executor runs the test suite natively via `npx playwright test`.
6. Any failures are routed to the Healer.
7. A final report is printed to the console!

---

## 📂 Project Structure

```text
├── run.py                       # Main execution entrypoint
├── orchestrator/                # LangGraph AI Pipeline
│   ├── graph.py                 # Core state machine logic
│   ├── mcp_client.py            # Singleton connection to Node MCP
│   ├── agents/                  # Planner, Generator, Healer logic
│   └── prompts/                 # System instructions (YAML)
├── playwright-mcp/              # TypeScript MCP Server
│   ├── src/index.ts             # Stateful browser tools
│   ├── package.json
│   └── tsconfig.json
└── test-results/                # Generated scripts and Playwright traces
```
