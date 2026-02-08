export type MessageType = 'text' | 'tool_use' | 'tool_result' | 'result' | 'error' | 'workspace' | 'workflow' | 'execution_report' | 'workflow_saved' | 'user_message';

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

export interface ToolResultMessage extends BaseMessage {
  type: 'tool_result';
  content: {
    tool_use_id: string;
    result: unknown;
    is_error: boolean;
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
    session_id?: string;
  };
}

export interface UserMessage extends BaseMessage {
  type: 'user_message';
  content: string;
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
      parameters?: Array<{ name: string; value: unknown; description: string; required?: boolean }>;
      depends_on?: string[];
      outputs?: Record<string, string>;
    }>;
    edges: Array<{ source: string; target: string }>;
    team?: string;
    parameters?: Record<string, unknown>;
    version?: number;
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
  | ToolResultMessage
  | ResultMessage
  | ErrorMessage
  | WorkspaceMessage
  | WorkflowMessage
  | ExecutionReportMessage
  | WorkflowSavedMessage
  | UserMessage;

export interface GenerateWorkflowRequest {
  description: string;
  workflow_id?: string;
  session_id?: string;
}
