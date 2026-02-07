import { useState, FormEvent } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';
import { useSSEStream } from '../../hooks/useSSEStream';
import { Button } from '../ui/Button';
import { Send } from 'lucide-react';

export function ChatInput() {
  const [description, setDescription] = useState('');
  const isStreaming = useWorkflowStore((state) => state.isStreaming);
  const { startStream } = useSSEStream();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!description.trim() || isStreaming) {
      return;
    }

    await startStream(description.trim());
    setDescription('');
  };

  return (
    <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4">
      <div className="flex gap-2">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe your workflow (e.g., 'Create an employee onboarding workflow')"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          rows={3}
          disabled={isStreaming}
        />
        <Button type="submit" disabled={!description.trim() || isStreaming}>
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </form>
  );
}
