import React, { useState } from 'react';
import { Fingerprint, Upload, Loader2, ShieldCheck, ShieldAlert, User, FileText, Clock } from 'lucide-react';
import { apiClient } from '../api/client';

export const LeakInvestigatorPage = () => {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setScanning(true);
    setError('');
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await apiClient.post('/integrity/extract-watermark', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Scan failed. Only Supervisors/Admins may run leak investigations.');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-slate-800 flex items-center">
          <Fingerprint className="w-7 h-7 mr-3 text-indigo-600" />
          Leak Investigator
        </h2>
        <p className="text-slate-500 mt-1">
          Upload a suspicious file found outside the system. Every download is invisibly
          watermarked — the scan reveals exactly whose copy was leaked. Scans are audit-logged.
        </p>
      </div>

      <form onSubmit={handleScan} className="bg-slate-900 text-white rounded-2xl shadow-xl p-6 sm:p-8">
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${file ? 'border-emerald-400/60 bg-emerald-500/5' : 'border-slate-600 hover:border-cyan-400/60'}`}
        >
          <Upload className="w-10 h-10 mx-auto mb-3 text-cyan-400" />
          <label className="cursor-pointer">
            <span className="font-bold text-lg">{file ? file.name : 'Choose suspicious file'}</span>
            <span className="block text-sm text-slate-400 mt-1">
              {file ? `${(file.size / 1024).toFixed(1)} KB — ready to scan` : '.txt exhibits downloaded from LEXSECURE carry invisible zero-width watermarks'}
            </span>
            <input type="file" className="hidden" onChange={e => setFile(e.target.files?.[0] || null)} />
          </label>
        </div>
        {error && <p className="mt-4 text-sm text-red-400" role="alert">{error}</p>}
        <button
          type="submit"
          disabled={!file || scanning}
          className="mt-5 w-full py-3 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white font-medium rounded-lg flex items-center justify-center transition-colors"
        >
          {scanning ? <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Scanning zero-width channels…</> : 'Extract Watermark & Identify Leaker'}
        </button>
      </form>

      {result && result.is_valid && (
        <div className="rounded-2xl shadow-lg border overflow-hidden bg-white border-red-300">
          <div className="p-4 bg-red-600 text-white flex items-center">
            <ShieldAlert className="w-6 h-6 mr-2" />
            <h3 className="font-bold text-lg">LEAK SOURCE IDENTIFIED</h3>
          </div>
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div className="bg-slate-50 p-4 rounded-lg border">
              <p className="text-xs font-bold text-slate-500 uppercase mb-1 flex items-center"><User className="w-3.5 h-3.5 mr-1" /> Leaker Email</p>
              <p className="font-bold text-slate-800 break-all">{result.email}</p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg border">
              <p className="text-xs font-bold text-slate-500 uppercase mb-1">Officer User ID</p>
              <p className="font-bold text-slate-800 font-mono">#{result.user_id}</p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg border">
              <p className="text-xs font-bold text-slate-500 uppercase mb-1 flex items-center"><FileText className="w-3.5 h-3.5 mr-1" /> Source Document</p>
              <p className="font-bold text-slate-800">Doc #{result.document_id} (v{result.version})</p>
            </div>
            <div className="bg-slate-50 p-4 rounded-lg border">
              <p className="text-xs font-bold text-slate-500 uppercase mb-1 flex items-center"><Clock className="w-3.5 h-3.5 mr-1" /> Download Timestamp</p>
              <p className="font-bold text-slate-800 font-mono text-xs break-all">{result.timestamp}</p>
            </div>
          </div>
          {result.chain_length > 1 && (
            <div className="px-6 pb-6">
              <p className="text-xs font-bold text-slate-500 uppercase mb-2">Custody chain ({result.chain_length} holders)</p>
              <div className="space-y-1">
                {result.chain.map((c: any, i: number) => (
                  <p key={i} className="text-xs font-mono text-slate-600 bg-slate-50 px-3 py-1.5 rounded border">
                    #{i + 1} {c.email} (uid {c.user_id}) · {c.timestamp}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {result && !result.is_valid && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 flex items-start gap-3">
          <ShieldCheck className="w-6 h-6 text-slate-400 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-slate-800">No verifiable watermark</h3>
            <p className="text-sm text-slate-500 mt-1">{result.error} Either this copy predates watermarking, is a non-text format, or its invisible channel was destroyed.</p>
          </div>
        </div>
      )}
    </div>
  );
};
