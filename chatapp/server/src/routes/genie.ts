import { Router, type Request, type Response } from 'express';
import { getDatabricksToken } from '@chat-template/auth';
import { getHostUrl } from '@chat-template/utils';
import { authMiddleware, requireAuth } from '../middleware/auth';

export const genieRouter = Router();
genieRouter.use(authMiddleware);

function getSpaceId(): string {
  const spaceId = process.env.DATABRICKS_GENIE_SPACE_ID;
  if (!spaceId) {
    throw new Error('DATABRICKS_GENIE_SPACE_ID is not configured');
  }
  return spaceId;
}

async function genieApi(
  method: string,
  path: string,
  body?: unknown,
): Promise<any> {
  const token = await getDatabricksToken();
  const host = getHostUrl();

  const response = await fetch(`${host}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Genie API ${response.status}: ${text}`);
  }

  return response.json();
}

// Start a new conversation (sends the first question)
genieRouter.post(
  '/start-conversation',
  requireAuth,
  async (req: Request, res: Response) => {
    try {
      const spaceId = getSpaceId();
      const { content } = req.body;
      const result = await genieApi(
        'POST',
        `/api/2.0/genie/spaces/${spaceId}/start-conversation`,
        { content },
      );
      res.json(result);
    } catch (error) {
      console.error('[genie] Start conversation error:', error);
      res.status(500).json({
        error: 'Failed to start conversation',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  },
);

// Send a follow-up message in an existing conversation
genieRouter.post(
  '/conversations/:conversationId/messages',
  requireAuth,
  async (req: Request, res: Response) => {
    try {
      const spaceId = getSpaceId();
      const { conversationId } = req.params;
      const { content } = req.body;

      const result = await genieApi(
        'POST',
        `/api/2.0/genie/spaces/${spaceId}/conversations/${conversationId}/messages`,
        { content },
      );
      res.json(result);
    } catch (error) {
      console.error('[genie] Send message error:', error);
      res.status(500).json({
        error: 'Failed to send message',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  },
);

// Poll message status
genieRouter.get(
  '/conversations/:conversationId/messages/:messageId',
  requireAuth,
  async (req: Request, res: Response) => {
    try {
      const spaceId = getSpaceId();
      const { conversationId, messageId } = req.params;

      const result = await genieApi(
        'GET',
        `/api/2.0/genie/spaces/${spaceId}/conversations/${conversationId}/messages/${messageId}`,
      );
      res.json(result);
    } catch (error) {
      console.error('[genie] Get message error:', error);
      res.status(500).json({
        error: 'Failed to get message',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  },
);

// Get query result
genieRouter.get(
  '/conversations/:conversationId/messages/:messageId/query-result',
  requireAuth,
  async (req: Request, res: Response) => {
    try {
      const spaceId = getSpaceId();
      const { conversationId, messageId } = req.params;

      const result = await genieApi(
        'GET',
        `/api/2.0/genie/spaces/${spaceId}/conversations/${conversationId}/messages/${messageId}/query-result`,
      );
      res.json(result);
    } catch (error) {
      console.error('[genie] Get query result error:', error);
      res.status(500).json({
        error: 'Failed to get query result',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  },
);

// Get Genie config (for frontend to know if Genie is available)
genieRouter.get(
  '/config',
  requireAuth,
  async (_req: Request, res: Response) => {
    const spaceId = process.env.DATABRICKS_GENIE_SPACE_ID;
    res.json({ enabled: !!spaceId });
  },
);
