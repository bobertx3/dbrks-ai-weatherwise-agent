import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { PlusIcon, WorkflowIcon } from 'lucide-react';
import { AgentFlowModal } from '@/components/agent-flow-modal';

export function ChatHeader() {
  const navigate = useNavigate();
  const [flowOpen, setFlowOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 flex items-center gap-2 bg-background px-4 py-1.5">
        <span className="font-semibold text-sm tracking-tight">
          Jackson &amp; Jackson
        </span>

        <Button
          variant="outline"
          className="ml-auto h-8 px-3 gap-1.5"
          onClick={() => setFlowOpen(true)}
        >
          <WorkflowIcon className="h-3.5 w-3.5" />
          <span className="text-xs">Agent Flow</span>
        </Button>

        <Button
          variant="outline"
          className="h-8 px-2"
          onClick={() => {
            navigate('/');
          }}
        >
          <PlusIcon />
          <span className="md:sr-only">New Chat</span>
        </Button>
      </header>

      <AgentFlowModal open={flowOpen} onClose={() => setFlowOpen(false)} />
    </>
  );
}
