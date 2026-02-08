import { useState, FormEvent, KeyboardEvent } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';
import { useSSEStream } from '../../hooks/useSSEStream';

export function AgentInput() {
  const [description, setDescription] = useState('');
  const isStreaming = useWorkflowStore((state) => state.isStreaming);
  const sessionId = useWorkflowStore((state) => state.sessionId);
  const { startStream } = useSSEStream();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!description.trim() || isStreaming) return;
    await startStream(description.trim());
    setDescription('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-dashed border-terminal-border p-3">
      <div className="flex items-start gap-2">
        <span className="text-terminal-green font-mono text-sm pt-1.5 select-none">$</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={sessionId ? "refine your workflow..." : "describe your workflow..."}
          className="flex-1 bg-transparent border-none outline-none font-mono text-sm text-terminal-green placeholder:text-terminal-text-dim caret-terminal-green resize-none"
          rows={2}
          disabled={isStreaming}
        />
      </div>
    </form>
  );
}
