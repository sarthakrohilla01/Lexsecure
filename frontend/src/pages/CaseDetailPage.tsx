import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FolderOpen, FileText, Users, Download, ShieldAlert } from 'lucide-react';
import { apiClient, errorDetail } from '../api/client';

export const CaseDetailPage = () => {
  const { id } = useParams();
  const [caseData, setCaseData] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [pkgError, setPkgError] = useState('');
  const [pkg, setPkg] = useState<any>(null);
  const [loadingPkg, setLoadingPkg] = useState(false);

  useEffect(() => {
    apiClient.get(`/cases/${id}`).then(res => setCaseData(res.data)).catch((e) => {
      setError(errorDetail(e, 'Unable to load case (ABAC denied or not found)'));
    });
    apiClient.get(`/cases/${id}/documents`).then(res => setDocs(res.data)).catch(() => {});
  }, [id]);

  const generatePackage = async () => {
    setLoadingPkg(true);
    setPkgError('');
    try {
      const res = await apiClient.get(`/reports/court-package/${id}`);
      setPkg(res.data);
    } catch (err: any) {
      setPkgError(errorDetail(err, 'Could not generate the court package.'));
    } finally {
      setLoadingPkg(false);
    }
  };

  const downloadPackage = () => {
    if (!pkg) return;
    const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${pkg.court_package_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (error) {
    return (
      <div className="max-w-2xl mx-auto bg-white p-8 rounded-xl border border-red-200 text-center">
        <ShieldAlert className="w-10 h-10 text-red-500 mx-auto mb-3" />
        <h2 className="font-bold text-lg text-slate-800">Access Restricted</h2>
        <p className="text-slate-500 text-sm mt-2">{error}</p>
        <Link to="/cases" className="inline-block mt-4 text-indigo-600 hover:underline text-sm">← Back to Cases</Link>
      </div>
    );
  }

  if (!caseData) return <div className="p-8 text-slate-500">Loading case file...</div>;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <Link to="/cases" className="text-sm text-indigo-600 hover:underline">← Back to Cases</Link>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-start gap-4">
          <FolderOpen className="w-10 h-10 text-indigo-500 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-xs font-mono text-slate-400">{caseData.id}</p>
            <h2 className="text-2xl font-bold text-slate-800">{caseData.title}</h2>
            <p className="text-slate-500 text-sm mt-2">{caseData.description}</p>
            <div className="flex gap-2 mt-3">
              <span className="text-xs px-2 py-1 bg-slate-100 rounded text-slate-700">{caseData.classification}</span>
              <span className="text-xs px-2 py-1 bg-indigo-50 rounded text-indigo-700">{caseData.status}</span>
              <span className="text-xs px-2 py-1 bg-slate-100 rounded text-slate-700">{caseData.department}</span>
            </div>
          </div>
          <button onClick={generatePackage} disabled={loadingPkg} className="px-4 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-800 flex items-center">
            <Download className="w-4 h-4 mr-2" /> {loadingPkg ? 'Generating...' : 'Court Package (65B)'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b bg-slate-50 font-bold text-slate-800 flex items-center">
            <FileText className="w-5 h-5 mr-2 text-slate-500" /> Case Documents ({docs.length})
          </div>
          {docs.map((d: any) => (
            <Link key={d.id} to={`/documents/${d.id}`} className="block p-4 border-b border-slate-100 hover:bg-slate-50">
              <p className="font-medium text-indigo-700">{d.title}</p>
              <p className="text-xs text-slate-500 mt-1">{d.document_type} • v{d.current_version} • {d.status} {d.is_tampered ? '• ⚠ TAMPERED' : ''}</p>
            </Link>
          ))}
          {docs.length === 0 && <div className="p-8 text-center text-slate-400 text-sm">No documents in this case yet.</div>}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden h-fit">
          <div className="p-4 border-b bg-slate-50 font-bold text-slate-800 flex items-center">
            <Users className="w-5 h-5 mr-2 text-slate-500" /> Assigned Officers
          </div>
          {caseData.assigned_officers?.map((o: any, i: number) => (
            <div key={i} className="p-4 border-b border-slate-100">
              <p className="font-medium text-sm text-slate-800">{o.user_name}</p>
              <p className="text-xs text-slate-500">{o.user_email} • {o.user_role}</p>
              <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded mt-1 inline-block">{o.assignment_role}</span>
            </div>
          ))}
        </div>
      </div>

      {pkgError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {pkgError}
        </div>
      )}

      {pkg && (
        <div className="bg-slate-900 text-white rounded-xl p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="font-bold text-lg">{pkg.court_package_id}</h3>
              <p className="text-xs text-slate-400">{pkg.evidentiary_standard} • {pkg.total_manifest_entries} entries</p>
            </div>
            <button onClick={downloadPackage} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium">Download Manifest JSON</button>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-xs space-y-3">
            {pkg.manifest.map((m: any, i: number) => (
              <div key={i} className="border-b border-slate-700 pb-2">
                <p className="text-cyan-400">{m.document_title} ({m.version})</p>
                <p className="text-emerald-400 break-all">SHA256: {m.sha256_hash}</p>
                <p className="text-slate-400">Block #{m.blockchain_notarization?.block_number} • {m.signatures.length} signature(s)</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
