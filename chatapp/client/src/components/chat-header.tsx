import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { PlusIcon } from 'lucide-react';

export function ChatHeader() {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 flex items-center gap-2 bg-background px-4 py-1.5">
      <span className="font-semibold text-sm tracking-tight">
        Jackson &amp; Jackson
      </span>

      <Button
        variant="outline"
        className="ml-auto h-8 px-2"
        onClick={() => {
          navigate('/');
        }}
      >
        <PlusIcon />
        <span className="md:sr-only">New Chat</span>
      </Button>
    </header>
  );
}
