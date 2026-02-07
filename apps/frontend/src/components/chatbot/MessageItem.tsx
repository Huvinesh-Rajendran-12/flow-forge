import { Message } from '../../types/api';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Wrench, CheckCircle, XCircle, Folder } from 'lucide-react';

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  switch (message.type) {
    case 'text':
      return (
        <div className="py-2 px-4 bg-gray-50 border-l-4 border-blue-500 rounded">
          <p className="text-gray-800 whitespace-pre-wrap">{message.content}</p>
        </div>
      );

    case 'tool_use':
      return (
        <Card className="bg-blue-50 border-blue-200">
          <div className="flex items-start gap-3">
            <Wrench className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="default">{message.content.tool}</Badge>
              </div>
              <div className="text-sm text-gray-700">
                <pre className="bg-white p-2 rounded border border-blue-200 overflow-x-auto text-xs">
                  {JSON.stringify(message.content.input, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </Card>
      );

    case 'result':
      return (
        <Card className="bg-green-50 border-green-200">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h4 className="font-semibold text-green-900 mb-2">Workflow Complete</h4>
              <div className="flex gap-4 text-sm text-green-800">
                <span>Cost: ${message.content.cost_usd.toFixed(4)}</span>
                <span>
                  Tokens: {(message.content.usage.total_tokens / 1000).toFixed(1)}K
                </span>
              </div>
            </div>
          </div>
        </Card>
      );

    case 'error':
      return (
        <Card className="bg-red-50 border-red-200">
          <div className="flex items-start gap-3">
            <XCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h4 className="font-semibold text-red-900 mb-1">Error</h4>
              <p className="text-sm text-red-800">{message.content}</p>
            </div>
          </div>
        </Card>
      );

    case 'workspace':
      return (
        <Card className="bg-purple-50 border-purple-200">
          <div className="flex items-start gap-3">
            <Folder className="w-5 h-5 text-purple-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <h4 className="font-semibold text-purple-900 mb-1">Workspace</h4>
              <p className="text-sm text-purple-800 font-mono truncate">
                {message.content.path}
              </p>
            </div>
          </div>
        </Card>
      );

    default:
      return null;
  }
}
