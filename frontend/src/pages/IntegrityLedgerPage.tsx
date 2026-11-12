import React, { useEffect, useState } from 'react';
import { Database, Link2, ShieldCheck, ShieldAlert, Radio, AlertTriangle, CheckCircle2, Upload, RefreshCw, FolderPlus, BadgeCheck } from 'lucide-react';
import { apiClient } from '../api/client';
import { useSecurityFeed } from '../hooks/useSecurityFeed';

const EVENT_ICONS: Record<string, React.ReactNode> = {
  TAMPER_ALERT: <AlertTriangle className="w-4 h-4" />,
  TAMPER_RESOLVED: <CheckCircle2 className="w-4 h-4" />,
  DOCUMENT_UPLOADED: <Upload className="w-4 h-4" />,
  CASE_CREATED: <FolderPlus className="w-4 h-4" />,
  APPROVAL_DECIDED: <BadgeCheck className="w-4 h-4" />,
};

const EVENT_STYLES: Record<string, string> = {
  TAMPER_ALERT: 'bg-red-500/10 border-red-400/50 text-red-600',
  TAMPER_RESOLVED: 'bg-emerald-500/10 border-emerald-400/50 text-emerald-600',
  DOCUMENT_UPLOADED: 'bg-cyan-500/10 border-cyan-400/50 text-cyan-700',
  CASE_CREATED: 'bg-indigo-500/10 border-indigo-400/50 text-indigo-700',
  APPROVAL_DECIDED: 'bg-emerald-500/10 border-emerald-400/50 text-emerald-700',
};

export const IntegrityLedgerPage = () => {
  const [blocks, setBlocks] = useState<any[]>([]);
  const [chainStatus, setChainStatus] = useState<any>(null);
  const { connected, events, revision } = useSecurityFeed();

  const fetchLedger = () => {
    apiClient.get('/integrity/ledger').then(res => setBlocks(res.data)).catch(() => {});
    apiClient.get('/integrity/verify-chain').then(res => setChainStatus(res.data)).catch(() => {});
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  useEffect(() => {
    if (revision > 0) fetchLedger();
  }, [revision]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 flex items-center">
            <Database className="w-6 h-6 mr-3 text-indigo-600" />
            Custody Ledger Explorer
          </h2>
          <p className="text-slate-500 mt-1">Append-only SHA-256 hash chain · every event verifiable end-to-end</p>
        </div>

        {chainStatus && (
          <div className={`px-4 py-2 rounded-lg flex items-center font-bold text-sm ${chainStatus.is_valid ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' : 'bg-red-100 text-red-700 border border-red-200'}`}>
            {chainStatus.is_valid ? <ShieldCheck className="w-5 h-5 mr-2" /> : <ShieldAlert className="w-5 h-5 mr-2" />}
            CHAIN {chainStatus.status}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-slate-700 flex items-center text-sm">
            <Radio className={`w-4 h-4 mr-2 ${connected ? 'text-red-500 animate-pulse' : 'text-slate-400'}`} />
            Live Security Feed
            <span className={`ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full border ${connected ? 'bg-red-50 text-red-600 border-red-200' : 'bg-slate-100 text-slate-400 border-slate-200'}`}>
              {connected ? 'LIVE' : 'OFFLINE'}
            </span>
          </h3>
          <button onClick={fetchLedger} className="text-xs text-slate-400 hover:text-indigo-600 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> refresh
          </button>
        </div>
        {events.length === 0 ? (
          <p className="text-xs text-slate-400">
            {connected
              ? 'Listening for tamper alerts, restorations, and secured uploads…'
              : 'Connecting to the live event stream…'}
          </p>
        ) : (
          <div className="space-y-2 max-h-56 overflow-y-auto">
            {events.map((ev, idx) => (
              <div key={`${ev.receivedAt}-${idx}`} className={`flex items-start gap-3 text-xs border rounded-lg p-2.5 ${EVENT_STYLES[ev.event] || 'bg-slate-50 border-slate-200 text-slate-600'}`}>
                <span className="flex-shrink-0 mt-0.5">{EVENT_ICONS[ev.event] || <ShieldCheck className="w-4 h-4" />}</span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{ev.event}</p>
                  <p className="text-slate-500">{ev.data?.message}</p>
                </div>
                <span className="text-[10px] text-slate-400 flex-shrink-0">{new Date(ev.receivedAt).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-slate-900 rounded-xl shadow-xl border border-slate-800 p-6 overflow-hidden relative">
        <div className="absolute left-10 top-0 bottom-0 w-1 bg-slate-700/50 z-0 hidden lg:block"></div>

        <div className="space-y-6 relative z-10">
          {blocks.map((block: any, idx: number) => (
            <div key={idx} className="flex flex-col lg:flex-row items-start lg:items-center">

              <div className="flex items-center lg:w-48 mb-4 lg:mb-0">
                <div className="w-12 h-12 bg-indigo-600 rounded-lg border-2 border-indigo-400 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(79,70,229,0.5)] z-10 relative">
                  B{block.block_number}
                </div>
                <div className="ml-4">
                  <span className={`text-xs font-bold px-2 py-1 rounded ${
                    block.event_type === 'GENESIS' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50' :
                    block.event_type === 'CREATED' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50' :
                    (block.event_type || '').includes('TAMPER') ? 'bg-red-500/20 text-red-400 border border-red-500/50' :
                    'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                  }`}>
                    {block.event_type}
                  </span>
                </div>
              </div>

              <div className="flex-1 bg-slate-800/80 border border-slate-700 rounded-lg p-4 w-full lg:ml-8 hover:bg-slate-800 transition-colors">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-slate-400 text-xs mb-1">Timestamp</p>
                    <p className="text-slate-200">{new Date(block.timestamp).toLocaleString()}</p>
                  </div>
                  {block.document_id && (
                    <div>
                      <p className="text-slate-400 text-xs mb-1">Target Document</p>
                      <p className="text-slate-200">Doc #{block.document_id} (v{block.version_number}) in {block.case_id}</p>
                    </div>
                  )}
                  <div className="md:col-span-2">
                    <p className="text-slate-400 text-xs mb-1 flex items-center"><Link2 className="w-3 h-3 mr-1"/> Previous Hash Link</p>
                    <p className="text-slate-300 font-mono text-xs break-all truncate" title={block.previous_hash}>{block.previous_hash}</p>
                  </div>
                  <div className="md:col-span-2 bg-slate-900/50 p-2 rounded border border-slate-700/50 mt-2">
                    <p className="text-slate-400 text-xs mb-1 text-cyan-400 font-semibold">Block Hash</p>
                    <p className="text-emerald-400 font-mono text-xs break-all">{block.block_hash}</p>
                  </div>
                </div>
              </div>

            </div>
          ))}

          {blocks.length === 0 && (
            <div className="text-slate-500 text-center py-8">Loading custody ledger...</div>
          )}
        </div>
      </div>
    </div>
  );
};
