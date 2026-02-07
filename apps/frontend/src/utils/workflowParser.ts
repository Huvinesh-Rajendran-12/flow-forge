import { WorkflowGraph, WorkflowNode } from '../types/workflow';
import { Edge } from 'reactflow';

export function parseWorkflowCode(code: string): WorkflowGraph {
  const nodes: WorkflowNode[] = [];
  const edges: Edge[] = [];

  // Extract function definitions
  const functionRegex = /def\s+(\w+)\s*\([^)]*\):\s*\n(?:\s*"""([^"]+)""")?/g;
  const functions: Array<{ name: string; description?: string }> = [];

  let match;
  while ((match = functionRegex.exec(code)) !== null) {
    const [, name, description] = match;

    // Skip internal functions and main
    if (name.startsWith('_') || name === 'main') {
      continue;
    }

    functions.push({ name, description: description?.trim() });
  }

  if (functions.length === 0) {
    return { nodes: [], edges: [] };
  }

  // Create start node
  const startNode: WorkflowNode = {
    id: 'start',
    type: 'start',
    position: { x: 250, y: 50 },
    data: { label: 'Start' },
  };
  nodes.push(startNode);

  // Create action nodes for each function
  functions.forEach((func, index) => {
    const nodeId = `step-${index}`;
    const node: WorkflowNode = {
      id: nodeId,
      type: 'action',
      position: { x: 250, y: 150 + index * 120 },
      data: {
        label: func.name.replace(/_/g, ' '),
        description: func.description,
      },
    };
    nodes.push(node);

    // Create edge from previous node
    const sourceId = index === 0 ? 'start' : `step-${index - 1}`;
    edges.push({
      id: `edge-${sourceId}-${nodeId}`,
      source: sourceId,
      target: nodeId,
      type: 'smoothstep',
    });
  });

  // Create end node
  const endNode: WorkflowNode = {
    id: 'end',
    type: 'end',
    position: { x: 250, y: 150 + functions.length * 120 },
    data: { label: 'End' },
  };
  nodes.push(endNode);

  // Create edge from last function to end
  edges.push({
    id: `edge-step-${functions.length - 1}-end`,
    source: `step-${functions.length - 1}`,
    target: 'end',
    type: 'smoothstep',
  });

  return { nodes, edges };
}

export function extractWorkflowFromToolUse(toolInput: Record<string, unknown>): string | null {
  // Check if this is a Write tool call for workflow.py
  const filePath = toolInput.file_path as string;
  if (!filePath?.endsWith('workflow.py')) {
    return null;
  }

  // Extract content from either 'content' or 'file_contents' field
  const content = (toolInput.content || toolInput.file_contents) as string;
  return content || null;
}

export function parseWorkflowJSON(workflowData: any): WorkflowGraph {
  const nodes: WorkflowNode[] = [];
  const edges: Edge[] = [];

  if (!workflowData.nodes || workflowData.nodes.length === 0) {
    return { nodes: [], edges: [] };
  }

  // Create start node
  const startNode: WorkflowNode = {
    id: 'start',
    type: 'start',
    position: { x: 250, y: 50 },
    data: { label: 'Start' },
  };
  nodes.push(startNode);

  // Create action nodes from workflow nodes
  workflowData.nodes.forEach((node: any, index: number) => {
    const actionNode: WorkflowNode = {
      id: node.id,
      type: 'action',
      position: { x: 250, y: 150 + index * 120 },
      data: {
        label: node.name || node.id,
        description: node.description,
      },
    };
    nodes.push(actionNode);
  });

  // Create end node
  const endNode: WorkflowNode = {
    id: 'end',
    type: 'end',
    position: { x: 250, y: 150 + workflowData.nodes.length * 120 },
    data: { label: 'End' },
  };
  nodes.push(endNode);

  // Create edges from workflow edges
  if (workflowData.edges && workflowData.edges.length > 0) {
    workflowData.edges.forEach((edge: any, index: number) => {
      edges.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
      });
    });

    // Connect start node to nodes without dependencies
    const nodesWithDependencies = new Set(workflowData.edges.map((e: any) => e.target));
    workflowData.nodes.forEach((node: any) => {
      if (!nodesWithDependencies.has(node.id)) {
        edges.push({
          id: `edge-start-${node.id}`,
          source: 'start',
          target: node.id,
          type: 'smoothstep',
        });
      }
    });

    // Connect leaf nodes to end node
    const nodesWithOutgoing = new Set(workflowData.edges.map((e: any) => e.source));
    workflowData.nodes.forEach((node: any) => {
      if (!nodesWithOutgoing.has(node.id)) {
        edges.push({
          id: `edge-${node.id}-end`,
          source: node.id,
          target: 'end',
          type: 'smoothstep',
        });
      }
    });
  } else {
    // No explicit edges, create linear flow
    edges.push({
      id: `edge-start-${workflowData.nodes[0].id}`,
      source: 'start',
      target: workflowData.nodes[0].id,
      type: 'smoothstep',
    });

    for (let i = 0; i < workflowData.nodes.length - 1; i++) {
      edges.push({
        id: `edge-${workflowData.nodes[i].id}-${workflowData.nodes[i + 1].id}`,
        source: workflowData.nodes[i].id,
        target: workflowData.nodes[i + 1].id,
        type: 'smoothstep',
      });
    }

    edges.push({
      id: `edge-${workflowData.nodes[workflowData.nodes.length - 1].id}-end`,
      source: workflowData.nodes[workflowData.nodes.length - 1].id,
      target: 'end',
      type: 'smoothstep',
    });
  }

  return { nodes, edges };
}
