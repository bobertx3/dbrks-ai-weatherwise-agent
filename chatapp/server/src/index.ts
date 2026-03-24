// Load environment variables FIRST before any other imports
import './env';

import express, {
  type Request,
  type Response,
  type NextFunction,
  type Express,
} from 'express';
import cors from 'cors';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { chatRouter } from './routes/chat';
import { historyRouter } from './routes/history';
import { sessionRouter } from './routes/session';
import { messagesRouter } from './routes/messages';
import { configRouter } from './routes/config';
import { feedbackRouter } from './routes/feedback';
import { ChatSDKError } from '@chat-template/core/errors';

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app: Express = express();
const isDevelopment = process.env.NODE_ENV !== 'production';
// Either let PORT be set by env or use 3001 for development and 3000 for production
// The CHAT_APP_PORT can be used to override the port for the chat app.
const PORT =
  process.env.CHAT_APP_PORT ||
  process.env.PORT ||
  (isDevelopment ? 3001 : 3000);

// CORS configuration
app.use(
  cors({
    origin: isDevelopment ? 'http://localhost:3000' : true,
    credentials: true,
  }),
);

// Body parsing middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Health check endpoint
app.get('/ping', (_req, res) => {
  res.status(200).send('pong');
});

// API routes
app.use('/api/chat', chatRouter);
app.use('/api/history', historyRouter);
app.use('/api/session', sessionRouter);
app.use('/api/messages', messagesRouter);
app.use('/api/config', configRouter);
app.use('/api/feedback', feedbackRouter);

// Agent backend proxy (optional)
// If API_PROXY is set, proxy /invocations requests to the agent backend
const agentBackendUrl = process.env.API_PROXY;
if (agentBackendUrl) {
  console.log(`✅ Proxying /invocations to ${agentBackendUrl}`);
  app.all('/invocations', async (req: Request, res: Response) => {
    try {
      const forwardHeaders = { ...req.headers } as Record<string, string>;
      forwardHeaders['content-length'] = undefined;

      const response = await fetch(agentBackendUrl, {
        method: req.method,
        headers: forwardHeaders,
        body:
          req.method !== 'GET' && req.method !== 'HEAD'
            ? JSON.stringify(req.body)
            : undefined,
      });

      // Copy status and headers
      res.status(response.status);
      response.headers.forEach((value, key) => {
        res.setHeader(key, value);
      });

      // Stream the response body
      if (response.body) {
        const reader = response.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          res.write(value);
        }
      }
      res.end();
    } catch (error) {
      console.error('[/invocations proxy] Error:', error);
      res.status(502).json({
        error: 'Proxy error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  });
}

// Serve static files in production
if (!isDevelopment) {
  const clientBuildPath = path.join(__dirname, '../../client/dist');
  app.use(express.static(clientBuildPath));

  // SPA fallback - serve index.html for all non-API routes
  app.get(/^\/(?!api).*/, (_req, res) => {
    res.sendFile(path.join(clientBuildPath, 'index.html'));
  });
}

// Error handling middleware
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('Error:', err);

  if (err instanceof ChatSDKError) {
    const response = err.toResponse();
    return res.status(response.status).json(response.json);
  }

  res.status(500).json({
    error: 'Internal Server Error',
    message: isDevelopment ? err.message : 'An unexpected error occurred',
  });
});

app.listen(PORT, () => {
  console.log(`Backend server is running on http://localhost:${PORT}`);
  console.log(`Environment: ${isDevelopment ? 'development' : 'production'}`);
});

export default app;
