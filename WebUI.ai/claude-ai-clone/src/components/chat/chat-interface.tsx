"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { ClaudeLogo, ClaudeTextLogo } from "@/components/claude-logo";
import { Menu, X, PlusCircle, Send, ChevronLeft, User } from "lucide-react";

// Define message type
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
};

// Mock data for conversation history
const mockConversations = [
  { id: "1", title: "Brainstorming Session", date: "2 days ago" },
  { id: "2", title: "Code Review Help", date: "3 days ago" },
  { id: "3", title: "Marketing Strategy", date: "1 week ago" },
  { id: "4", title: "Essay Outline", date: "2 weeks ago" },
];

// Mock messages for the current conversation
const initialMessages: Message[] = [
  {
    id: "1",
    role: "assistant",
    content: "Hello! I'm Claude, an AI assistant created by Anthropic. How can I help you today?",
    timestamp: new Date(Date.now() - 60000).toISOString()
  },
];

export function ChatInterface() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    // Simulate assistant response after a delay
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `I understand you're asking about "${inputValue}". This is a simulated response from Claude, as this is just a UI demo. In a real implementation, this would connect to the actual Claude API to provide thoughtful and helpful responses.`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile menu button */}
      <button
        type="button"
        className="md:hidden absolute top-4 left-4 z-40"
        onClick={() => setMobileMenuOpen(true)}
      >
        <Menu className="h-6 w-6" />
        <span className="sr-only">Open sidebar</span>
      </button>

      {/* Mobile sidebar */}
      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent side="left" className="p-0 w-[280px]">
          <ChatSidebar onClose={() => setMobileMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Desktop sidebar */}
      <div className="hidden md:flex md:w-[280px] border-r border-claude-border flex-shrink-0">
        <ChatSidebar />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col h-full">
        {/* Chat header */}
        <header className="border-b border-claude-border py-3 px-4 flex items-center">
          <Button
            variant="ghost"
            size="icon"
            asChild
            className="mr-2 hidden md:flex"
          >
            <Link href="/">
              <ChevronLeft className="h-5 w-5" />
              <span className="sr-only">Back to home</span>
            </Link>
          </Button>

          <div className="flex-1">
            <h1 className="text-lg font-medium">New Chat</h1>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-claude-muted bg-claude-bg px-3 py-1 rounded-full">
              Using limited free plan
            </span>
            <Button variant="outline" size="sm" asChild>
              <Link href="/pricing">Upgrade</Link>
            </Button>
          </div>
        </header>

        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6" id="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.role === "assistant" ? "" : "justify-end"
              }`}
            >
              {message.role === "assistant" && (
                <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-claude-bg">
                  <ClaudeLogo size={20} />
                </div>
              )}

              <div
                className={`max-w-3xl p-4 rounded-xl ${
                  message.role === "assistant"
                    ? "bg-white border border-claude-border"
                    : "bg-claude-bg border border-claude-border"
                }`}
              >
                <div className="prose prose-sm">
                  <p>{message.content}</p>
                </div>
              </div>

              {message.role === "user" && (
                <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-claude-bg border border-claude-border">
                  <User size={16} />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-claude-bg">
                <ClaudeLogo size={20} />
              </div>

              <div className="max-w-3xl p-4 rounded-xl bg-white border border-claude-border">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 bg-claude-sunburst rounded-full animate-pulse" />
                  <div className="h-2 w-2 bg-claude-sunburst rounded-full animate-pulse" style={{ animationDelay: "0.2s" }} />
                  <div className="h-2 w-2 bg-claude-sunburst rounded-full animate-pulse" style={{ animationDelay: "0.4s" }} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Suggestions or examples */}
        {messages.length === 1 && !isLoading && (
          <div className="px-4 py-6">
            <h2 className="text-center text-sm font-medium mb-4">
              Get started with an example below
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl mx-auto">
              <Button
                variant="outline"
                className="justify-start text-left h-auto py-3 px-4"
                onClick={() => {
                  setInputValue("Summarize the key features of Claude AI");
                  setTimeout(() => handleSendMessage(), 100);
                }}
              >
                <span>Summarize the key features of Claude AI</span>
              </Button>

              <Button
                variant="outline"
                className="justify-start text-left h-auto py-3 px-4"
                onClick={() => {
                  setInputValue("Generate a content calendar for a tech blog");
                  setTimeout(() => handleSendMessage(), 100);
                }}
              >
                <span>Generate a content calendar for a tech blog</span>
              </Button>

              <Button
                variant="outline"
                className="justify-start text-left h-auto py-3 px-4"
                onClick={() => {
                  setInputValue("Help me debug this code: function sum(a, b) { return a - b; }");
                  setTimeout(() => handleSendMessage(), 100);
                }}
              >
                <span>Help me debug some code</span>
              </Button>

              <Button
                variant="outline"
                className="justify-start text-left h-auto py-3 px-4"
                onClick={() => {
                  setInputValue("Write a short poem about artificial intelligence");
                  setTimeout(() => handleSendMessage(), 100);
                }}
              >
                <span>Write a short poem about AI</span>
              </Button>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-claude-border p-4">
          <div className="max-w-3xl mx-auto">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex gap-2 items-end"
            >
              <div className="relative flex-1">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="How can Claude help you today?"
                  className="min-h-[50px] py-6 pr-12 rounded-xl resize-none"
                />
                <Button
                  type="submit"
                  variant="ghost"
                  size="icon"
                  disabled={!inputValue.trim() || isLoading}
                  className="absolute right-2 bottom-1.5"
                >
                  <Send className="h-5 w-5" />
                  <span className="sr-only">Send message</span>
                </Button>
              </div>
            </form>

            <div className="mt-2 text-xs text-center text-claude-muted">
              <span>Claude can make mistakes. Please double-check responses.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Sidebar component
function ChatSidebar({ onClose }: { onClose?: () => void } = {}) {
  return (
    <div className="h-full flex flex-col bg-claude-bg">
      <div className="p-4 flex items-center justify-between">
        <Link href="/" className="flex items-center">
          <ClaudeTextLogo logoSize={24} />
        </Link>

        {onClose && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="md:hidden"
          >
            <X className="h-5 w-5" />
            <span className="sr-only">Close sidebar</span>
          </Button>
        )}
      </div>

      <div className="p-4">
        <Button className="w-full justify-start gap-2" asChild>
          <Link href="/chat">
            <PlusCircle className="h-4 w-4" />
            Start new chat
          </Link>
        </Button>
      </div>

      <Separator />

      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-1 px-2 py-2">
          <h3 className="text-xs font-medium text-claude-muted px-2 py-1">
            Recent conversations
          </h3>

          <div className="space-y-1">
            {mockConversations.map((convo) => (
              <Button
                key={convo.id}
                variant="ghost"
                className="w-full justify-start text-left h-auto py-2"
                asChild
              >
                <Link href={`/chat/${convo.id}`}>
                  <div className="truncate flex-1">{convo.title}</div>
                  <div className="text-xs text-claude-muted ml-2">
                    {convo.date}
                  </div>
                </Link>
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-4 border-t border-claude-border mt-auto">
        <div className="flex items-center justify-between">
          <div className="text-sm">Free plan</div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/settings">Settings</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
