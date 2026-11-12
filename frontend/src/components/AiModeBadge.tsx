import React, { useEffect, useState } from 'react';
import { Cpu, FlaskConical, ShieldCheck, KeyRound, Sparkles } from 'lucide-react';
import { apiClient } from '../api/client';


export const AiModeBadge = ({ compact = false }: { compact?: boolean }) => {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    apiClient.get('/ai/status').then((res) => setStatus(res.data)).catch(() => {});
  }, []);

  if (!status) return null;

  const llmOn = status.generation_mode === 'llm';
  const providerSet = !!status.llm_provider && status.llm_provider !== 'none';
  const keyMissing = providerSet && !llmOn;
  const degraded = llmOn && !!status.llm_last_error;

  return (
    <span
      title={degraded
        ? `Last AI call failed: ${status.llm_last_error.reason}`
        : status.note}
      className={`inline-flex items-center gap-2 font-bold uppercase tracking-wider border ${
        compact
          ? 'text-[11px] px-4 py-2.5 rounded-full leading-tight max-w-[240px] text-left'
          : 'text-[10px] px-2.5 py-1 rounded-full'
      } ${
        llmOn && !degraded
          ? 'bg-cyan-500/15 text-cyan-300 border-cyan-400/40'
          : 'bg-amber-500/15 text-amber-300 border-amber-400/40'
      }`}
    >
      {llmOn && !degraded
        ? <Cpu className={compact ? 'w-4 h-4 flex-shrink-0' : 'w-3 h-3'} />
        : keyMissing ? <KeyRound className="w-3 h-3 flex-shrink-0" /> : <FlaskConical className="w-3 h-3 flex-shrink-0" />}
      <span className={compact ? 'whitespace-normal' : undefined}>
        {degraded
          ? `${status.llm_provider} · degraded`
          : llmOn
            ? `LLM: ${status.llm_provider}/${status.llm_model}`
            : keyMissing
              ? `${status.llm_provider} · API key missing`
              : 'Deterministic RAG · local synthesis'}
      </span>
      {!compact && llmOn && !degraded && (
        <span className="font-medium normal-case text-cyan-400/80">· grounded retrieval</span>
      )}
    </span>
  );
};


export const AiModeNote = () => {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    apiClient.get('/ai/status').then((res) => setStatus(res.data)).catch(() => {});
  }, []);

  if (!status) return null;

  return (
    <div className="mt-2">
      <p className="text-xs text-slate-400 flex items-center justify-center gap-1.5">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
        {status.note}
      </p>
      <p className="text-xs text-slate-500 flex items-center justify-center gap-1.5 mt-1">
        <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
        Embeddings: {status.embedding_provider === 'gemini'
          ? `Google Gemini (${status.embedding_model}) — true semantic vectors`
          : 'local offline hash vectors (air-gapped)'}
      </p>
    </div>
  );
};
