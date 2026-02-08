export type MessageType = 'text' | 'tool_use' | 'result' | 'error' | 'workspace' | 'workflow' | 'execution_report' | 'workflow_saved';

export interface BaseMessage {
  id: string;
  type: MessageType;
  timestamp: number;
}

export interface TextMessage extends BaseMessage {
  type: 'text';
  content: string;
}

export interface ToolUseMessage extends BaseMessage {
  type: 'tool_use';
  content: {
    tool: string;
    input: Record<string, unknown>;
  };
}

export interface ResultMessage extends BaseMessage {
  type: 'result';
  content: {
    cost_usd: number;
    usage: {
      total_tokens: number;
      input_tokens?: number;
      output_tokens?: number;
    };
  };
}

export interface ErrorMessage extends BaseMessage {
  type: 'error';
  content: string;
}

export interface WorkspaceMessage extends BaseMessage {
  type: 'workspace';
  content: {
    path: string;
  };
}

export interface WorkflowMessage extends BaseMessage {
  type: 'workflow';
  content: {
    id: string;
    name: string;
    description: string;
    nodes: Array<{
      id: string;
      name: string;
      description: string;
      service: string;
      action: string;
      actor: string;
      parameters?: Array<{ name: string; type: string; required?: boolean }>;
      depends_on?: string[];
      outputs?: Record<string, string>;
    }>;
    edges: Array<{ source: string; target: string }>;
  };
}

export interface ExecutionReportMessage extends BaseMessage {
  type: 'execution_report';
  content: {
    report: {
      workflow_id: string;
      workflow_name: string;
      total_steps: number;
      successful: number;
      failed: number;
      skipped: number;
      trace: {
        steps: Array<{
          node_id: string;
          service: string;
          action: string;
          parameters: Record<string, unknown>;
          result?: Record<string, unknown> | null;
          status: 'success' | 'failed' | 'skipped';
          error?: string | null;
        }>;
      };
      dependency_violations: string[];
    };
    markdown: string;
    attempt: number;
  };
}

export interface WorkflowSavedMessage extends BaseMessage {
  type: 'workflow_saved';
  content: {
    workflow_id: string;
    team: string;
    version: number;
  };
}

export type Message =
  | TextMessage
  | ToolUseMessage
  | ResultMessage
  | ErrorMessage
  | WorkspaceMessage
  | WorkflowMessage
  | ExecutionReportMessage
  | WorkflowSavedMessage;

export interface GenerateWorkflowRequest {
  description: string;
}
