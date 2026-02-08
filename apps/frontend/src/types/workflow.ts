import { Node, Edge } from 'reactflow';

export type NodeType = 'start' | 'action' | 'end';

export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export interface WorkflowNode extends Node {
  type: NodeType;
  data: {
    label: string;
    description?: string;
    service?: string;
    action?: string;
    actor?: string;
    executionStatus?: ExecutionStatus;
  };
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: Edge[];
}

export interface WorkflowMetadata {
  path?: string;
  stepCount: number;
  workflowName?: string;
}
