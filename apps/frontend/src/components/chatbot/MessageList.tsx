import { useWorkflowStore } from '../../store/workflowStore';
import { useAutoScroll } from '../../hooks/useAutoScroll';
import { MessageItem } from './MessageItem';

export function MessageList() {
  const messages = useWorkflowStore((state) => state.messages);
  const scrollRef = useAutoScroll<HTMLDivElement>([messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <p className="text-lg font-medium mb-2">No messages yet</p>
          <p className="text-sm">Describe a workflow to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  );
}
