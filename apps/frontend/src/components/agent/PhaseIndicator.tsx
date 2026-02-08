import { useWorkflowStore, AgentPhase } from '../../store/workflowStore';

const phaseLabels: Record<AgentPhase, string> = {
  idle: 'Waiting for input...',
  searching: 'Searching knowledge base...',
  building: 'Building workflow...',
  executing: 'Executing workflow...',
  self_correcting: 'Self-correcting...',
  complete: 'Complete',
  error: 'Error occurred',
};

export function PhaseIndicator() {
  const agentPhase = useWorkflowStore((state) => state.agentPhase);
  const isStreaming = useWorkflowStore((state) => state.isStreaming);

  if (!isStreaming && agentPhase === 'idle') return null;

  const isActive = isStreaming && agentPhase !== 'complete' && agentPhase !== 'error';

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono">
      {isActive && (
        <span className="w-1.5 h-1.5 rounded-full bg-terminal-green animate-blink" />
      )}
      {agentPhase === 'complete' && (
        <span className="w-1.5 h-1.5 rounded-full bg-terminal-green" />
      )}
      {agentPhase === 'error' && (
        <span className="w-1.5 h-1.5 rounded-full bg-terminal-red" />
      )}
      <span className={agentPhase === 'error' ? 'text-terminal-red' : 'text-terminal-green-muted'}>
        {'> '}{phaseLabels[agentPhase]}
      </span>
    </div>
  );
}
