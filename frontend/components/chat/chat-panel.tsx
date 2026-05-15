"use client";

import { useState, useRef, useEffect } from "react";
import { useApp } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageCircle, X, Send, Loader2 } from "lucide-react";

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

interface Message {
  role: "user" | "assistant";
  content: string;
  usage?: { input_tokens: number; output_tokens: number };
}

export function ChatPanel() {
  const { projectId, revision } = useApp();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 프로젝트 전환 시 대화 초기화
  useEffect(() => {
    setMessages([]);
  }, [projectId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Message = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    // Context Rot 방지: 최근 10턴(20메시지)만 API에 전달
    const MAX_CONTEXT_MESSAGES = 20;
    const contextMessages = newMessages.slice(-MAX_CONTEXT_MESSAGES).map(({ role, content }) => ({ role, content }));

    try {
      const res = await fetch(`${FASTAPI}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          projectId,
          revision,
          messages: contextMessages,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages([...newMessages, { role: "assistant", content: data.content, usage: data.usage }]);
      } else {
        setMessages([...newMessages, { role: "assistant", content: "오류가 발생했습니다. 다시 시도해 주세요." }]);
      }
    } catch {
      setMessages([...newMessages, { role: "assistant", content: "서버에 연결할 수 없습니다." }]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:scale-105 transition-transform"
      >
        <MessageCircle className="h-5 w-5" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 h-[500px] rounded-xl border bg-card shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">AI 어시스턴트</span>
          <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">Sonnet</span>
        </div>
        <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-sm text-muted-foreground mt-8">
            {projectId ? (
              <>
                <p className="font-medium">프로젝트에 대해 질문하세요</p>
                <p className="mt-1 text-xs">예: &quot;매출 이익률이 몇 %야?&quot;</p>
                <p className="text-xs">&quot;간접비 계산 근거 알려줘&quot;</p>
                <p className="text-xs">&quot;0차 대비 1차 변경점 요약해줘&quot;</p>
              </>
            ) : (
              <p className="font-medium">프로젝트를 먼저 선택해 주세요</p>
            )}
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
              msg.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground"
            }`}>
              {msg.content}
              {msg.usage && (
                <div className="text-[9px] text-muted-foreground mt-1 opacity-60">
                  {msg.usage.input_tokens + msg.usage.output_tokens} tokens
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-lg px-3 py-2">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t p-3 flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={projectId ? "질문을 입력하세요..." : "프로젝트를 선택하세요"}
          className="text-sm"
          disabled={loading || !projectId}
        />
        <Button size="icon" onClick={send} disabled={loading || !input.trim() || !projectId}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
