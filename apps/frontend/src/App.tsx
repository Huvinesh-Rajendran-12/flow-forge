import { ChatbotPanel } from './components/chatbot/ChatbotPanel';
import { WorkflowVisualization } from './components/workflow/WorkflowVisualization';

export function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <div className="w-2/5 flex-shrink-0">
        <ChatbotPanel />
      </div>
      <div className="flex-1">
        <WorkflowVisualization />
      </div>
    </div>
  );
}
