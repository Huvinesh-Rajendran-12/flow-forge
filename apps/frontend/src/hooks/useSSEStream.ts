import { useCallback } from 'react';
import { useWorkflowStore } from '../store/workflowStore';
import { Message, UserMessage } from '../types/api';
import { extractWorkflowFromToolUse, parseWorkflowCode, parseWorkflowJSON } from '../utils/workflowParser';

export function useSSEStream() {
  const { addMessage, setStreaming, setWorkflowGraph, reset, softReset } = useWorkflowStore();

  const startStream = useCallback(
    async (description: string) => {
      const { sessionId, currentWorkflowId } = useWorkflowStore.getState();

      if (sessionId) {
        softReset();
        const userMessage: UserMessage = {
          id: crypto.randomUUID(),
          timestamp: Date.now(),
          type: 'user_message',
          content: description,
        };
        addMessage(userMessage);
      } else {
        reset();
      }

      setStreaming(true);

      const body: Record<string, string> = { description };
      if (sessionId) body.session_id = sessionId;
      if (currentWorkflowId) body.workflow_id = currentWorkflowId;

      try {
        const response = await fetch('/api/workflows/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
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

                // Check if this is a workflow file write operation
                if (message.type === 'tool_use') {
                  const toolInput = message.content.input;
                  const filePath = toolInput.file_path as string;

                  if (filePath?.endsWith('workflow.json')) {
                    const content = (toolInput.content || toolInput.file_contents) as string;
                    if (content) {
                      try {
                        const parsed = JSON.parse(content);
                        const graph = parseWorkflowJSON(parsed);
                        if (graph.nodes.length > 0) {
                          setWorkflowGraph(graph, { workflowName: parsed.name });
                        }
                      } catch {
                        // JSON not valid yet, skip early preview
                      }
                    }
                  } else {
                    const workflowCode = extractWorkflowFromToolUse(toolInput);
                    if (workflowCode) {
                      const graph = parseWorkflowCode(workflowCode);
                      if (graph.nodes.length > 0) {
                        setWorkflowGraph(graph);
                      }
                    }
                  }
                }

                // Handle workflow message type from backend
                if (data.type === 'workflow') {
                  const graph = parseWorkflowJSON(data.content);
                  if (graph.nodes.length > 0) {
                    setWorkflowGraph(graph, { workflowName: data.content.name });
                  }
                }

                // execution_report and workflow_saved are handled by addMessage in the store
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
        if (sessionId) {
          useWorkflowStore.setState({ sessionId: null });
        }
      } finally {
        setStreaming(false);
      }
    },
    [addMessage, setStreaming, setWorkflowGraph, reset, softReset]
  );

  return { startStream };
}
