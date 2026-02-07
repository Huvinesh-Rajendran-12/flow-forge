import { useCallback } from 'react';
import { useWorkflowStore } from '../store/workflowStore';
import { Message } from '../types/api';
import { extractWorkflowFromToolUse, parseWorkflowCode, parseWorkflowJSON } from '../utils/workflowParser';

export function useSSEStream() {
  const { addMessage, setStreaming, setWorkflowGraph, reset } = useWorkflowStore();

  const startStream = useCallback(
    async (description: string) => {
      reset();
      setStreaming(true);

      try {
        const response = await fetch('/api/workflows/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ description }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('No response body');
        }

        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');

          // Keep the last incomplete line in the buffer
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                const message: Message = {
                  id: crypto.randomUUID(),
                  timestamp: Date.now(),
                  type: data.type,
                  content: data.content,
                } as Message;

                addMessage(message);

                // Check if this is a workflow.py write operation
                if (message.type === 'tool_use') {
                  const workflowCode = extractWorkflowFromToolUse(message.content.input);
                  if (workflowCode) {
                    const graph = parseWorkflowCode(workflowCode);
                    if (graph.nodes.length > 0) {
                      setWorkflowGraph(graph);
                    }
                  }
                }

                // Handle workflow message type from backend
                if (message.type === 'workflow') {
                  const graph = parseWorkflowJSON(message.content);
                  if (graph.nodes.length > 0) {
                    setWorkflowGraph(graph);
                  }
                }
              } catch (error) {
                console.error('Error parsing SSE message:', error, line);
              }
            }
          }
        }
      } catch (error) {
        const errorMessage: Message = {
          id: crypto.randomUUID(),
          timestamp: Date.now(),
          type: 'error',
          content: error instanceof Error ? error.message : 'Unknown error occurred',
        };
        addMessage(errorMessage);
      } finally {
        setStreaming(false);
      }
    },
    [addMessage, setStreaming, setWorkflowGraph, reset]
  );

  return { startStream };
}
