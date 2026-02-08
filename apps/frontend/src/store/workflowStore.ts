import { create } from 'zustand';
import { Message, ExecutionReportMessage, UserMessage } from '../types/api';
import { WorkflowGraph, WorkflowMetadata, ExecutionStatus } from '../types/workflow';

export type AgentPhase = 'idle' | 'searching' | 'building' | 'executing' | 'self_correcting' | 'complete' | 'error';

interface WorkflowState {
  messages: Message[];
  isStreaming: boolean;
  workflowGraph: WorkflowGraph | null;
  workflowMetadata: WorkflowMetadata;
  costUsd: number;
  totalTokens: number;
  agentPhase: AgentPhase;
  nodeStatuses: Record<string, ExecutionStatus>;
  executionReports: ExecutionReportMessage[];
  correctionAttempt: number;
  workflowSaved: { workflow_id: string; team: string; version: number } | null;
  sessionId: string | null;
  currentWorkflowId: string | null;

  // Actions
  addMessage: (message: Message) => void;
  setStreaming: (isStreaming: boolean) => void;
  setWorkflowGraph: (graph: WorkflowGraph, metadata?: Partial<WorkflowMetadata>) => void;
  setNodeStatuses: (statuses: Record<string, ExecutionStatus> | ((prev: Record<string, ExecutionStatus>) => Record<string, ExecutionStatus>)) => void;
  setAgentPhase: (phase: AgentPhase) => void;
  reset: () => void;
  softReset: () => void;
}

function detectPhase(message: Message, currentPhase: AgentPhase): AgentPhase {
  if (message.type === 'error') return 'error';
  if (message.type === 'workflow_saved') return 'complete';
  if (message.type === 'execution_report') return 'executing';
  if (message.type === 'workflow') return 'executing';

  if (message.type === 'text') {
    const text = message.content.toLowerCase();
    if (text.includes('self-correction') || text.includes('self_correction') || text.includes('fix')) {
      return 'self_correcting';
    }
    if (text.includes('search') || text.includes('knowledge')) return 'searching';
    if (text.includes('generat') || text.includes('build') || text.includes('creat')) return 'building';
  }

  if (message.type === 'tool_use') {
    // During self-correction, keep the phase sticky even for tool_use events
    if (currentPhase === 'self_correcting') {
      return 'self_correcting';
    }
    const tool = message.content.tool.toLowerCase();
    if (tool.includes('search') || tool.includes('knowledge')) return 'searching';
    if (tool.includes('write') || tool.includes('edit')) return 'building';
  }

  return currentPhase === 'idle' ? 'searching' : currentPhase;
}

const initialState = {
  messages: [] as Message[],
  isStreaming: false,
  workflowGraph: null as WorkflowGraph | null,
  workflowMetadata: { stepCount: 0 } as WorkflowMetadata,
  costUsd: 0,
  totalTokens: 0,
  agentPhase: 'idle' as AgentPhase,
  nodeStatuses: {} as Record<string, ExecutionStatus>,
  executionReports: [] as ExecutionReportMessage[],
  correctionAttempt: 0,
  workflowSaved: null as { workflow_id: string; team: string; version: number } | null,
  sessionId: null as string | null,
  currentWorkflowId: null as string | null,
};

export const useWorkflowStore = create<WorkflowState>((set) => ({
  ...initialState,

  addMessage: (message) =>
    set((state) => {
      const newMessages = [...state.messages, message];
      let newCorrectionAttempt = state.correctionAttempt;

      // Track correction attempts
      if (message.type === 'text') {
        const text = (message.content as string).toLowerCase();
        if (text.includes('self-correction') || text.includes('self_correction')) {
          newCorrectionAttempt = state.correctionAttempt + 1;
        }
      }

      // Reset correction tracking when we get a new execution report
      if (message.type === 'execution_report') {
        newCorrectionAttempt = 0;
      }

      const newPhase = detectPhase(message, state.agentPhase);
      const updates: Partial<WorkflowState> = {
        messages: newMessages,
        agentPhase: newPhase,
        correctionAttempt: newCorrectionAttempt,
      };

      if (message.type === 'result') {
        updates.costUsd = state.costUsd + (message.content.cost_usd ?? 0);
        updates.totalTokens = state.totalTokens + (message.content.usage.total_tokens ?? 0);
        if (message.content.session_id) {
          updates.sessionId = message.content.session_id;
        }
      }

      if (message.type === 'workspace') {
        updates.workflowMetadata = {
          ...state.workflowMetadata,
          path: message.content.path,
        };
      }

      if (message.type === 'execution_report') {
        updates.executionReports = [...state.executionReports, message];
      }

      if (message.type === 'workflow_saved') {
        updates.workflowSaved = message.content;
        updates.currentWorkflowId = message.content.workflow_id;
      }

      return updates;
    }),

  setStreaming: (isStreaming) =>
    set((state) => ({
      isStreaming,
      ...(isStreaming
        ? { agentPhase: 'searching' as AgentPhase }
        : state.agentPhase !== 'error' && state.agentPhase !== 'idle'
          ? { agentPhase: 'complete' as AgentPhase }
          : {}),
    })),

  setWorkflowGraph: (graph, metadata = {}) =>
    set((state) => ({
      workflowGraph: graph,
      workflowMetadata: {
        ...state.workflowMetadata,
        ...metadata,
        stepCount: graph.nodes.filter((n) => n.type === 'action').length,
      },
    })),

  setNodeStatuses: (statuses) =>
    set((state) => ({
      nodeStatuses: typeof statuses === 'function' ? statuses(state.nodeStatuses) : statuses,
    })),

  setAgentPhase: (phase) => set({ agentPhase: phase }),

  reset: () => set(initialState),

  softReset: () =>
    set({
      isStreaming: false,
      agentPhase: 'idle' as AgentPhase,
      nodeStatuses: {} as Record<string, ExecutionStatus>,
      executionReports: [] as ExecutionReportMessage[],
      correctionAttempt: 0,
      // Preserve: messages, sessionId, currentWorkflowId, workflowGraph,
      // workflowMetadata, costUsd, totalTokens, workflowSaved
    }),
}));

// Selectors
export const selectAgentMessages = (state: WorkflowState) =>
  state.messages.filter((m) => m.type === 'text' || m.type === 'error' || m.type === 'user_message');

export const selectToolMessages = (state: WorkflowState) =>
  state.messages.filter((m) => m.type === 'tool_use');

export const selectLatestExecutionReport = (state: WorkflowState) =>
  state.executionReports.length > 0 ? state.executionReports[state.executionReports.length - 1] : null;
