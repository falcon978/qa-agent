class BaseOrchestratorError(Exception):
    """Base exception class for all orchestrator errors."""
    pass

class DataValidationError(BaseOrchestratorError):
    """Raised when data validation fails against the schema."""
    pass

class ServiceTimeoutError(BaseOrchestratorError):
    """Raised when an external service or MCP connection times out."""
    pass

class StateTransitionViolation(BaseOrchestratorError):
    """Raised when an invalid state transition is attempted."""
    pass

class LLMExecutionError(BaseOrchestratorError):
    """Raised when the LLM service fails to execute or respond correctly."""
    pass

class MCPConnectionError(BaseOrchestratorError):
    """Raised when the connection to the MCP server fails."""
    pass
