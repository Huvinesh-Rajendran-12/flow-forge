"""DAG executor which  runs a workflow against simulated service backends."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from ..simulator.failures import FailureConfig
from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace, SimulatorState, TraceStep
from .report import ExecutionReport
from .schema import Workflow, WorkflowNode


class WorkflowExecutor:
    """Executes a workflow DAG in topological order against the simulator."""

    def __init__(
        self,
        state: SimulatorState,
        trace: ExecutionTrace,
        services: dict,
        failure_config: FailureConfig | None = None,
    ):
        self.state = state
        self.trace = trace
        self.services = services
        self.failure_config = failure_config
        # Stores outputs keyed by node_id -> result dict
        self.node_outputs: dict[str, dict] = {}

    async def execute(self, workflow: Workflow) -> ExecutionReport:
        """Execute the DAG in topological order, respecting dependencies."""
        self.trace.started_at = datetime.now()
        node_map = {node.id: node for node in workflow.nodes}
        order = self._topological_sort(workflow)
        dependency_violations: list[str] = []

        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()
        successful = 0
        failed = 0
        skipped = 0

        for node_id in order:
            node = node_map[node_id]

            # Skip if any upstream dependency failed
            upstream_failures = [dep for dep in node.depends_on if dep in failed_nodes or dep in skipped_nodes]
            if upstream_failures:
                skipped_nodes.add(node_id)
                skipped += 1
                self.trace.steps.append(
                    TraceStep(
                        node_id=node_id,
                        service=node.service,
                        action=node.action,
                        parameters={},
                        status="skipped",
                        error=f"Skipped due to upstream failure: {', '.join(upstream_failures)}",
                    )
                )
                continue

            # Check for injected failures
            if self.failure_config:
                rule = self.failure_config.should_fail(node.service, node.action)
                if rule:
                    failed_nodes.add(node_id)
                    failed += 1
                    self.trace.steps.append(
                        TraceStep(
                            node_id=node_id,
                            service=node.service,
                            action=node.action,
                            parameters=self._resolve_parameters(node, workflow),
                            status="failed",
                            error=f"[{rule.error_type}] {rule.message}",
                        )
                    )
                    continue

            # Execute the node
            try:
                result = self._execute_node(node, workflow)
                self.node_outputs[node_id] = result
                successful += 1
            except Exception as e:
                failed_nodes.add(node_id)
                failed += 1
                error_msg = str(e)
                if isinstance(e, ServiceError):
                    dependency_violations.append(f"{node_id}: {e}")
                self.trace.steps.append(
                    TraceStep(
                        node_id=node_id,
                        service=node.service,
                        action=node.action,
                        parameters=self._resolve_parameters(node, workflow),
                        status="failed",
                        error=error_msg,
                    )
                )

        self.trace.completed_at = datetime.now()

        return ExecutionReport(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            total_steps=len(workflow.nodes),
            successful=successful,
            failed=failed,
            skipped=skipped,
            trace=self.trace,
            dependency_violations=dependency_violations,
        )

    def _execute_node(self, node: WorkflowNode, workflow: Workflow) -> dict:
        """Execute a single workflow node by dispatching to the appropriate service."""
        service = self.services.get(node.service)
        if service is None:
            raise ServiceError(f"Unknown service: {node.service}", "unknown_service")

        action_fn = getattr(service, node.action, None)
        if action_fn is None:
            raise ServiceError(
                f"Unknown action {node.action} for service {node.service}",
                "unknown_action",
            )

        params = self._resolve_parameters(node, workflow)
        return action_fn(node.id, **params)

    def _resolve_parameters(self, node: WorkflowNode, workflow: Workflow) -> dict:
        """Build the parameter dict for a node, substituting global and upstream values."""
        params = {}
        for param in node.parameters:
            value = param.value
            # Substitute global workflow parameters (e.g., "{{employee_name}}")
            if isinstance(value, str) and "{{" in value:
                for key, val in workflow.parameters.items():
                    value = value.replace(f"{{{{{key}}}}}", str(val))
                # Also substitute upstream node outputs (e.g., "{{create_hr_record.employee_id}}")
                for upstream_id, outputs in self.node_outputs.items():
                    for out_key, out_val in outputs.items():
                        value = value.replace(f"{{{{{upstream_id}.{out_key}}}}}", str(out_val))
            params[param.name] = value
        return params

    def _topological_sort(self, workflow: Workflow) -> list[str]:
        """Return node IDs in topological order based on depends_on edges."""
        in_degree: dict[str, int] = defaultdict(int)
        dependents: dict[str, list[str]] = defaultdict(list)
        all_ids = [node.id for node in workflow.nodes]

        for node in workflow.nodes:
            in_degree.setdefault(node.id, 0)
            for dep in node.depends_on:
                dependents[dep].append(node.id)
                in_degree[node.id] += 1

        queue: deque[str] = deque()
        for nid in all_ids:
            if in_degree[nid] == 0:
                queue.append(nid)

        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for dependent in dependents[nid]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(all_ids):
            missing = set(all_ids) - set(order)
            raise ValueError(f"Cycle detected in workflow DAG involving nodes: {missing}")

        return order
