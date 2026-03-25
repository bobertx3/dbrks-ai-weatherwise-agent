import { Outlet } from 'react-router-dom';
import { useSession } from '@/contexts/SessionContext';
import { ChatHeader } from '@/components/chat-header';

export default function ChatLayout() {
  const { session, loading } = useSession();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!session?.user) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="mb-4 font-bold text-2xl">Authentication Required</h1>
          <p className="text-muted-foreground">
            Please authenticate using Databricks to access this application.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col">
      <ChatHeader />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
