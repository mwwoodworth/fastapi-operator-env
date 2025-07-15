"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "react-hot-toast";
import useSWR from "swr";

interface SpeechRecognitionEvent extends Event {
  results: {
    [key: number]: {
      [key: number]: {
        transcript: string;
      };
      isFinal: boolean;
    };
    length: number;
  };
}

declare global {
  interface Window {
    webkitSpeechRecognition: {
      new(): {
        continuous: boolean;
        interimResults: boolean;
        lang: string;
        onstart: () => void;
        onresult: (event: SpeechRecognitionEvent) => void;
        onerror: () => void;
        onend: () => void;
        start: () => void;
      };
    };
  }
}

interface Message {
  id: string;
  type: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

interface SystemStatus {
  status: "online" | "offline" | "maintenance";
  services: {
    assistant: boolean;
    voice: boolean;
    workflow: boolean;
    qa: boolean;
    files: boolean;
  };
  version: string;
  uptime: string;
}

export default function BrainOpsDashboard() {
  const [activeTab, setActiveTab] = useState("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // System status monitoring
  const { data: systemStatus } = useSWR<SystemStatus>(
    "/api/status",
    { refreshInterval: 30000 }
  );

  // WebSocket connection
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/assistant");
    
    ws.onopen = () => {
      setWsConnection(ws);
      toast.success("Connected to BrainOps Assistant");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "message") {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          type: "assistant",
          content: data.content,
          timestamp: new Date(),
          metadata: data.metadata
        }]);
      }
      setIsLoading(false);
    };

    ws.onclose = () => {
      setWsConnection(null);
      toast.error("Disconnected from BrainOps Assistant");
    };

    return () => {
      ws.close();
    };
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (message: string, type: string = "chat") => {
    if (!wsConnection || !message.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: message,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);

    wsConnection.send(JSON.stringify({
      message: message,
      type: type,
      context: { timestamp: new Date().toISOString() }
    }));
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputMessage);
    }
  };

  const toggleVoice = () => {
    setIsVoiceActive(!isVoiceActive);
    if (!isVoiceActive) {
      startVoiceRecognition();
    } else {
      stopVoiceRecognition();
    }
  };

  const startVoiceRecognition = () => {
    if ('webkitSpeechRecognition' in window) {
      const recognition = new window.webkitSpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        toast.success("Voice recognition started");
      };

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const transcript = event.results[event.results.length - 1][0].transcript;
        if (event.results[event.results.length - 1].isFinal) {
          sendMessage(transcript, "voice");
        }
      };

      recognition.onerror = () => {
        toast.error("Voice recognition error");
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } else {
      toast.error("Speech recognition not supported");
    }
  };

  const stopVoiceRecognition = () => {
    setIsListening(false);
    setIsVoiceActive(false);
  };

  const StatusIndicator = ({ status }: { status: boolean }) => (
    <div className={`w-2 h-2 rounded-full ${status ? 'status-online' : 'status-offline'}`} />
  );

  const TabButton = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
    <button
      onClick={onClick}
      className={`px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
        active 
          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' 
          : 'glass-button'
      }`}
    >
      {label}
    </button>
  );

  const ChatInterface = () => (
    <div className="chat-container h-full">
      <div className="chat-messages">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`message-${message.type} animate-fadeIn`}
          >
            <div className="flex justify-between items-start mb-2">
              <span className="font-medium capitalize">{message.type}</span>
              <span className="text-xs text-gray-400">
                {message.timestamp.toLocaleTimeString()}
              </span>
            </div>
            <div className="whitespace-pre-wrap">{message.content}</div>
            {message.metadata && (
              <div className="mt-2 text-xs text-gray-500">
                {JSON.stringify(message.metadata, null, 2)}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message-assistant animate-fadeIn">
            <div className="loading-dots">
              <div className="loading-dot"></div>
              <div className="loading-dot"></div>
              <div className="loading-dot"></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="p-4 border-t border-white/10">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask BrainOps anything..."
              className="chat-input"
              rows={1}
            />
          </div>
          <button
            onClick={toggleVoice}
            className={`glass-button px-4 py-2 ${isVoiceActive ? 'bg-red-500/20 border-red-500/30' : ''}`}
          >
            {isListening ? '🎙️' : '🎤'}
          </button>
          <button
            onClick={() => sendMessage(inputMessage)}
            disabled={!inputMessage.trim() || isLoading}
            className="glass-button px-6 py-2 bg-blue-500/20 border-blue-500/30 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );

  const VoiceInterface = () => (
    <div className="glass-card h-full">
      <div className="mb-6">
        <h3 className="text-xl font-bold mb-2">Voice Interface</h3>
        <p className="text-gray-400">Real-time voice interaction with BrainOps AI</p>
      </div>
      
      <div className="voice-visualizer mb-6">
        <div className={`voice-wave ${isVoiceActive ? 'voice-active' : ''}`}></div>
      </div>
      
      <div className="space-y-4">
        <button
          onClick={toggleVoice}
          className={`w-full glass-button py-4 text-lg ${
            isVoiceActive 
              ? 'bg-red-500/20 border-red-500/30' 
              : 'bg-blue-500/20 border-blue-500/30'
          }`}
        >
          {isVoiceActive ? 'Stop Voice' : 'Start Voice'}
        </button>
        
        <div className="text-center">
          <p className="text-sm text-gray-400">
            Status: {isListening ? 'Listening...' : 'Ready'}
          </p>
        </div>
      </div>
    </div>
  );

  const FileManager = () => (
    <div className="glass-card h-full">
      <div className="mb-6">
        <h3 className="text-xl font-bold mb-2">File Manager</h3>
        <p className="text-gray-400">Browse and manage your files</p>
      </div>
      
      <div className="file-grid">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="file-item">
            <div className="text-2xl mb-2">📄</div>
            <div className="text-sm">document_{i}.txt</div>
            <div className="text-xs text-gray-500">2.5 KB</div>
          </div>
        ))}
      </div>
    </div>
  );

  const WorkflowBuilder = () => (
    <div className="glass-card h-full">
      <div className="mb-6">
        <h3 className="text-xl font-bold mb-2">Workflow Builder</h3>
        <p className="text-gray-400">Create and manage automated workflows</p>
      </div>
      
      <div className="workflow-canvas">
        <div className="workflow-node" style={{ top: '20%', left: '10%' }}>
          Trigger
        </div>
        <div className="workflow-node" style={{ top: '40%', left: '40%' }}>
          Action
        </div>
        <div className="workflow-node" style={{ top: '60%', left: '70%' }}>
          Output
        </div>
      </div>
    </div>
  );

  const TaskDashboard = () => (
    <div className="glass-card h-full">
      <div className="mb-6">
        <h3 className="text-xl font-bold mb-2">Task Dashboard</h3>
        <p className="text-gray-400">Monitor active tasks and processes</p>
      </div>
      
      <div className="space-y-4">
        {[
          { name: "Data Analysis", status: "running", progress: 75 },
          { name: "Report Generation", status: "completed", progress: 100 },
          { name: "Email Processing", status: "pending", progress: 0 }
        ].map((task, i) => (
          <div key={i} className="p-4 bg-white/5 rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="font-medium">{task.name}</span>
              <span className={`px-2 py-1 rounded text-xs ${
                task.status === 'running' ? 'bg-yellow-500/20 text-yellow-300' :
                task.status === 'completed' ? 'bg-green-500/20 text-green-300' :
                'bg-gray-500/20 text-gray-300'
              }`}>
                {task.status}
              </span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div 
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const QADashboard = () => (
    <div className="glass-card h-full">
      <div className="mb-6">
        <h3 className="text-xl font-bold mb-2">QA Dashboard</h3>
        <p className="text-gray-400">Quality assurance and code review</p>
      </div>
      
      <div className="space-y-4">
        <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <h4 className="font-medium text-green-300 mb-2">Code Quality</h4>
          <p className="text-sm text-green-400">All checks passed ✓</p>
        </div>
        
        <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
          <h4 className="font-medium text-yellow-300 mb-2">Security Scan</h4>
          <p className="text-sm text-yellow-400">2 minor issues detected</p>
        </div>
        
        <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
          <h4 className="font-medium text-blue-300 mb-2">Test Coverage</h4>
          <p className="text-sm text-blue-400">85% coverage</p>
        </div>
      </div>
    </div>
  );

  const SettingsPanel = () => (
    <div className="glass-card h-full">
      <div className="mb-6">
        <h3 className="text-xl font-bold mb-2">Settings</h3>
        <p className="text-gray-400">Configure BrainOps AI Assistant</p>
      </div>
      
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">AI Model</label>
          <select className="glass-input w-full">
            <option>GPT-4</option>
            <option>Claude 3</option>
            <option>Custom</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-2">Voice Language</label>
          <select className="glass-input w-full">
            <option>English</option>
            <option>Spanish</option>
            <option>French</option>
          </select>
        </div>
        
        <div>
          <label className="flex items-center">
            <input type="checkbox" className="mr-2" />
            <span className="text-sm">Enable notifications</span>
          </label>
        </div>
        
        <div>
          <label className="flex items-center">
            <input type="checkbox" className="mr-2" />
            <span className="text-sm">Auto-save conversations</span>
          </label>
        </div>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case "chat": return <ChatInterface />;
      case "voice": return <VoiceInterface />;
      case "files": return <FileManager />;
      case "workflows": return <WorkflowBuilder />;
      case "tasks": return <TaskDashboard />;
      case "qa": return <QADashboard />;
      case "settings": return <SettingsPanel />;
      default: return <ChatInterface />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-white/10 backdrop-blur-sm">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
                <span className="text-white font-bold">B</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gradient">BrainOps AI Assistant</h1>
                <p className="text-sm text-gray-400">AI Chief of Staff - Full Operational Control</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* System Status */}
              <div className="flex items-center space-x-2 glass px-3 py-2 rounded-lg">
                <StatusIndicator status={systemStatus?.services?.assistant ?? false} />
                <span className="text-sm">
                  {systemStatus?.status ?? 'offline'}
                </span>
              </div>
              
              {/* Version */}
              <div className="text-sm text-gray-400">
                v{systemStatus?.version ?? '1.0.0'}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {/* Tab Navigation */}
        <nav className="flex space-x-4 mb-8 overflow-x-auto pb-2">
          <TabButton label="Chat" active={activeTab === "chat"} onClick={() => setActiveTab("chat")} />
          <TabButton label="Voice" active={activeTab === "voice"} onClick={() => setActiveTab("voice")} />
          <TabButton label="Files" active={activeTab === "files"} onClick={() => setActiveTab("files")} />
          <TabButton label="Workflows" active={activeTab === "workflows"} onClick={() => setActiveTab("workflows")} />
          <TabButton label="Tasks" active={activeTab === "tasks"} onClick={() => setActiveTab("tasks")} />
          <TabButton label="QA" active={activeTab === "qa"} onClick={() => setActiveTab("qa")} />
          <TabButton label="Settings" active={activeTab === "settings"} onClick={() => setActiveTab("settings")} />
        </nav>

        {/* Tab Content */}
        <div className="h-[calc(100vh-200px)] animate-fadeIn">
          {renderTabContent()}
        </div>
      </main>
    </div>
  );
}
