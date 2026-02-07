import { useWorkflowStore } from '../../store/workflowStore';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { Loader2 } from 'lucide-react';

export function ChatbotPanel() {
  const isStreaming = useWorkflowStore((state) => state.isStreaming);
  const costUsd = useWorkflowStore((state) => state.costUsd);
  const totalTokens = useWorkflowStore((state) => state.totalTokens);

  return (
    <div className="h-screen flex flex-col bg-white border-r border-gray-200">
      <div className="border-b border-gray-200 p-4">
        <h1 className="text-xl font-bold text-gray-900 mb-1">FlowForge</h1>
        <div className="flex items-center gap-4 text-sm text-gray-600">
          {isStreaming && (
            <div className="flex items-center gap-2 text-blue-600">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Generating...</span>
            </div>
          )}
          {costUsd > 0 && (
            <div className="flex gap-3">
              <span>Cost: ${costUsd.toFixed(4)}</span>
              <span>Tokens: {(totalTokens / 1000).toFixed(1)}K</span>
            </div>
          )}
        </div>
      </div>
      <MessageList />
      <ChatInput />
    </div>
  );
}
