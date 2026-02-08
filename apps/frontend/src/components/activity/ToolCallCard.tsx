import { useState } from 'react';
import { ToolUseMessage } from '../../types/api';
import { Badge } from '../ui/Badge';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface ToolCallCardProps {
  message: ToolUseMessage;
  isLatest?: boolean;
}

export function ToolCallCard({ message, isLatest }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-dashed border-terminal-border rounded p-2 bg-terminal-card">
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3 text-terminal-text-dim flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-terminal-text-dim flex-shrink-0" />
        )}
        <Badge variant={isLatest ? 'running' : 'default'}>
          {message.content.tool}
        </Badge>
        {isLatest && (
          <span className="text-[10px] text-terminal-cyan font-mono ml-auto">running</span>
        )}
      </div>

      {expanded && (
        <div className="mt-2 ml-5">
          <pre className="text-[10px] text-terminal-text-dim font-mono bg-terminal-bg p-2 rounded overflow-x-auto max-h-32 overflow-y-auto">
            {JSON.stringify(message.content.input, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
