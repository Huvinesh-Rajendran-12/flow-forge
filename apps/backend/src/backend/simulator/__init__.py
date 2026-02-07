"""FlowForge environment simulated service backends for workflow execution."""

from .failures import FailureConfig
from .services import GitHubService, GoogleService, HRService, JiraService, SlackService
from .state import ExecutionTrace, SimulatorState


def create_simulator(
    failure_config: FailureConfig | None = None,
) -> tuple[SimulatorState, ExecutionTrace, dict, FailureConfig | None]:
    """Create a fresh simulator with all services wired together."""
    state = SimulatorState()
    trace = ExecutionTrace()

    services = {
        "hr": HRService(state, trace),
        "google": GoogleService(state, trace),
        "slack": SlackService(state, trace),
        "jira": JiraService(state, trace),
        "github": GitHubService(state, trace),
    }

    return state, trace, services, failure_config
