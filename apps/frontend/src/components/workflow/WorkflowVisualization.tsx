import { useWorkflowStore } from '../../store/workflowStore';
import { WorkflowGraph } from './WorkflowGraph';
import { Workflow } from 'lucide-react';

export function WorkflowVisualization() {
  const workflowGraph = useWorkflowStore((state) => state.workflowGraph);
  const workflowMetadata = useWorkflowStore((state) => state.workflowMetadata);

  if (!workflowGraph) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center text-gray-500">
          <Workflow className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium mb-2">No workflow generated yet</p>
          <p className="text-sm">
            The workflow visualization will appear here once generated
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <div className="border-b border-gray-200 bg-white p-4">
        <h2 className="text-xl font-bold text-gray-900 mb-1">Workflow Visualization</h2>
        <div className="flex gap-4 text-sm text-gray-600">
          <span>{workflowMetadata.stepCount} steps</span>
          {workflowMetadata.path && (
            <span className="font-mono truncate">{workflowMetadata.path}</span>
          )}
        </div>
      </div>
      <div className="flex-1">
        <WorkflowGraph graph={workflowGraph} />
      </div>
    </div>
  );
}
