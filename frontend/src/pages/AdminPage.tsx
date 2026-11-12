import React, { useEffect, useState } from 'react';
import { ShieldAlert, Users, Activity, ScrollText, Cpu, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { apiClient } from '../api/client';

export const AdminPage = () => {
  const [health, setHealth] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [policies, setPolicies] = useState<any[]>([]);
  const [usersRestricted, setUsersRestricted] = useState(false);
  const [ai, setAi] = useState<any>(null);

  useEffect(() => {
    apiClient.get('/admin/system-health').then(res => setHealth(res.data)).catch(() => {});
    apiClient.get('/admin/users').then(res => setUsers(res.data)).catch(() => {
      setUsersRestricted(true);
    });
    apiClient.get('/admin/policies').then(res => setPolicies(res.data)).catch(() => {});
    apiClient.get('/ai/status').then(res => setAi(res.data)).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800 flex items-center"><ShieldAlert className="w-6 h-6 mr-2 text-red-500" /> System Administration</h2>
        <p className="text-slate-500">Health, users, and access policy matrix</p>
      </div>

      {health && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            { label: 'Cases', value: health.metrics?.total_cases },
            { label: 'Documents', value: health.metrics?.total_documents },
            { label: 'Ledger Blocks', value: health.metrics?.total_ledger_blocks },
            { label: 'Audit Events', value: health.metrics?.total_audit_events },
            { label: 'Tamper Alerts', value: health.metrics?.active_tamper_alerts },
          ].map((m, i) => (
            <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 text-center">
              <p className="text-2xl font-bold text-slate-800">{m.value ?? '...'}</p>
              <p className="text-xs text-slate-500 mt-1">{m.label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b bg-slate-50 font-bold flex items-center"><Users className="w-5 h-5 mr-2 text-slate-500" /> Registered Officers{users.length > 0 ? ` (${users.length})` : ''}</div>
          {usersRestricted ? (
            <div className="p-6 text-sm text-slate-500 flex items-start gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-500 flex-shrink-0" />
              <p>Officer directory is restricted to Administrators. System health and policy matrix below remain visible to your role.</p>
            </div>
          ) : (
            users.map((u: any) => (
            <div key={u.id} className="p-4 border-b border-slate-100 flex justify-between items-center">
              <div>
                <p className="font-medium text-sm">{u.full_name}</p>
                <p className="text-xs text-slate-500">{u.email} • {u.badge_number}</p>
              </div>
              <div className="text-right">
                <span className="text-xs px-2 py-1 bg-indigo-50 text-indigo-700 rounded font-bold">{u.role}</span>
                <p className="text-xs text-slate-400 mt-1">{u.is_active ? 'Active' : 'Deactivated'}</p>
              </div>
            </div>
            ))
          )}
        </div>

        <div className="space-y-6">
          {ai && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-4 border-b bg-slate-50 font-bold flex items-center">
                <Cpu className="w-5 h-5 mr-2 text-slate-500" /> AI Provider Health
                <span className={`ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                  ai.quota_exhausted
                    ? 'bg-amber-100 text-amber-700 border-amber-200'
                    : ai.llm_last_error
                      ? 'bg-amber-100 text-amber-700 border-amber-200'
                      : ai.llm_ready
                        ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
                        : 'bg-slate-100 text-slate-500 border-slate-200'
                }`}>
                  {ai.quota_exhausted ? 'QUOTA LIMITED' : ai.llm_last_error ? 'DEGRADED' : ai.llm_ready ? 'OPERATIONAL' : 'OFFLINE MODE'}
                </span>
              </div>
              <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-slate-500">Provider</p>
                  <p className="font-medium text-slate-800">{ai.llm_provider || 'none (local template engine)'}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Active model</p>
                  <p className="font-medium text-slate-800">{ai.llm_model || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Embeddings</p>
                  <p className="font-medium text-slate-800">
                    {ai.embedding_provider === 'gemini' ? `Google Gemini (${ai.embedding_model})` : 'local offline vectors'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Model failover list</p>
                  <p className="font-medium text-slate-800 text-xs break-all">
                    {ai.llm_allowed_models?.length ? ai.llm_allowed_models.join(', ') : 'auto-discover (all live models)'}
                  </p>
                </div>
              </div>
              {ai.quota_exhausted && (
                <div className="mx-4 mb-4 flex items-start gap-2 text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-3">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <p>
                    {ai.quota_exhausted.message}
                    {ai.quota_exhausted.retry_in_seconds > 0 &&
                      ` Retrying automatically in ~${ai.quota_exhausted.retry_in_seconds}s.`}
                    {' '}Until then the assistant serves a deterministic, ABAC-scoped template answer and says so.
                  </p>
                </div>
              )}
              {!ai.quota_exhausted && ai.llm_last_error && (
                <div className="mx-4 mb-4 flex items-start gap-2 text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-3">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <p>
                    Last provider call failed — {ai.llm_last_error.reason}
                    {' '}The assistant falls back to a deterministic, ABAC-scoped template answer and labels it as such.
                  </p>
                </div>
              )}
              {!ai.quota_exhausted && ai.llm_ready && (
                <div className="mx-4 mb-4 flex items-start gap-2 text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg p-3">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <p>Answers are generated by {ai.llm_provider}/{ai.llm_model} and grounded in ABAC-filtered evidence only.</p>
                </div>
              )}
            </div>
          )}

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="p-4 border-b bg-slate-50 font-bold flex items-center"><Activity className="w-5 h-5 mr-2 text-slate-500" /> Component Health</div>
            {health && Object.entries(health.components || {}).map(([k, v]: any) => (
              <div key={k} className="p-3 border-b border-slate-100 flex justify-between text-sm">
                <span className="font-medium text-slate-700">{k}</span>
                <span className={`text-xs font-bold px-2 py-1 rounded ${v.status === 'ONLINE' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>{v.status}</span>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="p-4 border-b bg-slate-50 font-bold flex items-center"><ScrollText className="w-5 h-5 mr-2 text-slate-500" /> RBAC + ABAC Policy Matrix</div>
            {policies.map((p: any, i: number) => (
              <div key={i} className="p-4 border-b border-slate-100">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-sm">{p.role}</span>
                  <span className="text-xs px-2 py-1 bg-slate-100 rounded">{p.clearance}</span>
                </div>
                <p className="text-xs text-slate-500 mt-1">{p.rule}</p>
                <div className="flex gap-2 mt-2 text-[11px]">
                  <span>Upload: {p.can_upload ? '✓' : '✗'}</span>
                  <span>Sign: {p.can_sign ? '✓' : '✗'}</span>
                  <span>Approve: {p.can_approve ? '✓' : '✗'}</span>
                  <span>Admin: {p.can_admin ? '✓' : '✗'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
