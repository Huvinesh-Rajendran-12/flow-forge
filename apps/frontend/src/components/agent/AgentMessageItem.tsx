import { TextMessage, ErrorMessage, UserMessage } from '../../types/api';

interface AgentMessageItemProps {
  message: TextMessage | ErrorMessage | UserMessage;
}

export function AgentMessageItem({ message }: AgentMessageItemProps) {
  if (message.type === 'error') {
    return (
      <div className="px-3 py-1 font-mono text-xs">
        <span className="text-terminal-red">{'! '}{message.content}</span>
      </div>
    );
  }

  if (message.type === 'user_message') {
    return (
      <div className="px-3 py-1 font-mono text-xs mt-2">
        <span className="text-terminal-green">{'$ '}</span>
        <span className="text-terminal-green whitespace-pre-wrap">{message.content}</span>
      </div>
    );
  }

  return (
    <div className="px-3 py-1 font-mono text-xs">
      <span className="text-terminal-green-muted">{'> '}</span>
      <span className="text-terminal-text whitespace-pre-wrap">{message.content}</span>
    </div>
  );
}
