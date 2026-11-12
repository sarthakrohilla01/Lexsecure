import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen, Plus, ShieldCheck, ShieldAlert, X, Search } from 'lucide-react';
import { apiClient, errorDetail } from '../api/client';
import { useSecurityFeed } from '../hooks/useSecurityFeed';

export const CasesPage = () => {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ id: '', title: '', description: '', department: 'CYBER_CRIME', classification: 'RESTRICTED' });
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');

  const fetchCases = () => {
    setLoading(true);
    setLoadError('');
    apiClient.get('/cases').then(res => {
      setCases(res.data);
      setLoading(false);
    }).catch((err) => {
      setLoadError(errorDetail(err, 'Could not reach the backend API.'));
      setLoading(false);
    });
  };

  useEffect(() => { fetchCases(); }, []);

  const { revision } = useSecurityFeed();
  useEffect(() => {
    if (revision === 0) return;
    const timer = setTimeout(fetchCases, 500);
    return () => clearTimeout(timer);
  }, [revision]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await apiClient.post('/cases', { ...form, status: 'UNDER_INVESTIGATION' });
      setShowCreate(false);
      setForm({ id: '', title: '', description: '', department: 'CYBER_CRIME', classification: 'RESTRICTED' });
      fetchCases();
    } catch (err: any) {
      setError(errorDetail(err, 'Failed to create case'));
    }
  };

  const needle = filter.trim().toLowerCase();
  const filtered = cases.filter((c: any) =>
    !needle ||
    (c.id || '').toLowerCase().includes(needle) ||
    (c.title || '').toLowerCase().includes(needle)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Case Files</h2>
          <p className="text-slate-500">Investigation cases — document access enforced by assignment (ABAC)</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="flex items-center justify-center px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-sm font-medium flex-shrink-0">
          <Plus className="w-4 h-4 mr-2" /> New Case
        </button>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search by case ID or title..."
          aria-label="Search cases"
          className="w-full pl-10 pr-4 py-2 bg-white border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
        />
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-500">Loading cases...</div>
      ) : loadError ? (
        <div className="p-8 text-center bg-white rounded-xl border border-red-200">
          <p className="font-semibold text-red-700">Could not load cases</p>
          <p className="text-sm text-slate-500 mt-1">{loadError}</p>
          <button
            onClick={fetchCases}
            className="mt-3 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800"
          >
            Retry
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-8 text-center text-slate-500 bg-white rounded-xl border">
          {cases.length === 0 ? 'No cases found.' : 'No cases match your search.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((c: any) => (
            <Link key={c.id} to={`/cases/${c.id}`} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:shadow-md transition-shadow block">
              <div className="flex items-start justify-between mb-3">
                <FolderOpen className="w-8 h-8 text-indigo-500" />
                {c.user_is_assigned ? (
                  <span className="flex items-center text-xs font-bold px-2 py-1 bg-emerald-100 text-emerald-700 rounded"><ShieldCheck className="w-3 h-3 mr-1" /> AUTHORIZED</span>
                ) : (
                  <span className="flex items-center text-xs font-bold px-2 py-1 bg-slate-100 text-slate-500 rounded"><ShieldAlert className="w-3 h-3 mr-1" /> NO ACCESS</span>
                )}
              </div>
              <p className="text-xs font-mono text-slate-400">{c.id}</p>
              <h3 className="font-bold text-slate-800 mt-1 line-clamp-2">{c.title}</h3>
              <p className="text-sm text-slate-500 mt-2 line-clamp-2">{c.description}</p>
              <div className="flex items-center gap-2 mt-4">
                <span className="text-xs px-2 py-1 bg-slate-100 rounded text-slate-700">{c.classification}</span>
                <span className="text-xs px-2 py-1 bg-indigo-50 rounded text-indigo-700">{c.status}</span>
              </div>
              <div className="flex justify-between text-xs text-slate-500 mt-4 pt-3 border-t border-slate-100">
                <span>{c.document_count} documents</span>
                <span>{c.assigned_officers_count} officers</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-lg">Create New Case</h3>
              <button onClick={() => setShowCreate(false)}><X className="w-5 h-5 text-slate-400" /></button>
            </div>
            {error && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded border border-red-200">{error}</div>}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Case ID (e.g. CASE-2026-010)</label>
                <input required value={form.id} onChange={e => setForm({ ...form, id: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg font-mono text-sm" placeholder="CASE-2026-010" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Title</label>
                <input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg" placeholder="State vs. ..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg" rows={3} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Department</label>
                  <select value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg">
                    <option value="CYBER_CRIME">CYBER_CRIME</option>
                    <option value="FORENSIC_LAB">FORENSIC_LAB</option>
                    <option value="PROSECUTION">PROSECUTION</option>
                    <option value="WOMEN_SAFETY">WOMEN_SAFETY</option>
                    <option value="ADMINISTRATION">ADMINISTRATION</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Classification</label>
                  <select value={form.classification} onChange={e => setForm({ ...form, classification: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg">
                    <option value="RESTRICTED">RESTRICTED</option>
                    <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                    <option value="SECRET">SECRET</option>
                    <option value="TOP_SECRET">TOP_SECRET</option>
                  </select>
                </div>
              </div>
              <button type="submit" className="w-full py-2.5 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-800">Create Case</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
