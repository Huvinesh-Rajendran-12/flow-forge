import { Node, Edge } from 'reactflow';

export type NodeType = 'start' | 'action' | 'end';

export interface WorkflowNode extends Node {
  type: NodeType;
  data: {
    label: string;
    description?: string;
  };
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: Edge[];
}

export interface WorkflowMetadata {
  path?: string;
  stepCount: number;
}
