import { useWorkflowStore } from '../../store/workflowStore';
import { Badge } from '../ui/Badge';

export function MetricsBar() {
  const costUsd = useWorkflowStore((state) => state.costUsd);
  const totalTokens = useWorkflowStore((state) => state.totalTokens);
  const workflowSaved = useWorkflowStore((state) => state.workflowSaved);

  if (costUsd === 0 && !workflowSaved) return null;

  return (
    <div className="border-t border-dashed border-terminal-border px-3 py-2">
      <div className="flex flex-wrap gap-2 text-[10px] font-mono">
        {costUsd > 0 && (
          <span className="text-terminal-text-dim">
            cost: ${costUsd.toFixed(4)}
          </span>
        )}
        {totalTokens > 0 && (
          <span className="text-terminal-text-dim">
            tokens: {(totalTokens / 1000).toFixed(1)}k
          </span>
        )}
        {workflowSaved && (
          <Badge variant="success">saved</Badge>
        )}
      </div>
    </div>
  );
}
