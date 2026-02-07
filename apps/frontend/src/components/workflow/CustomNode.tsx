import { Handle, Position, NodeProps } from 'reactflow';
import { cn } from '../../utils/cn';
import { Play, Square, CheckCircle } from 'lucide-react';

export function CustomNode({ data, type }: NodeProps) {
  const nodeStyles = {
    start: 'bg-green-100 border-green-500 text-green-900',
    action: 'bg-blue-100 border-blue-500 text-blue-900',
    end: 'bg-red-100 border-red-500 text-red-900',
  };

  const Icon = type === 'start' ? Play : type === 'end' ? CheckCircle : Square;

  return (
    <div
      className={cn(
        'px-4 py-3 rounded-lg border-2 shadow-md min-w-[180px]',
        nodeStyles[type as keyof typeof nodeStyles]
      )}
    >
      {type !== 'start' && <Handle type="target" position={Position.Top} />}
      <div className="flex items-center gap-2">
        <Icon className="w-5 h-5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="font-semibold capitalize">{data.label}</div>
          {data.description && (
            <div className="text-xs mt-1 opacity-75">{data.description}</div>
          )}
        </div>
      </div>
      {type !== 'end' && <Handle type="source" position={Position.Bottom} />}
    </div>
  );
}
