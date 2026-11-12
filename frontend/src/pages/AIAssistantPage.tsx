import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, Loader2, Cpu, ShieldCheck, FileText, Bot, AlertTriangle,
  Copy, Check, RotateCcw, Trash2, Download,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { AiModeBadge } from '../components/AiModeBadge';
import { Markdown } from '../components/Markdown';

type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
  status?: string;
  model?: string;
  llm_error?: any;
  at: Date;
  failed?: boolean;
  retryQuestion?: string;
};

const GREETING: ChatMessage = {
  role: 'assistant',
  content:
    'Hello. I am the **LexSecure Investigative Assistant** — a permission-aware ' +
    'retrieval system for case evidence.\n\n' +
    'I can help you:\n' +
    '- **Summarize findings** from forensic reports, statements and charge sheets\n' +
    '- **Recall testimony** and correlate exhibits across documents\n' +
    '- **Explain charges** and the evidence supporting them\n\n' +
    'I answer only from documents within your clearance, and every claim carries ' +
    'a source citation. Ask a question to begin.',
  sources: [],
  at: new Date(),
};

const formatTime = (d: Date) =>
  d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export const AIAssistantPage = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const scrollEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const copyTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isLoading]);

  useEffect(() => {
    if (!isLoading) return;
    setElapsed(0);
    const started = Date.now();
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, [isLoading]);

  useEffect(() => () => window.clearTimeout(copyTimer.current), []);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = useCallback(async (question: string) => {
    const q = question.trim();
    if (!q || isLoading) return;

    setMessages(prev => [...prev, { role: 'user', content: q, at: new Date() }]);
    setInput('');
    setIsLoading(true);
    if (inputRef.current) inputRef.current.style.height = 'auto';

    try {
      const res = await apiClient.post('/ai/ask', { question: q });
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.answer,
        sources: res.data.sources || [],
        status: res.data.status,
        model: res.data.model,
        llm_error: res.data.llm_error || null,
        at: new Date(),
      }]);
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ||
        (err?.response?.status ? `Request failed (HTTP ${err.response.status}).` : 'Could not reach the backend.');
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `**Unable to complete this request.** ${detail}`,
        failed: true,
        retryQuestion: q,
        at: new Date(),
      }]);
    } finally {
      setIsLoading(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isLoading]);

  const copyMessage = async (content: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedIdx(idx);
      window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => setCopiedIdx(null), 1600);
    } catch {

    }
  };

  const clearChat = () => {
    setMessages([GREETING]);
    setInput('');
    inputRef.current?.focus();
  };

  const exportChat = () => {
    const lines = messages.map(m => {
      const who = m.role === 'user' ? 'OFFICER' : 'LEXSECURE ASSISTANT';
      const when = m.at.toLocaleString();
      let block = `### ${who} — ${when}\n\n${m.content}\n`;
      if (m.sources?.length) {
        block += `\n**Sources**\n`;
        block += m.sources
          .map((s: any) => `- [${s.document_title} v${s.version_number}] — case ${s.case_id}`)
          .join('\n');
        block += '\n';
      }
      return block;
    });
    const blob = new Blob([`# LexSecure — Case Assistant Transcript\n\n${lines.join('\n---\n\n')}`],
      { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lexsecure-assistant-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  const onInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-5xl mx-auto bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      <div className="bg-slate-900 text-white px-6 py-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="flex items-center gap-4 min-w-0">
          <Bot className="w-7 h-7 text-cyan-400 flex-shrink-0" />
          <div className="min-w-0">
            <h2 className="text-xl font-bold leading-snug text-white">
              LexSecure Investigative RAG Assistant
            </h2>
            <p className="text-sm text-slate-400 flex items-center mt-1.5">
              <ShieldCheck className="w-4 h-4 mr-1.5 text-emerald-400 flex-shrink-0" />
              Permission-Aware Context Injection Active
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <AiModeBadge compact />
          <button
            onClick={exportChat}
            title="Export transcript as Markdown"
            className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={clearChat}
            title="New conversation"
            className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-6 bg-slate-50">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] sm:max-w-[78%] rounded-2xl px-4 py-3.5 ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white shadow-md rounded-tr-none'
                : 'bg-white border border-slate-200 shadow-sm rounded-tl-none'
            }`}>

              {msg.role === 'user' ? (
                <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
              ) : (
                <Markdown content={msg.content} />
              )}

              {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                <div className="mt-3.5 pt-3.5 border-t border-slate-100">
                  <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wide mb-2 flex items-center">
                    <FileText className="w-3 h-3 mr-1.5" /> Evidentiary sources
                  </p>
                  <div className="space-y-1.5">
                    {msg.sources.map((src: any, sIdx: number) => (
                      <div
                        key={sIdx}
                        className="bg-slate-50 px-2.5 py-1.5 rounded-md border border-slate-200 text-xs text-slate-600 flex items-center justify-between gap-3"
                      >
                        <span className="font-medium text-indigo-700 truncate">
                          [{src.document_title}, v{src.version_number}]
                        </span>
                        <span className="text-[10px] text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200 whitespace-nowrap">
                          {src.case_id}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {msg.role === 'assistant' && msg.llm_error && (
                <div className="mt-3 flex items-start gap-2 text-xs bg-amber-50 border border-amber-300 text-amber-900 rounded-lg p-2.5">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">AI provider unavailable — deterministic template answer</p>
                    <p className="mt-0.5 leading-relaxed">
                      {msg.llm_error.reason} (provider: {msg.llm_error.provider}
                      {msg.llm_error.model ? `, model: ${msg.llm_error.model}` : ''})
                    </p>
                  </div>
                </div>
              )}

              {msg.role === 'assistant' && msg.failed && msg.retryQuestion && (
                <button
                  onClick={() => handleSend(msg.retryQuestion!)}
                  disabled={isLoading}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Retry
                </button>
              )}

              <div className="mt-2.5 flex items-center justify-between gap-3">
                <span className="text-[10px] text-slate-400">{formatTime(msg.at)}</span>
                <div className="flex items-center gap-2">
                  {msg.role === 'assistant' && msg.model && (
                    <span className="text-[10px] text-slate-400 font-mono flex items-center truncate max-w-[260px]">
                      <Cpu className="w-3 h-3 mr-1 flex-shrink-0" />
                      <span className="truncate">{msg.model}</span>
                    </span>
                  )}
                  {msg.role === 'assistant' && msg.content && (
                    <button
                      onClick={() => copyMessage(msg.content, idx)}
                      title="Copy answer"
                      className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                    >
                      {copiedIdx === idx
                        ? <Check className="w-3.5 h-3.5 text-emerald-600" />
                        : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 px-4 py-3 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2.5">
              <Loader2 className="w-4 h-4 text-indigo-500 animate-spin flex-shrink-0" />
              <div>
                <p className="text-sm text-slate-600">Searching authorized evidence and composing an answer…</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  {elapsed}s elapsed — free-tier models can take 10–20s
                </p>
              </div>
            </div>
          </div>
        )}
        <div ref={scrollEndRef} />
      </div>

      <div className="bg-white px-4 sm:px-6 py-3.5 border-t border-slate-200">
        <form
          onSubmit={(e) => { e.preventDefault(); handleSend(input); }}
          className="flex items-end gap-2"
        >
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={onInput}
            onKeyDown={onKeyDown}
            placeholder="Ask about a case, exhibit, statement or charge — Enter to send, Shift+Enter for a new line"
            className="flex-1 resize-none px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm leading-relaxed focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none disabled:opacity-60 max-h-40"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="p-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            title="Send"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
        <p className="mt-2 text-[10px] text-slate-400">
          Answers are generated only from documents your clearance permits. Queries are recorded in the audit trail.
        </p>
      </div>
    </div>
  );
};
