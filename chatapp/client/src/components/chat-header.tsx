import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  WorkflowIcon,
  MessageSquareIcon,
  LayoutDashboardIcon,
  SparklesIcon,
} from 'lucide-react';
import { AgentFlowModal } from '@/components/agent-flow-modal';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', label: 'Agent', icon: MessageSquareIcon, matchPaths: ['/', '/chat'] },
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboardIcon, matchPaths: ['/dashboard'] },
  { path: '/genie', label: 'Ask Genie', icon: SparklesIcon, matchPaths: ['/genie'] },
];

export function ChatHeader() {
  const navigate = useNavigate();
  const location = useLocation();
  const [flowOpen, setFlowOpen] = useState(false);

  const isActive = (item: (typeof navItems)[0]) =>
    item.matchPaths.some((p) =>
      p === '/' ? location.pathname === '/' || location.pathname.startsWith('/chat') : location.pathname.startsWith(p),
    );

  return (
    <>
      <header className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background px-4 py-1.5">
        <span className="font-semibold text-sm tracking-tight">
          Jackson &amp; Jackson
        </span>

        <nav className="ml-4 flex items-center gap-1">
          {navItems.map((item) => (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
                isActive(item)
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant="outline"
            className="h-8 px-3 gap-1.5"
            onClick={() => setFlowOpen(true)}
          >
            <WorkflowIcon className="h-3.5 w-3.5" />
            <span className="text-xs">Agent Flow</span>
          </Button>
        </div>
      </header>

      <AgentFlowModal open={flowOpen} onClose={() => setFlowOpen(false)} />
    </>
  );
}
