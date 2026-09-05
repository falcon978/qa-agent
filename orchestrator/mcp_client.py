import asyncio
from typing import Dict, Any, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from contextlib import AsyncExitStack

from orchestrator.logger import get_logger
from orchestrator.exceptions import MCPConnectionError
from orchestrator.config import settings

logger = get_logger(__name__)

_mcp_stack = None
_mcp_session = None
_mcp_lock = asyncio.Lock()

async def get_mcp_session() -> ClientSession:
    global _mcp_stack, _mcp_session
    if _mcp_session is not None:
        return _mcp_session
        
    _mcp_stack = AsyncExitStack()
    server_params = StdioServerParameters(
        command=settings.mcp_command,
        args=settings.mcp_args.split(),
        env=None
    )
    
    try:
        read, write = await _mcp_stack.enter_async_context(stdio_client(server_params))
        session = await _mcp_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        _mcp_session = session
        return _mcp_session
    except Exception as e:
        raise MCPConnectionError("Failed to initialize global MCP session") from e

async def run_mcp_tests(test_scripts: List[Dict[str, str]], run_id: str = None) -> str:
    """
    Connects to the Node.js MCP server via stdio, passes the test scripts,
    and returns the JSON report of the execution.
    """
    try:
        async with _mcp_lock:
            session = await get_mcp_session()
            payload = {"files": test_scripts}
            if run_id:
                payload["run_id"] = run_id
            result = await session.call_tool("run_test_suite", payload)
        
        if result.is_error:
            error_msg = "\\n".join([c.text for c in result.content if c.type == "text"])
            raise MCPConnectionError(f"MCP Tool returned error: {error_msg}")
            
        output = "\\n".join([c.text for c in result.content if c.type == "text"])
        return output
    except Exception as e:
        logger.error(f"Failed to execute tests via MCP: {e}")
        raise MCPConnectionError("Failed to communicate with Playwright MCP server.") from e

async def explore_url_via_mcp(url: str) -> str:
    """
    Connects to the Node.js MCP server via stdio and extracts the DOM.
    """
    try:
        async with _mcp_lock:
            session = await get_mcp_session()
            result = await session.call_tool("explore_url", {"url": url})
        
        if result.is_error:
            error_msg = "\\n".join([c.text for c in result.content if c.type == "text"])
            logger.error(f"MCP Tool returned error: {error_msg}")
            return f"Failed to extract DOM: {error_msg}"
            
        return "\\n".join([c.text for c in result.content if c.type == "text"])
    except Exception as e:
        logger.error(f"Failed to explore URL via MCP: {e}")
        return "Failed to communicate with Playwright MCP server for DOM extraction."

async def execute_playwright_commands_via_mcp(base_url: str, commands: List[Dict[str, Any]]) -> str:
    """
    Connects to the Node.js MCP server via stdio and executes atomic Playwright commands.
    """
    try:
        async with _mcp_lock:
            session = await get_mcp_session()
            result = await session.call_tool("execute_playwright_commands", {
                "base_url": base_url,
                "commands": commands
            })
        
        if result.is_error:
            error_msg = "\\n".join([c.text for c in result.content if c.type == "text"])
            logger.error(f"MCP Tool returned error: {error_msg}")
            return f"Failed to execute commands: {error_msg}"
            
        return "\\n".join([c.text for c in result.content if c.type == "text"])
    except Exception as e:
        logger.error(f"Failed to execute commands via MCP: {e}")
        return "Failed to communicate with Playwright MCP server for command execution."

async def reset_browser_via_mcp() -> str:
    """
    Connects to the Node.js MCP server via stdio and resets the browser session.
    """
    try:
        async with _mcp_lock:
            session = await get_mcp_session()
            result = await session.call_tool("reset_browser", {})
        
        if result.is_error:
            error_msg = "\\n".join([c.text for c in result.content if c.type == "text"])
            logger.error(f"MCP Tool returned error: {error_msg}")
            return f"Failed to reset browser: {error_msg}"
            
        return "\\n".join([c.text for c in result.content if c.type == "text"])
    except Exception as e:
        logger.error(f"Failed to reset browser via MCP: {e}")
        return "Failed to communicate with Playwright MCP server for browser reset."
