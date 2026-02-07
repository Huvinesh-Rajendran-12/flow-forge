import { create } from 'zustand';
import { Message } from '../types/api';
import { WorkflowGraph, WorkflowMetadata } from '../types/workflow';

interface WorkflowState {
  messages: Message[];
  isStreaming: boolean;
  workflowGraph: WorkflowGraph | null;
  workflowMetadata: WorkflowMetadata;
  costUsd: number;
  totalTokens: number;

  // Actions
  addMessage: (message: Message) => void;
  setStreaming: (isStreaming: boolean) => void;
  setWorkflowGraph: (graph: WorkflowGraph, metadata?: Partial<WorkflowMetadata>) => void;
  reset: () => void;
}

const initialState = {
  messages: [],
  isStreaming: false,
  workflowGraph: null,
  workflowMetadata: { stepCount: 0 },
  costUsd: 0,
  totalTokens: 0,
};

export const useWorkflowStore = create<WorkflowState>((set) => ({
  ...initialState,

  addMessage: (message) =>
    set((state) => {
      const newMessages = [...state.messages, message];

      // Update metrics if this is a result message
      if (message.type === 'result') {
        return {
          messages: newMessages,
          costUsd: message.content.cost_usd,
          totalTokens: message.content.usage.total_tokens,
        };
      }

      // Update workspace path if this is a workspace message
      if (message.type === 'workspace') {
        return {
          messages: newMessages,
          workflowMetadata: {
            ...state.workflowMetadata,
            path: message.content.path,
          },
        };
      }

      return { messages: newMessages };
    }),

  setStreaming: (isStreaming) => set({ isStreaming }),

  setWorkflowGraph: (graph, metadata = {}) =>
    set((state) => ({
      workflowGraph: graph,
      workflowMetadata: {
        ...state.workflowMetadata,
        ...metadata,
        stepCount: graph.nodes.filter((n) => n.type === 'action').length,
      },
    })),

  reset: () => set(initialState),
}));
