import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, Download, Hash, FileSignature, GitCommit, Play, RefreshCcw, MessageSquare, CheckCircle, XCircle, Upload } from 'lucide-react';
import { apiClient, errorDetail } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const DocumentDetailPage = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const [doc, setDoc] = useState<any>(null);
  const [integrityReport, setIntegrityReport] = useState<any>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [comments, setComments] = useState<any[]>([]);
  const [commentText, setCommentText] = useState('');
  const [auditTrail, setAuditTrail] = useState<any[]>([]);
  const [reviewNotes, setReviewNotes] = useState('');
  const [versionReason, setVersionReason] = useState('');
  const [newVersionFile, setNewVersionFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [previewImageMime, setPreviewImageMime] = useState<string>('image/png');
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  const [dualAuthStatus, setDualAuthStatus] = useState<string | null>(null);
  const [unlockToken, setUnlockToken] = useState<string | null>(null);
  const [grantExpiresAt, setGrantExpiresAt] = useState<string | null>(null);
  const [locked, setLocked] = useState<any | null>(null);
  const [nowMs, setNowMs] = useState<number>(Date.now());

  const authHeaders = (token?: string | null) =>
    token ? { 'X-Unlock-Token': token } : {};

  const fetchDoc = async (tokenOverride?: string | null) => {
    const token = tokenOverride !== undefined ? tokenOverride : unlockToken;
    try {
      const res = await apiClient.get(`/documents/${id}`, {
        headers: authHeaders(token),
      });
      setDoc(res.data);
      setLocked(null);
      if (res.data.requires_dual_auth) {
        checkDualAuth();
      }
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      if (e.response?.status === 403 && detail && typeof detail === 'object' && detail.error === 'TWO_MAN_RULE_REQUIRED') {
        setLocked(detail);
        setDoc(null);
        checkDualAuth();
      } else {
        setActionMsg(errorDetail(e, 'Failed to reload document state.'));
      }
    }
  };

  const checkDualAuth = async () => {
    try {
      const res = await apiClient.get('/approvals/my-requests');
      const req = [...res.data]
        .filter((r: any) => r.document_id === Number(id))
        .sort((a: any, b: any) => b.id - a.id)[0];
      if (req) {
        setDualAuthStatus(req.status);
        setGrantExpiresAt(req.expires_at || null);
        if (req.status === 'APPROVED' && req.unlock_token && req.unlock_token !== unlockToken) {
          setUnlockToken(req.unlock_token);
          await fetchDoc(req.unlock_token);
        }
      }
    } catch (e: any) {
      setActionMsg(errorDetail(e, 'Could not read the approval status.'));
    }
  };

  const requestDualAuth = async () => {
    setActionMsg('');
    try {
      const res = await apiClient.post('/approvals/request', { document_id: Number(id) });
      setDualAuthStatus(res.data.status);
      if (res.data.status === 'APPROVED' && res.data.unlock_token) {
        setUnlockToken(res.data.unlock_token);
        setGrantExpiresAt(res.data.expires_at || null);
        await fetchDoc(res.data.unlock_token);
      } else {
        setActionMsg('Access request sent to a supervisor. This page will unlock automatically once granted.');
      }
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      setActionMsg(errorDetail(e, 'Failed to send access request.'));
    }
  };

  useEffect(() => {
    if (!grantExpiresAt) return;
    const t = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(t);
  }, [grantExpiresAt]);

  const grantRemainingMs = grantExpiresAt ? new Date(grantExpiresAt).getTime() - nowMs : null;
  const grantRemainingLabel = grantRemainingMs == null ? '' : grantRemainingMs <= 0 ? 'expired'
    : `${Math.floor(grantRemainingMs / 60000)}:${String(Math.floor((grantRemainingMs % 60000) / 1000)).padStart(2, '0')}`;

  const fetchComments = () => {
    apiClient.get(`/workflow/comments/${id}`).then(res => setComments(res.data)).catch(() => {});
  };
  const fetchAudit = () => {
    apiClient.get(`/audit/document/${id}`).then(res => setAuditTrail(res.data)).catch(() => {});
  };

  useEffect(() => {
    fetchDoc();
    fetchComments();
    fetchAudit();
  }, [id]);

  const sniffImageMime = (bytes: Uint8Array, declared: string): string | null => {
    if (declared && declared.startsWith('image/')) return declared;
    if (bytes.length > 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) return 'image/png';
    if (bytes.length > 2 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg';
    if (bytes.length > 5 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) return 'image/gif';
    if (bytes.length > 11 && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50) return 'image/webp';
    if (bytes.length > 1 && bytes[0] === 0x42 && bytes[1] === 0x4d) return 'image/bmp';
    return null;
  };
  useEffect(() => {
    if (!doc) return;
    if (doc.is_tampered) {
      setPreviewLoading(false);
      setPreviewError('TAMPERED_STATE');
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError('');
    setPreviewUrl(null);
    setPreviewImageUrl(null);
    setPreviewText(null);
    apiClient.get(`/documents/${id}/download`, {
      responseType: 'blob',
      headers: authHeaders(),
    })
      .then(async (res) => {
        const buf = await (res.data as Blob).arrayBuffer();
        if (cancelled) return;
        const bytes = new Uint8Array(buf);
        const isPdf = bytes.length > 4 &&
          bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46;
        if (isPdf) {
          objectUrl = URL.createObjectURL(new Blob([buf], { type: 'application/pdf' }));
          setPreviewUrl(objectUrl);
          return;
        }
        const declaredMime = doc?.versions?.[0]?.mime_type || '';
        const imageMime = sniffImageMime(bytes, declaredMime);
        if (imageMime) {
          objectUrl = URL.createObjectURL(new Blob([buf], { type: imageMime }));
          setPreviewImageUrl(objectUrl);
          setPreviewImageMime(imageMime);
          return;
        }
        setPreviewText(new TextDecoder('utf-8', { fatal: false }).decode(buf));
      })
      .catch(() => { if (!cancelled) setPreviewError('Preview unavailable for this version.'); })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [doc, id, unlockToken]);

  const verifyIntegrity = async (versionId: number) => {
    setIsVerifying(true);
    setActionMsg('');
    try {
      const res = await apiClient.post(`/integrity/verify/${versionId}`);
      setIntegrityReport(res.data);
      await fetchDoc();
    } catch (e: any) {
      setActionMsg(errorDetail(e, 'Integrity check failed. Please retry.'));
    } finally {
      setIsVerifying(false);
    }
  };

  const runTamperDrill = async (versionId: number) => {
    setIsVerifying(true);
    setActionMsg('');
    try {
      const res = await apiClient.post(`/integrity/tamper-test/${versionId}`);
      setIntegrityReport(res.data);
      await fetchDoc();
    } catch (e: any) {
      setActionMsg(errorDetail(e, 'Integrity drill failed. Please retry.'));
    } finally {
      setIsVerifying(false);
    }
  };

  const restoreDocument = async (versionId: number) => {
    setIsVerifying(true);
    setActionMsg('');
    try {
      const res = await apiClient.post(`/integrity/restore/${versionId}`);
      setIntegrityReport(res.data);
      await fetchDoc();
      if (res.data?.is_valid) {
        setActionMsg('Clean document restored and re-verified against the ledger.');
      } else {
        setActionMsg('Restore ran but verification still fails — see report details below.');
      }
    } catch (e: any) {
      setActionMsg(errorDetail(e, 'Restore failed — no state was changed. Please retry.'));
    } finally {
      setIsVerifying(false);
    }
  };

  const downloadDoc = async (version?: number) => {
    setActionMsg('');
    try {
      const urlQuery = new URLSearchParams();
      if (version) urlQuery.append('version', version.toString());
      const qs = urlQuery.toString();
      const res = await apiClient.get(`/documents/${id}/download${qs ? `?${qs}` : ''}`, {
        responseType: 'blob',
        headers: authHeaders(),
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc?.versions?.[0]?.file_name || `document-${id}.bin`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      try {
        const text = await (e.response?.data as Blob)?.text?.();
        const parsed = text ? JSON.parse(text) : null;
        setActionMsg(parsed?.detail || 'Download failed');
      } catch {
        setActionMsg(e.response?.status === 409
          ? 'Download blocked: this version failed integrity verification. Restore it first.'
          : 'Download failed');
      }
    }
  };

  const signDoc = async () => {
    setActionMsg('');
    try {
      const res = await apiClient.post(`/documents/${id}/sign`, { document_id: Number(id), action: 'SIGN' });
      setActionMsg(`Signed successfully — Ledger Block #${res.data.ledger_block_number}`);
      fetchDoc();
    } catch (e: any) { setActionMsg(errorDetail(e, 'Sign failed')); }
  };

  const unsignDoc = async () => {
    if (!window.confirm('Remove signature(s) from the current version? The revocation itself is notarized on the ledger and audit trail.')) return;
    setActionMsg('');
    try {
      const res = await apiClient.delete(`/documents/${id}/sign`);
      setActionMsg(`Signature revoked — Ledger Block #${res.data.ledger_block_number}`);
      fetchDoc();
    } catch (e: any) { setActionMsg(errorDetail(e, 'Revoke failed')); }
  };

  const approveDoc = async (approve: boolean) => {
    setActionMsg('');
    try {
      const endpoint = approve ? '/workflow/approve' : '/workflow/reject';
      await apiClient.post(endpoint, { document_id: Number(id), action: approve ? 'APPROVE' : 'REJECT', notes: reviewNotes });
      setActionMsg(approve ? 'Document APPROVED and notarized on ledger.' : 'Document REJECTED.');
      setReviewNotes('');
      fetchDoc();
    } catch (e: any) { setActionMsg(errorDetail(e, 'Workflow action failed')); }
  };

  const postComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    try {
      await apiClient.post('/workflow/comments', { document_id: Number(id), content: commentText });
      setCommentText('');
      fetchComments();
    } catch (e: any) {
      setActionMsg(errorDetail(e, 'Could not post the note.'));
    }
  };

  const uploadNewVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVersionFile) return;
    const fd = new FormData();
    fd.append('file', newVersionFile);
    fd.append('change_reason', versionReason || 'Updated document version');
    try {
      await apiClient.post(`/documents/${id}/versions`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setNewVersionFile(null);
      setVersionReason('');
      setActionMsg('New version uploaded, hashed, and notarized.');
      fetchDoc();
    } catch (err: any) { setActionMsg(errorDetail(err, 'Version upload failed')); }
  };

  if (!doc) {
    if (locked) {
      return (
        <div className="max-w-2xl mx-auto">
          <div className="bg-slate-900 text-white rounded-2xl shadow-xl overflow-hidden">
            <div className="p-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/15 border border-red-400/40 mb-4">
                <ShieldAlert className="w-8 h-8 text-red-400" />
              </div>
              <p className="text-xs font-bold tracking-widest text-red-400 uppercase mb-2">Sealed · Two-Man Rule</p>
              <h2 className="text-2xl font-bold">{locked.document_title || `Document #${locked.document_id}`}</h2>
              <p className="text-slate-400 text-sm mt-3 max-w-md mx-auto">
                {locked.message || 'Supervisor approval is required before viewing or download.'}
              </p>
              <p className="text-xs text-slate-500 mt-2">No content, hash, or metadata is exposed until a grant is issued.</p>
            </div>
            <div className="bg-slate-800/70 px-8 py-5">
              {dualAuthStatus === 'APPROVED' && unlockToken ? (
                <div className="text-center">
                  <p className="text-emerald-400 font-bold flex items-center justify-center gap-2">
                    <ShieldCheck className="w-5 h-5" /> Access Granted
                    {grantRemainingLabel && grantRemainingLabel !== 'expired' && (
                      <span className="font-mono bg-emerald-500/15 border border-emerald-400/30 rounded px-2 py-0.5">expires in {grantRemainingLabel}</span>
                    )}
                  </p>
                  <button onClick={() => fetchDoc()} className="mt-3 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors">
                    Enter Sealed Document
                  </button>
                </div>
              ) : dualAuthStatus === 'PENDING' ? (
                <div className="text-center">
                  <p className="text-amber-400 font-bold">Request Pending</p>
                  <p className="text-slate-400 text-sm mt-1">A supervisor has been notified. This page unlocks automatically once granted.</p>
                  <button onClick={() => checkDualAuth()} className="mt-3 px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors">
                    Check Again
                  </button>
                </div>
              ) : dualAuthStatus === 'REJECTED' ? (
                <div className="text-center">
                  <p className="text-red-400 font-bold">Request Rejected</p>
                  <p className="text-slate-400 text-sm mt-1">Contact your supervising officer for the grounds of refusal.</p>
                  <button onClick={requestDualAuth} className="mt-3 px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors">
                    Request Again
                  </button>
                </div>
              ) : (
                <button onClick={requestDualAuth} className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-medium rounded-lg transition-colors">
                  Request Supervisor Access
                </button>
              )}
              {actionMsg && <p className="text-sm mt-3 text-center text-cyan-300">{actionMsg}</p>}
            </div>
          </div>
        </div>
      );
    }
    return <div className="p-8">Loading secure document...</div>;
  }
  const currentVer = doc.versions[0];
  const canApprove = user && ['SUPERVISOR', 'LEGAL_OFFICER', 'ADMINISTRATOR'].includes(user.role);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex justify-between items-start">
        <div>
          <div className="flex items-center space-x-3 mb-2">
            <span className="px-3 py-1 bg-slate-100 text-slate-700 text-xs font-bold rounded-full">{doc.document_type}</span>
            <span className={`px-3 py-1 text-xs font-bold rounded-full ${doc.classification === 'SECRET' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'}`}>{doc.classification}</span>
            <span className="px-3 py-1 bg-indigo-100 text-indigo-700 text-xs font-bold rounded-full">v{doc.current_version}</span>
            <span className="px-3 py-1 bg-slate-900 text-white text-xs font-bold rounded-full">{doc.status}</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mb-1">{doc.title}</h2>
          <p className="text-slate-500 text-sm">Case: {doc.case_id} • Uploaded by {doc.uploaded_by_name}</p>
          {doc.requires_dual_auth && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="px-3 py-1 bg-red-100 text-red-700 text-xs font-bold rounded-full border border-red-200">SEALED · TWO-MAN RULE</span>
              {unlockToken && grantRemainingLabel && grantRemainingLabel !== 'expired' && (
                <span className="px-3 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded-full border border-emerald-200 font-mono">
                  ACCESS GRANTED · {grantRemainingLabel}
                </span>
              )}
            </div>
          )}
          {actionMsg && <p className="text-sm mt-2 px-3 py-2 bg-indigo-50 text-indigo-700 rounded border border-indigo-100">{actionMsg}</p>}
        </div>
        <div className="flex flex-col gap-2">
          <button onClick={() => downloadDoc()} className="flex items-center px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 text-sm font-medium">
            <Download className="w-4 h-4 mr-2" /> Download
          </button>
          {doc.can_sign && !doc.signed_by_me && (
            <button onClick={signDoc} className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 text-sm font-medium">
              <FileSignature className="w-4 h-4 mr-2" /> Sign (RSA-2048)
            </button>
          )}
          {doc.signed_by_me && (
            <button onClick={unsignDoc} className="flex items-center px-4 py-2 bg-white border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50 text-sm font-medium" title="Revoke your signature — the revocation is recorded on the ledger">
              <FileSignature className="w-4 h-4 mr-2" /> Unsign (Revoke Mine)
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b bg-slate-50 flex items-center">
              <Hash className="w-5 h-5 text-slate-500 mr-2" />
              <h3 className="font-bold text-slate-800">Cryptographic Identity</h3>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase mb-1">SHA-256 Document Hash (Immutable)</p>
                <div className="bg-slate-900 text-emerald-400 font-mono text-sm p-3 rounded-lg break-all">{currentVer.sha256_hash}</div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 p-3 rounded-lg border"><p className="text-xs text-slate-500">Encryption</p><p className="font-semibold">AES-256-GCM</p></div>
                <div className="bg-slate-50 p-3 rounded-lg border"><p className="text-xs text-slate-500">File Size</p><p className="font-semibold">{(currentVer.file_size / 1024).toFixed(2)} KB</p></div>
              </div>
              {currentVer.signatures.length > 0 && (
                <div className="mt-4 pt-4 border-t">
                  <h4 className="text-sm font-bold text-slate-700 flex items-center mb-3"><FileSignature className="w-4 h-4 mr-2 text-indigo-500" /> Digital Signatures ({currentVer.signatures.length})</h4>
                  {currentVer.signatures.map((sig: any, idx: number) => (
                    <div key={idx} className="flex items-start bg-indigo-50 p-3 rounded-lg border border-indigo-100 mb-2">
                      <ShieldCheck className="w-5 h-5 text-indigo-600 mt-0.5 mr-3" />
                      <div>
                        <p className="text-sm font-semibold text-indigo-900">{sig.signer_name} ({sig.signer_role})</p>
                        <p className="text-xs text-indigo-700 font-mono mt-1">Sig: {sig.signature_hex.substring(0, 40)}...</p>
                        <p className="text-xs text-indigo-600 mt-1">{sig.algorithm} • {new Date(sig.signed_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b bg-slate-50 flex items-center justify-between">
              <h3 className="font-bold text-slate-800 flex items-center">
                <Download className="w-5 h-5 text-slate-500 mr-2" /> Document Preview
              </h3>
              <span className="text-xs text-slate-400">decrypted locally, never uploaded</span>
            </div>
            <div className="p-4">
              {previewLoading && <p className="text-sm text-slate-500 py-8 text-center">Decrypting preview...</p>}
              {previewError === 'TAMPERED_STATE' && (
                <div className="py-6 text-center">
                  <p className="font-bold text-red-600">⚠ Preview unavailable — payload is TAMPERED</p>
                  <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto">
                    This is the expected result of the integrity drill: the vault bytes no longer
                    match their cryptographic seal, so nothing can be decrypted or rendered.
                    Click <span className="font-semibold">“Restore Clean Document”</span> on the
                    right to bring the preview back.
                  </p>
                </div>
              )}
              {previewError && previewError !== 'TAMPERED_STATE' && <p className="text-sm text-red-600 py-4 text-center">{previewError}</p>}
              {previewUrl && (
                <iframe src={previewUrl} title="Document preview" className="w-full h-[600px] rounded-lg border border-slate-200 bg-slate-100" />
              )}
              {previewImageUrl && (
                <div className="text-center">
                  <img src={previewImageUrl} alt="Evidence preview" className="max-h-[600px] mx-auto rounded-lg border border-slate-200 bg-slate-100 object-contain" />
                  <p className="text-xs text-slate-400 mt-2">Decrypted image evidence ({previewImageMime}) — vault copy stays AES-256 encrypted.</p>
                </div>
              )}
              {previewText !== null && (
                <div>
                  <p className="text-xs text-slate-400 mb-2">Text-based exhibit — rendered as text (original bytes preserved for integrity).</p>
                  <pre className="whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 p-4 rounded-lg border border-slate-200 max-h-[600px] overflow-y-auto font-sans">{previewText}</pre>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="p-4 border-b bg-slate-50 flex items-center"><GitCommit className="w-5 h-5 text-slate-500 mr-2" /><h3 className="font-bold">Version History</h3></div>
            {doc.versions.map((v: any, index: number) => (
              <div key={v.id} className={`p-4 border-b flex items-start ${index === 0 ? 'bg-blue-50/30' : ''}`}>
                <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${index === 0 ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>v{v.version_number}</span>
                <div className="ml-4 flex-1">
                  <div className="flex justify-between"><p className="font-semibold">{v.change_reason || 'Initial upload'}</p><span className="text-xs text-slate-500">{new Date(v.created_at).toLocaleString()}</span></div>
                  <p className="text-sm text-slate-500 mt-1">By: {v.uploader_name}</p>
                  <p className="text-xs font-mono text-slate-400 mt-1">Hash: {v.sha256_hash.substring(0, 20)}...</p>
                  {index !== 0 && <button onClick={() => downloadDoc(v.version_number)} className="text-xs text-indigo-600 hover:underline mt-1">Download v{v.version_number}</button>}
                </div>
              </div>
            ))}
            <form onSubmit={uploadNewVersion} className="p-4 bg-slate-50 flex gap-2 items-center">
              <Upload className="w-4 h-4 text-slate-400" />
              <input type="file" onChange={e => setNewVersionFile(e.target.files?.[0] || null)} className="text-sm flex-1" />
              <input
                type="text"
                value={versionReason}
                onChange={e => setVersionReason(e.target.value)}
                placeholder="Reason for this version"
                className="text-sm flex-1 px-3 py-1.5 border rounded-lg"
              />
              <button type="submit" disabled={!newVersionFile} className="px-3 py-1.5 bg-slate-900 text-white text-sm rounded-lg disabled:opacity-40">Upload v{doc.current_version + 1}</button>
            </form>
          </div>

          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="p-4 border-b bg-slate-50 flex items-center"><MessageSquare className="w-5 h-5 text-slate-500 mr-2" /><h3 className="font-bold">Investigation Notes ({comments.length})</h3></div>
            <div className="p-4 space-y-3 max-h-64 overflow-y-auto">
              {comments.map((c: any) => (
                <div key={c.id} className="bg-slate-50 p-3 rounded-lg border">
                  <p className="text-xs font-bold text-slate-700">{c.user_name} <span className="font-normal text-slate-400">({c.user_role}) • {new Date(c.created_at).toLocaleString()}</span></p>
                  <p className="text-sm text-slate-700 mt-1">{c.content}</p>
                </div>
              ))}
              {comments.length === 0 && <p className="text-sm text-slate-400">No notes yet.</p>}
            </div>
            <form onSubmit={postComment} className="p-4 border-t flex gap-2">
              <input value={commentText} onChange={e => setCommentText(e.target.value)} placeholder="Add investigation note..." className="flex-1 px-3 py-2 border rounded-lg text-sm" />
              <button type="submit" className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg">Post</button>
            </form>
          </div>

          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="p-4 border-b bg-slate-50 font-bold">Chain-of-Custody Audit ({auditTrail.length})</div>
            <div className="p-4 space-y-2 max-h-64 overflow-y-auto">
              {auditTrail.map((a: any) => (
                <div key={a.id} className="text-xs border-l-2 border-indigo-200 pl-3 py-1">
                  <p className="font-mono text-indigo-700">{a.action} • {a.status}</p>
                  <p className="text-slate-600">{a.details}</p>
                  <p className="text-slate-400">{a.user_email} • {new Date(a.timestamp).toLocaleString()}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-slate-900 rounded-xl shadow-lg border border-slate-800 text-white overflow-hidden">
            <div className="p-5 border-b border-slate-800">
              <h3 className="font-bold text-lg flex items-center"><ShieldCheck className="w-5 h-5 text-cyan-400 mr-2" /> Integrity Verification</h3>
              <p className="text-slate-400 text-sm mt-1">Validate chain of custody</p>
            </div>
            <div className="p-5 space-y-4">
              <button onClick={() => verifyIntegrity(currentVer.id)} disabled={isVerifying} className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 rounded-lg font-medium">
                {isVerifying ? 'Verifying...' : 'Verify Document Integrity'}
              </button>
              <div className="pt-4 border-t border-slate-800">
                <h4 className="text-sm text-slate-400 mb-3 uppercase text-center font-semibold">Integrity Drill</h4>
                {!currentVer.is_tampered ? (
                  <button onClick={() => runTamperDrill(currentVer.id)} disabled={isVerifying} className="w-full py-2 border border-red-500/50 hover:bg-red-500/20 text-red-400 rounded-lg text-sm flex justify-center items-center">
                    <Play className="w-4 h-4 mr-2" /> Run Tamper Drill
                  </button>
                ) : (
                  <button onClick={() => restoreDocument(currentVer.id)} disabled={isVerifying} className="w-full py-2 border border-emerald-500/50 hover:bg-emerald-500/20 text-emerald-400 rounded-lg text-sm flex justify-center items-center">
                    <RefreshCcw className="w-4 h-4 mr-2" /> Restore Clean Document
                  </button>
                )}
              </div>
            </div>
          </div>

          {canApprove && (
            <div className="bg-white rounded-xl border p-5 space-y-3">
              <h3 className="font-bold text-sm">Supervisory Review</h3>
              <textarea value={reviewNotes} onChange={e => setReviewNotes(e.target.value)} placeholder="Review notes..." className="w-full px-3 py-2 border rounded-lg text-sm" rows={2} />
              <div className="flex gap-2">
                <button onClick={() => approveDoc(true)} className="flex-1 py-2 bg-emerald-600 text-white text-sm rounded-lg flex items-center justify-center"><CheckCircle className="w-4 h-4 mr-1" /> Approve</button>
                <button onClick={() => approveDoc(false)} className="flex-1 py-2 bg-red-600 text-white text-sm rounded-lg flex items-center justify-center"><XCircle className="w-4 h-4 mr-1" /> Reject</button>
              </div>
            </div>
          )}

          {integrityReport && (
            <div className={`rounded-xl shadow-lg border overflow-hidden ${integrityReport.is_valid ? 'bg-white border-emerald-200' : 'bg-red-50 border-red-300'}`}>
              <div className={`p-4 border-b flex items-center ${integrityReport.is_valid ? 'bg-emerald-50 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                {integrityReport.is_valid ? <ShieldCheck className="w-6 h-6 mr-2" /> : <ShieldAlert className="w-6 h-6 mr-2" />}
                <h3 className="font-bold">{integrityReport.is_valid ? 'INTEGRITY VERIFIED' : '⚠ TAMPERING DETECTED'}</h3>
              </div>
              <div className="p-5 space-y-3 text-sm">
                {!integrityReport.is_valid && (
                  <div className="bg-white p-3 rounded border border-red-200">
                    <p className="font-bold text-red-600 mb-1">Hash Mismatch</p>
                    <p className="text-xs text-slate-500">Expected (Ledger):</p>
                    <p className="font-mono text-xs text-emerald-600 break-all">{integrityReport.expected_hash}</p>
                    <p className="text-xs text-slate-500 mt-2">Actual (Payload):</p>
                    <p className="font-mono text-xs text-red-600 break-all">{integrityReport.actual_hash}</p>
                  </div>
                )}
                <p><span className="text-xs uppercase font-bold text-slate-500">Decryption: </span>{integrityReport.decryption_status}</p>
                <p><span className="text-xs uppercase font-bold text-slate-500">Signature: </span>{integrityReport.digital_signature?.status}</p>
                <p><span className="text-xs uppercase font-bold text-slate-500">Ledger: </span>{integrityReport.blockchain_ledger?.status} {integrityReport.blockchain_ledger?.block_number && `(Block #${integrityReport.blockchain_ledger.block_number})`}</p>
                <div className="p-3 bg-slate-900 text-white rounded text-xs">{integrityReport.details}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
