import { useWorkflowStore, selectToolMessages } from '../../store/workflowStore';
import { useAutoScroll } from '../../hooks/useAutoScroll';
import { ToolUseMessage, ExecutionReportMessage } from '../../types/api';
import { ToolCallCard } from './ToolCallCard';
import { ExecutionReportSection } from './ExecutionReportSection';
import { MetricsBar } from './MetricsBar';

export function ToolActivityPanel() {
  const toolMessages = useWorkflowStore(selectToolMessages);
  const executionReport = useWorkflowStore((state) => state.executionReport);
  const isStreaming = useWorkflowStore((state) => state.isStreaming);
  const scrollRef = useAutoScroll<HTMLDivElement>([toolMessages.length, executionReport]);

  return (
    <div className="h-full flex flex-col bg-terminal-panel border-l border-dashed border-terminal-border">
      {/* Header */}
      <div className="border-b border-dashed border-terminal-border px-4 py-3">
        <h2 className="text-sm font-mono font-bold text-terminal-green tracking-widest">
          TOOL ACTIVITY
        </h2>
        <p className="text-[10px] font-mono text-terminal-text-dim mt-0.5">
          {toolMessages.length} call{toolMessages.length !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Tool calls + report */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2">
        {toolMessages.length === 0 && !executionReport ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-terminal-text-dim font-mono text-xs">
              {'> '}no activity_
            </p>
          </div>
        ) : (
          <>
            {toolMessages.map((msg, i) => (
              <ToolCallCard
                key={msg.id}
                message={msg as ToolUseMessage}
                isLatest={isStreaming && i === toolMessages.length - 1}
              />
            ))}
            {executionReport && executionReport.type === 'execution_report' && (
              <ExecutionReportSection report={executionReport as ExecutionReportMessage} />
            )}
          </>
        )}
      </div>

      {/* Metrics */}
      <MetricsBar />
    </div>
  );
}
