import React, { useEffect, useState } from 'react';
import { AlertTriangle, Search, Download, FileSpreadsheet, FileJson } from 'lucide-react';
import { apiClient } from '../api/client';

export const AuditTrailPage = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [exportMsg, setExportMsg] = useState('');
  const [exporting, setExporting] = useState(false);

  const fetchLogs = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (actionFilter) params.append('action', actionFilter);
    if (statusFilter) params.append('status', statusFilter);
    params.append('limit', '100');
    apiClient.get(`/audit?${params.toString()}`).then(res => {
      setLogs(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchLogs(); }, []);

  const exportLogs = async (fmt: 'csv' | 'json') => {
    setExporting(true);
    setExportMsg('');
    try {
      const params = new URLSearchParams();
      if (actionFilter) params.append('action', actionFilter);
      if (statusFilter) params.append('status', statusFilter);
      params.append('format', fmt);

      const res = await apiClient.get(`/audit/export?${params.toString()}`, {
        responseType: 'blob',
      });

      const cd = String(res.headers['content-disposition'] || '');
      const nameMatch = cd.match(/filename="?([^";]+)"?/);
      const sha = String(res.headers['x-export-sha256'] || '');
      const count = String(res.headers['x-export-count'] || '?');

      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = nameMatch ? nameMatch[1] : `lexsecure_audit_trail.${fmt}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setExportMsg(
        `Downloaded ${count} events as ${fmt.toUpperCase()} — SHA-256 ${sha.slice(0, 16)}…`
      );
    } catch {
      setExportMsg('Export failed — please retry.');
    } finally {
      setExporting(false);
    }
  };

  const statusColor = (s: string) =>
    s === 'SUCCESS' ? 'bg-emerald-100 text-emerald-700' :
    s === 'FAILURE' || s === 'BLOCKED' ? 'bg-red-100 text-red-700' :
    'bg-amber-100 text-amber-700';

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800 flex items-center">
          <AlertTriangle className="w-6 h-6 mr-2 text-amber-500" /> Immutable Audit Trail
        </h2>
        <p className="text-slate-500">Every authentication, document view, signature, and tamper event is logged</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-slate-400" />
          <input value={actionFilter} onChange={e => setActionFilter(e.target.value)} placeholder="Filter by action (e.g. LOGIN_SUCCESS)" className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-64" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
          <option value="">All statuses</option>
          <option value="SUCCESS">SUCCESS</option>
          <option value="FAILURE">FAILURE</option>
          <option value="WARNING">WARNING</option>
          <option value="BLOCKED">BLOCKED</option>
        </select>
        <button onClick={fetchLogs} className="px-4 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-800">Apply Filters</button>

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => exportLogs('csv')}
            disabled={exporting}
            title="Download the (filtered) audit trail as CSV for Excel / court submission"
            className="px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            <FileSpreadsheet className="w-4 h-4" /> Export CSV
          </button>
          <button
            onClick={() => exportLogs('json')}
            disabled={exporting}
            title="Download the (filtered) audit trail as JSON for external systems"
            className="px-3 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5"
          >
            <FileJson className="w-4 h-4" /> Export JSON
          </button>
        </div>
      </div>

      {exportMsg && (
        <div className="flex items-center gap-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
          <Download className="w-3.5 h-3.5" /> {exportMsg}
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-500">Loading audit events...</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-500 border-b">
                <th className="p-3 font-medium">Timestamp</th>
                <th className="p-3 font-medium">Actor</th>
                <th className="p-3 font-medium">Action</th>
                <th className="p-3 font-medium">Target</th>
                <th className="p-3 font-medium">Details</th>
                <th className="p-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l: any) => (
                <tr key={l.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="p-3 text-xs text-slate-500 whitespace-nowrap">{new Date(l.timestamp).toLocaleString()}</td>
                  <td className="p-3"><p className="font-medium text-slate-700 text-xs">{l.user_email}</p><p className="text-xs text-slate-400">{l.user_role}</p></td>
                  <td className="p-3 font-mono text-xs text-indigo-700">{l.action}</td>
                  <td className="p-3 text-xs text-slate-500">{l.target_type}{l.target_id ? ` #${l.target_id}` : ''}</td>
                  <td className="p-3 text-xs text-slate-600 max-w-xs truncate" title={l.details}>{l.details}</td>
                  <td className="p-3"><span className={`text-xs font-bold px-2 py-1 rounded ${statusColor(l.status)}`}>{l.status}</span></td>
                </tr>
              ))}
              {logs.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-slate-400">No audit events match filters.</td></tr>}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
