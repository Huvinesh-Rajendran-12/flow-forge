import { useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { CustomNode } from './CustomNode';
import { WorkflowGraph as WorkflowGraphType } from '../../types/workflow';

const nodeTypes = {
  start: CustomNode,
  action: CustomNode,
  end: CustomNode,
};

interface WorkflowGraphProps {
  graph: WorkflowGraphType;
}

export function WorkflowGraph({ graph }: WorkflowGraphProps) {
  const [nodes, , onNodesChange] = useNodesState(graph.nodes);
  const [edges, , onEdgesChange] = useEdgesState(graph.edges);

  const onInit = useCallback((reactFlowInstance: any) => {
    reactFlowInstance.fitView({ padding: 0.2 });
  }, []);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onInit={onInit}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            switch (node.type) {
              case 'start':
                return '#86efac';
              case 'end':
                return '#fca5a5';
              case 'action':
                return '#93c5fd';
              default:
                return '#e5e7eb';
            }
          }}
        />
        <Panel position="top-right" className="bg-white p-3 rounded-lg shadow-md border border-gray-200">
          <div className="text-sm font-medium text-gray-900">
            {graph.nodes.filter((n) => n.type === 'action').length} Steps
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
