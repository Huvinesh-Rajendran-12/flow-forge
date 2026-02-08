import { useWorkflowStore, selectAgentMessages } from '../../store/workflowStore';
import { useAutoScroll } from '../../hooks/useAutoScroll';
import { TextMessage, ErrorMessage, UserMessage } from '../../types/api';
import { PhaseIndicator } from './PhaseIndicator';
import { AgentMessageItem } from './AgentMessageItem';
import { AgentInput } from './AgentInput';

export function AgentStreamPanel() {
  const agentMessages = useWorkflowStore(selectAgentMessages);
  const sessionId = useWorkflowStore((state) => state.sessionId);
  const reset = useWorkflowStore((state) => state.reset);
  const isStreaming = useWorkflowStore((state) => state.isStreaming);
  const scrollRef = useAutoScroll<HTMLDivElement>([agentMessages.length]);

  return (
    <div className="h-full flex flex-col bg-terminal-panel border-r border-dashed border-terminal-border">
      {/* Header */}
      <div className="border-b border-dashed border-terminal-border px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-sm font-mono font-bold text-terminal-green tracking-widest">
            FLOWFORGE
          </h1>
          <p className="text-[10px] font-mono text-terminal-text-dim mt-0.5">
            agent stream
          </p>
        </div>
        {sessionId && !isStreaming && (
          <button
            onClick={reset}
            className="text-[10px] font-mono text-terminal-text-dim hover:text-terminal-green border border-dashed border-terminal-border px-2 py-1 transition-colors"
          >
            new workflow
          </button>
        )}
      </div>

      {/* Phase */}
      <PhaseIndicator />

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto py-2">
        {agentMessages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center px-4">
              <p className="text-terminal-text-dim font-mono text-xs">
                {'> '}ready_
              </p>
              <p className="text-terminal-text-dim font-mono text-[10px] mt-2">
                describe a workflow to begin
              </p>
            </div>
          </div>
        ) : (
          agentMessages.map((msg) => (
            <AgentMessageItem
              key={msg.id}
              message={msg as TextMessage | ErrorMessage | UserMessage}
            />
          ))
        )}
      </div>

      {/* Input */}
      <AgentInput />
    </div>
  );
}
