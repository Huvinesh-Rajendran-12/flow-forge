import { useEffect, useRef } from 'react';
import { useWorkflowStore, selectLatestExecutionReport } from '../store/workflowStore';
import { ExecutionStatus } from '../types/workflow';

export function useExecutionReplay() {
  const executionReport = useWorkflowStore(selectLatestExecutionReport);
  const setNodeStatuses = useWorkflowStore((state) => state.setNodeStatuses);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    // Clear any pending animations
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];

    if (!executionReport) return;

    const steps = executionReport.content.report.trace?.steps;

    if (!steps || steps.length === 0) return;

    // Set all nodes to pending first
    const initialStatuses: Record<string, ExecutionStatus> = {};
    steps.forEach((step) => {
      initialStatuses[step.node_id] = 'pending';
    });
    setNodeStatuses(initialStatuses);

    // Animate through each step
    steps.forEach((step, index) => {
      // Set to running
      const runningTimeout = setTimeout(() => {
        setNodeStatuses((prev) => ({
          ...prev,
          [step.node_id]: 'running',
        }));
      }, index * 600 + 200);
      timeoutsRef.current.push(runningTimeout);

      // Set to final status
      const finalStatus: ExecutionStatus =
        step.status === 'success' ? 'success' : step.status === 'failed' ? 'failed' : 'skipped';

      const finalTimeout = setTimeout(() => {
        setNodeStatuses((prev) => ({
          ...prev,
          [step.node_id]: finalStatus,
        }));
      }, (index + 1) * 600);
      timeoutsRef.current.push(finalTimeout);
    });

    return () => {
      timeoutsRef.current.forEach(clearTimeout);
      timeoutsRef.current = [];
    };
  }, [executionReport, setNodeStatuses]);
}
