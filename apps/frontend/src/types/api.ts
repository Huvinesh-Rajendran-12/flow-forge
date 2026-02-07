export type MessageType = 'text' | 'tool_use' | 'result' | 'error' | 'workspace';

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

export type Message =
  | TextMessage
  | ToolUseMessage
  | ResultMessage
  | ErrorMessage
  | WorkspaceMessage;

export interface GenerateWorkflowRequest {
  description: string;
}
