# MyRoofGenius Frontend Integration Guide

## Overview

This guide details how to connect the MyRoofGenius Next.js frontend to the BrainOps FastAPI backend, enabling full AI-powered roofing estimation capabilities.

## Backend Endpoints

### Base URL
- Development: `http://localhost:8000`
- Production: `https://api.brainops.com`

### Authentication Endpoints
- `POST /auth/register` - User registration
- `POST /auth/token` - OAuth2 token login
- `POST /auth/login` - Login with user details
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Get current user
- `POST /auth/logout` - Logout user

### AI Streaming Endpoints
- `POST /ai/chat/stream` - SSE streaming chat
- `WS /ai/chat/ws` - WebSocket streaming
- `GET /ai/models` - List available models
- `GET /ai/sessions` - List user sessions

### RAG System Endpoints
- `POST /rag/documents` - Create document
- `POST /rag/search` - Search documents
- `POST /rag/context` - Generate context
- `GET /rag/documents` - List documents

## Frontend Configuration

### 1. Update Environment Variables

```env
# /myroofgenius-app/.env.local
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_WS_BASE=ws://localhost:8000
```

### 2. Create API Client

```typescript
// /myroofgenius-app/lib/api-client.ts
import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

class APIClient {
  private token: string | null = null;
  
  constructor() {
    // Load token from localStorage
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('access_token');
    }
  }
  
  private get headers() {
    return {
      'Content-Type': 'application/json',
      ...(this.token ? { 'Authorization': `Bearer ${this.token}` } : {})
    };
  }
  
  async login(username: string, password: string) {
    const response = await axios.post(`${API_BASE}/auth/login`, {
      username,
      password
    });
    
    this.token = response.data.access_token;
    localStorage.setItem('access_token', this.token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    
    return response.data;
  }
  
  async register(username: string, email: string, password: string) {
    const response = await axios.post(`${API_BASE}/auth/register`, {
      username,
      email,
      password
    });
    
    return response.data;
  }
  
  async streamChat(message: string, model: string = 'claude-3-opus') {
    const response = await fetch(`${API_BASE}/ai/chat/stream`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        message,
        model,
        stream: true
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.body;
  }
  
  async searchDocuments(query: string, category?: string) {
    const response = await axios.post(
      `${API_BASE}/rag/search`,
      {
        query,
        category,
        search_type: 'hybrid'
      },
      { headers: this.headers }
    );
    
    return response.data;
  }
  
  connectWebSocket() {
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_BASE}/ai/chat/ws?token=${this.token}`;
    return new WebSocket(wsUrl);
  }
}

export const apiClient = new APIClient();
```

### 3. Update Authentication Context

```typescript
// /myroofgenius-app/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';

interface AuthContextType {
  user: any | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState(null);
  
  const login = async (username: string, password: string) => {
    const data = await apiClient.login(username, password);
    setUser(data.user);
  };
  
  const register = async (username: string, email: string, password: string) => {
    await apiClient.register(username, email, password);
    await login(username, password);
  };
  
  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };
  
  return (
    <AuthContext.Provider value={{
      user,
      login,
      register,
      logout,
      isAuthenticated: !!user
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

### 4. Update AI Chat Component

```typescript
// /myroofgenius-app/components/AIChat.tsx
import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';

export function AIChat() {
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  
  const sendMessage = async () => {
    if (!input.trim()) return;
    
    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    
    try {
      const stream = await apiClient.streamChat(input);
      const reader = stream!.getReader();
      const decoder = new TextDecoder();
      
      let assistantMessage = { role: 'assistant', content: '' };
      setMessages(prev => [...prev, assistantMessage]);
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                assistantMessage.content += data.content;
                setMessages(prev => [
                  ...prev.slice(0, -1),
                  { ...assistantMessage }
                ]);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsStreaming(false);
    }
  };
  
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl p-4 rounded-lg ${
              msg.role === 'user' ? 'bg-primary/10' : 'bg-glass'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>
      
      <div className="p-4 border-t border-glass-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            className="flex-1 glass-input"
            placeholder="Ask about roofing..."
            disabled={isStreaming}
          />
          <button
            onClick={sendMessage}
            disabled={isStreaming}
            className="glass-button"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 5. WebSocket Integration

```typescript
// /myroofgenius-app/hooks/useWebSocket.ts
import { useEffect, useRef, useState } from 'react';
import { apiClient } from '@/lib/api-client';

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  
  useEffect(() => {
    const connect = () => {
      try {
        ws.current = apiClient.connectWebSocket();
        
        ws.current.onopen = () => {
          console.log('WebSocket connected');
          setIsConnected(true);
        };
        
        ws.current.onmessage = (event) => {
          const data = JSON.parse(event.data);
          setMessages(prev => [...prev, data]);
        };
        
        ws.current.onclose = () => {
          console.log('WebSocket disconnected');
          setIsConnected(false);
          // Reconnect after 3 seconds
          setTimeout(connect, 3000);
        };
        
        ws.current.onerror = (error) => {
          console.error('WebSocket error:', error);
        };
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
      }
    };
    
    connect();
    
    return () => {
      ws.current?.close();
    };
  }, []);
  
  const sendMessage = (message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };
  
  return { isConnected, messages, sendMessage };
}
```

### 6. RAG Integration

```typescript
// /myroofgenius-app/components/DocumentSearch.tsx
import { useState } from 'react';
import { apiClient } from '@/lib/api-client';

export function DocumentSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
  const search = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    try {
      const data = await apiClient.searchDocuments(query, 'roofing');
      setResults(data);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && search()}
          placeholder="Search roofing documents..."
          className="flex-1 glass-input"
        />
        <button onClick={search} disabled={loading} className="glass-button">
          Search
        </button>
      </div>
      
      <div className="space-y-2">
        {results.map((result) => (
          <div key={result.id} className="glass-card p-4">
            <h3 className="font-semibold">{result.title}</h3>
            <p className="text-sm text-text-secondary mt-1">{result.snippet}</p>
            <div className="flex gap-2 mt-2">
              <span className="text-xs bg-primary/10 px-2 py-1 rounded">
                {result.category}
              </span>
              <span className="text-xs text-text-secondary">
                Score: {(result.score * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## API Routes Updates

### Update Next.js API Routes

```typescript
// /myroofgenius-app/app/api/claude/route.ts
import { NextRequest, NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const token = req.headers.get('authorization');
    
    // Forward to FastAPI backend
    const response = await fetch(`${API_BASE}/ai/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token || ''
      },
      body: JSON.stringify(body)
    });
    
    // Return streaming response
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
      }
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

## Testing Integration

### 1. Start Backend
```bash
cd /path/to/fastapi-backend
docker-compose up -d
```

### 2. Start Frontend
```bash
cd /path/to/myroofgenius-app
npm run dev
```

### 3. Test Authentication
1. Navigate to http://localhost:3000/signup
2. Create a new account
3. Verify token is stored in localStorage
4. Check that protected routes work

### 4. Test AI Chat
1. Navigate to dashboard
2. Open AI chat
3. Send a message
4. Verify streaming response

### 5. Test Document Search
1. Upload a document via API
2. Search for it in frontend
3. Verify results display correctly

## Production Deployment

### 1. Update Frontend Environment
```env
NEXT_PUBLIC_API_BASE=https://api.brainops.com
NEXT_PUBLIC_WS_BASE=wss://api.brainops.com
```

### 2. Configure CORS
Ensure backend allows frontend domain:
```python
# Backend CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myroofgenius.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. SSL/TLS
Both frontend and backend must use HTTPS in production.

## Troubleshooting

### CORS Issues
- Verify backend CORS configuration
- Check browser console for errors
- Ensure credentials are included in requests

### Authentication Failures
- Check token expiration
- Verify JWT secret matches
- Test token refresh flow

### WebSocket Connection
- Ensure WSS protocol in production
- Check firewall rules
- Verify token in query string

### SSE Streaming
- Check Content-Type headers
- Verify proxy configuration
- Test with curl first

---

**Integration Version**: 1.0
**Last Updated**: January 2025