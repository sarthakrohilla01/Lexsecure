import React, { useEffect, useState } from 'react';
import { Shield, FileText, FolderOpen, AlertTriangle, CheckCircle, Database, KeyRound, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiClient, errorDetail } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const DashboardPage = () => {
  const { user } = useAuth();
  const [health, setHealth] = useState<any>(null);
  const [pending, setPending] = useState<any[]>([]);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState('');

  const isSupervisor = user && ['SUPERVISOR', 'ADMINISTRATOR'].includes(user.role);

  const fetchPending = () => {
    if (!isSupervisor) return;
    apiClient.get('/approvals/pending').then(res => setPending(res.data)).catch(() => {});
  };

  useEffect(() => {
    apiClient.get('/admin/system-health').then(res => setHealth(res.data)).catch(() => {});
    fetchPending();
  }, []);

  const processRequest = async (requestId: number, approve: boolean) => {
    setProcessingId(requestId);
    setActionError('');
    try {
      await apiClient.post('/approvals/process', { request_id: requestId, approve });
      fetchPending();
    } catch (e: any) {
      setActionError(errorDetail(e, 'Could not record the approval decision.'));
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Security & Analytics Overview</h2>
          <p className="text-slate-500">System metrics and cryptographic posture</p>
        </div>
        {health && (
          <div className={`px-4 py-2 rounded-full font-bold text-sm ${health.overall_status === 'ONLINE' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
            SYSTEM {health.overall_status}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard icon={<FolderOpen />} label="Total Active Cases" value={health?.metrics?.total_cases || "..."} color="blue" />
        <StatCard icon={<FileText />} label="Encrypted Documents" value={health?.metrics?.total_documents || "..."} color="indigo" />
        <StatCard icon={<Database />} label="Ledger Blocks" value={health?.metrics?.total_ledger_blocks || "..."} color="emerald" />
        <StatCard icon={<AlertTriangle />} label="Tamper Alerts" value={health?.metrics?.active_tamper_alerts || "0"} color="red" />
      </div>

      {isSupervisor && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <h3 className="font-bold text-lg flex items-center text-slate-800">
              <KeyRound className="w-5 h-5 mr-2 text-amber-500" />
              Pending Two-Man Rule Approvals
              {pending.length > 0 && (
                <span className="ml-2 text-xs font-bold px-2 py-1 bg-amber-100 text-amber-700 rounded-full">{pending.length}</span>
              )}
            </h3>
          </div>
          {pending.length === 0 ? (
            <p className="p-5 text-sm text-slate-400">No access requests awaiting your decision.</p>
          ) : (
            pending.map((r: any) => (              <div key={r.id} className="p-5 border-b border-slate-100 last:border-0 flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex-1 min-w-0">
                  <Link to={`/documents/${r.document_id}`} className="font-bold text-indigo-700 hover:underline truncate block">
                    {r.document_title}
                  </Link>
                  <p className="text-xs text-slate-500 mt-1">
                    Requested by <span className="font-medium text-slate-700">{r.requester_email}</span> • Doc #{r.document_id}
                  </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => processRequest(r.id, true)}
                    disabled={processingId === r.id}
                    className="flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
                  >
                    <CheckCircle className="w-4 h-4 mr-1.5" /> Grant Access
                  </button>
                  <button
                    onClick={() => processRequest(r.id, false)}
                    disabled={processingId === r.id}
                    className="flex items-center px-4 py-2 bg-white border border-red-300 hover:bg-red-50 text-red-700 text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
                  >
                    <XCircle className="w-4 h-4 mr-1.5" /> Reject
                  </button>
                </div>
              </div>
            ))
          )}
          <p className="px-5 py-3 bg-slate-50 text-[11px] text-slate-400 border-t border-slate-100">
            Granting issues a 2-hour unlock token bound to that investigator and document. Grants and rejections are audit-logged.
          </p>
          {actionError && (
            <p className="px-5 py-3 text-sm text-red-700 bg-red-50 border-t border-red-100">{actionError}</p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-bold text-lg mb-4 flex items-center text-slate-800">
            <Shield className="w-5 h-5 mr-2 text-indigo-500" />
            Active Security Controls
          </h3>
          <div className="space-y-4">
            <ControlItem label="Authentication" desc={health?.security_controls?.mfa_enforcement || "ACTIVE"} />
            <ControlItem label="Authorization Policy" desc={health?.security_controls?.rbac_abac || "ACTIVE"} />
            <ControlItem label="Encryption at Rest" desc={health?.security_controls?.at_rest_encryption || "ACTIVE"} />
            <ControlItem label="Digital Signatures" desc={health?.security_controls?.pki_signatures || "ACTIVE"} />
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-bold text-lg mb-4 flex items-center text-slate-800">
            <CheckCircle className="w-5 h-5 mr-2 text-emerald-500" />
            Infrastructure Status
          </h3>
          <div className="space-y-4">
            <ControlItem label="Backend Engine" desc={health?.components?.backend_api?.status || "..."} />
            <ControlItem label="Primary Database" desc={health?.components?.database?.technology || "..."} />
            <ControlItem label="Object Storage" desc={health?.components?.object_storage?.technology || "..."} />
            <ControlItem label="Trust Ledger" desc={health?.components?.permissioned_ledger?.technology || "..."} />
          </div>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ icon, label, value, color }: any) => {
  const colorMap: any = {
    blue: 'bg-blue-100 text-blue-600',
    indigo: 'bg-indigo-100 text-indigo-600',
    emerald: 'bg-emerald-100 text-emerald-600',
    red: 'bg-red-100 text-red-600',
  };
  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex items-center">
      <div className={`p-4 rounded-lg ${colorMap[color]} mr-4`}>
        {icon}
      </div>
      <div>
        <p className="text-slate-500 text-sm font-medium">{label}</p>
        <p className="text-2xl font-bold text-slate-800">{value}</p>
      </div>
    </div>
  );
};

const ControlItem = ({ label, desc }: any) => (
  <div className="flex justify-between items-center py-2 border-b border-slate-50 last:border-0">
    <span className="text-slate-600 font-medium">{label}</span>
    <span className="text-sm px-3 py-1 bg-slate-100 rounded text-slate-700">{desc}</span>
  </div>
);
