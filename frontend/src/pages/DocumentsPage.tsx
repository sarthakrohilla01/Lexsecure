import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Search, Plus, X, Upload } from 'lucide-react';
import { apiClient, errorDetail } from '../api/client';
import { useSecurityFeed } from '../hooks/useSecurityFeed';

export const DocumentsPage = () => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [cases, setCases] = useState<any[]>([]);
  const [uploadForm, setUploadForm] = useState({ case_id: '', title: '', document_type: '', classification: 'RESTRICTED', change_reason: 'Initial case filing' });
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [loadError, setLoadError] = useState('');

  const fetchDocs = () => {
    setLoading(true);
    setLoadError('');
    apiClient.get('/documents').then(res => {
      setDocuments(res.data);
      setLoading(false);
    }).catch((err) => {
      setLoadError(errorDetail(err, 'Could not reach the backend API.'));
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchDocs();
    apiClient.get('/cases').then(res => setCases(res.data.filter((c: any) => c.user_is_assigned))).catch(() => {});
  }, []);

  const { revision } = useSecurityFeed();
  useEffect(() => {
    if (revision === 0) return;
    const timer = setTimeout(fetchDocs, 500);
    return () => clearTimeout(timer);
  }, [revision]);

  const needle = filter.toLowerCase();
  const filtered = documents.filter((d: any) =>
    !needle ||
    (d.title || '').toLowerCase().includes(needle) ||
    (d.case_id || '').toLowerCase().includes(needle) ||
    (d.document_type || '').toLowerCase().includes(needle)
  );

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !uploadForm.case_id) {
      setUploadError('Select a case and a file to upload.');
      return;
    }
    setUploading(true);
    setUploadError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('case_id', uploadForm.case_id);
      if (uploadForm.title) fd.append('title', uploadForm.title);
      if (uploadForm.document_type) fd.append('document_type', uploadForm.document_type);
      fd.append('classification', uploadForm.classification);
      fd.append('change_reason', uploadForm.change_reason);
      await apiClient.post('/documents/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setShowUpload(false);
      setFile(null);
      setUploadForm({ case_id: '', title: '', document_type: '', classification: 'RESTRICTED', change_reason: 'Initial case filing' });
      fetchDocs();
    } catch (err: any) {
      setUploadError(errorDetail(err, 'Upload failed'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Document Repository</h2>
          <p className="text-slate-500">Secure evidentiary documents across authorized cases</p>
        </div>
        <button onClick={() => setShowUpload(true)} className="flex items-center px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-sm font-medium">
          <Plus className="w-4 h-4 mr-2" /> Upload Evidence
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter authorized documents..."
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500"
            />
          </div>
          <span className="text-xs text-slate-500">{filtered.length} of {documents.length} shown</span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-500">Loading authorized documents...</div>
        ) : loadError ? (
          <div className="p-8 text-center">
            <p className="font-semibold text-red-700">Could not load documents</p>
            <p className="text-sm text-slate-500 mt-1">{loadError}</p>
            <button
              onClick={fetchDocs}
              className="mt-3 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-medium hover:bg-slate-800"
            >
              Retry
            </button>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 text-slate-500 text-sm border-b border-slate-200">
                <th className="p-4 font-medium">Document Title</th>
                <th className="p-4 font-medium">Case ID</th>
                <th className="p-4 font-medium">Type</th>
                <th className="p-4 font-medium">Version</th>
                <th className="p-4 font-medium">Status</th>
                <th className="p-4 font-medium">Integrity</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((doc: any) => (
                <tr key={doc.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="p-4">
                    <Link to={`/documents/${doc.id}`} className="font-medium text-indigo-600 hover:underline flex items-center">
                      <FileText className="w-4 h-4 mr-2" /> {doc.title}
                    </Link>
                  </td>
                  <td className="p-4 text-sm text-slate-600">{doc.case_id}</td>
                  <td className="p-4 text-sm"><span className="px-2 py-1 bg-slate-100 rounded text-slate-700">{doc.document_type}</span></td>
                  <td className="p-4 text-sm">v{doc.current_version}</td>
                  <td className="p-4 text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      doc.status === 'APPROVED' || doc.status === 'SIGNED' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {doc.status}
                    </span>
                    {doc.requires_dual_auth && (
                      <span className="ml-1 px-2 py-1 rounded text-xs font-bold bg-red-100 text-red-700 border border-red-200" title="Sealed under the Two-Man Rule">
                        SEALED
                      </span>
                    )}
                  </td>
                  <td className="p-4 text-sm">
                    {doc.is_tampered ? (
                      <span className="text-red-500 font-bold">⚠ ALERT</span>
                    ) : (
                      <span className="text-emerald-500 font-bold flex items-center"><span className="w-2 h-2 rounded-full bg-emerald-500 mr-2"></span> SECURE</span>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-500">No documents match the current filter.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showUpload && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-lg flex items-center"><Upload className="w-5 h-5 mr-2" /> Upload Evidence</h3>
              <button onClick={() => setShowUpload(false)}><X className="w-5 h-5 text-slate-400" /></button>
            </div>
            {uploadError && <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded border border-red-200">{uploadError}</div>}
            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Case (assigned only)</label>
                <select required value={uploadForm.case_id} onChange={e => setUploadForm({ ...uploadForm, case_id: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg">
                  <option value="">Select case...</option>
                  {cases.map((c: any) => <option key={c.id} value={c.id}>{c.id} — {c.title.slice(0, 50)}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Evidence File (pdf, txt, docx, jpg, png — max 50MB)</label>
                <input type="file" required onChange={e => setFile(e.target.files?.[0] || null)} className="w-full text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Title (optional)</label>
                <input value={uploadForm.title} onChange={e => setUploadForm({ ...uploadForm, title: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg" placeholder="Defaults to filename" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Type (optional)</label>
                  <input value={uploadForm.document_type} onChange={e => setUploadForm({ ...uploadForm, document_type: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg" placeholder="Auto-classified if blank" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Classification</label>
                  <select value={uploadForm.classification} onChange={e => setUploadForm({ ...uploadForm, classification: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg">
                    <option>RESTRICTED</option><option>CONFIDENTIAL</option><option>SECRET</option><option>TOP_SECRET</option>
                  </select>
                </div>
              </div>
              <button type="submit" disabled={uploading} className="w-full py-2.5 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-800 disabled:opacity-50">
                {uploading ? 'Encrypting & uploading...' : 'Encrypt & Upload (AES-256 + SHA-256 + Ledger)'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
