import { ExecutionReportMessage } from '../../types/api';
import { Badge } from '../ui/Badge';

interface ExecutionReportSectionProps {
  report: ExecutionReportMessage;
}

export function ExecutionReportSection({ report }: ExecutionReportSectionProps) {
  const { successful, failed, skipped, trace } = report.content.report;
  const steps = trace?.steps ?? [];

  return (
    <div className="border border-dashed border-terminal-border rounded p-3 bg-terminal-card">
      <div className="text-[10px] font-mono text-terminal-text-dim uppercase tracking-wider mb-2">
        Execution Report (attempt {report.content.attempt})
      </div>

      {/* Summary bar */}
      <div className="flex gap-3 text-xs font-mono mb-3">
        <span className="text-terminal-green-muted">PASS: {successful}</span>
        <span className="text-terminal-red">FAIL: {failed}</span>
        <span className="text-terminal-text-dim">SKIP: {skipped}</span>
      </div>

      {/* Step traces */}
      <div className="space-y-1">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
            <Badge
              variant={step.status === 'success' ? 'success' : step.status === 'failed' ? 'error' : 'default'}
            >
              {step.status === 'success' ? 'PASS' : step.status === 'failed' ? 'FAIL' : 'SKIP'}
            </Badge>
            <span className="text-terminal-text truncate">{step.node_id}</span>
            <span className="text-terminal-text-dim truncate">{step.service}.{step.action}</span>
            {step.error && (
              <span className="text-terminal-red truncate ml-auto max-w-[120px]" title={step.error}>
                {step.error}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
