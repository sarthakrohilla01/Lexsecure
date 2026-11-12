import React, { useEffect, useState } from 'react';
import { useNavigate, Navigate, Link } from 'react-router-dom';
import {
  Shield, ShieldAlert, ShieldCheck, KeyRound, Loader2, Eye, EyeOff, Lock,
  Fingerprint, Cloud, Smartphone, ArrowLeft, Copy, Check, Download, BookOpen,
} from 'lucide-react';
import { apiClient, errorDetail } from '../api/client';
import { useAuth } from '../context/AuthContext';

type Enrollment = {
  token: string;
  qr: string;
  secret: string;
  uri: string;
  account: string;
};

export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [aiStatus, setAiStatus] = useState<any>(null);

  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [enrollCode, setEnrollCode] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [pendingSession, setPendingSession] = useState<{ token: string; user: any } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiClient.get('/ai/status').then((res) => setAiStatus(res.data)).catch(() => {});
  }, []);
  const aiRemote = aiStatus?.generation_mode === 'llm';

  const { login, user } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/auth/login', {
        username: email,
        password,
        mfa_code: mfaCode || null,
      });

      if (response.data.mfa_enrollment_required) {
        const token = response.data.enrollment_token;
        const setup = await apiClient.post('/auth/mfa/setup', null, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setEnrollment({
          token,
          qr: setup.data.qr_data_url,
          secret: setup.data.secret,
          uri: setup.data.otpauth_uri,
          account: setup.data.account,
        });
        return;
      }

      login(response.data.access_token, response.data.user, response.data.mfa_verified);
      navigate('/dashboard');
    } catch (err: any) {
      let errorMsg = 'Authentication failed. Please check credentials.';
      if (err.response?.status === 429) {
        errorMsg = 'Too many failed attempts. Please wait 5 minutes and try again.';
      } else {
        const detail = err.response?.data?.detail;
        if (typeof detail === 'string') {
          errorMsg = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          errorMsg = detail.map((d: any) => d.msg).join(', ');
        }
      }
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActivate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollment) return;
    setIsLoading(true);
    setError('');
    try {
      const res = await apiClient.post(
        '/auth/mfa/activate',
        { code: enrollCode },
        { headers: { Authorization: `Bearer ${enrollment.token}` } },
      );
      setBackupCodes(res.data.backup_codes || []);
      setPendingSession({ token: res.data.access_token, user: res.data.user });
    } catch (err: any) {
      setError(errorDetail(err, 'Could not activate the authenticator.'));
    } finally {
      setIsLoading(false);
    }
  };

  const finishEnrollment = () => {
    if (!pendingSession) return;
    login(pendingSession.token, pendingSession.user, true);
    navigate('/dashboard');
  };

  const copySecret = async () => {
    if (!enrollment) return;
    try {
      await navigator.clipboard.writeText(enrollment.secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {

    }
  };

  const resetEnrollment = () => {
    setEnrollment(null);
    setBackupCodes(null);
    setPendingSession(null);
    setEnrollCode('');
    setMfaCode('');
    setError('');
  };

  const downloadBackupCodes = () => {
    if (!backupCodes) return;
    const body = [
      'LexSecure — MFA backup codes',
      `Account: ${pendingSession?.user?.email || email}`,
      `Generated: ${new Date().toISOString()}`,
      '',
      ...backupCodes,
      '',
      'Each code can be used once. Store this file offline.',
    ].join('\n');
    const url = URL.createObjectURL(new Blob([body], { type: 'text/plain' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'lexsecure-backup-codes.txt';
    link.click();
    URL.revokeObjectURL(url);
  };

  if (user) return <Navigate to="/dashboard" replace />;

  const renderCard = () => {
    if (backupCodes) {
      return (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <h2 className="text-xl font-bold text-slate-800">Authenticator activated</h2>
          </div>
          <p className="text-sm text-slate-500 mb-5">
            Save these single-use backup codes. They are shown only once and can replace a
            lost authenticator at sign-in.
          </p>

          <div className="grid grid-cols-2 gap-2 mb-4 font-mono text-sm">
            {backupCodes.map((code) => (
              <div key={code} className="px-3 py-2 bg-slate-100 border border-slate-200 rounded-md text-slate-800 tracking-wider">
                {code}
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={downloadBackupCodes}
              className="flex-1 inline-flex items-center justify-center gap-2 border border-slate-300 text-slate-700 font-medium py-2.5 rounded-lg hover:bg-slate-50"
            >
              <Download className="w-4 h-4" /> Download
            </button>
            <button
              type="button"
              onClick={finishEnrollment}
              className="flex-1 bg-slate-900 text-white font-medium py-2.5 rounded-lg hover:bg-slate-800"
            >
              Continue to dashboard
            </button>
          </div>
        </div>
      );
    }

    if (enrollment) {
      return (
        <div>
          <button
            type="button"
            onClick={resetEnrollment}
            className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
          >
            <ArrowLeft className="w-4 h-4" /> Back to sign in
          </button>

          <div className="flex items-center gap-2 mb-1">
            <Smartphone className="w-5 h-5 text-cyan-600" />
            <h2 className="text-xl font-bold text-slate-800">Set up your authenticator</h2>
          </div>
          <p className="text-sm text-slate-500 mb-5">
            Scan the QR code with Google Authenticator, 1Password, Authy or any TOTP app,
            then enter the 6-digit code it shows.
          </p>

          {error && (
            <div className="mb-5 p-3 bg-red-50 border-l-4 border-red-500 rounded text-sm text-red-700" role="alert">
              {error}
            </div>
          )}

          <div className="flex justify-center mb-4">
            <img
              src={enrollment.qr}
              alt={`QR code for ${enrollment.account}`}
              className="w-48 h-48 rounded-lg border border-slate-200 bg-white p-2"
            />
          </div>

          <div className="mb-5">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
              Can't scan? Enter this key manually
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2 bg-slate-100 border border-slate-200 rounded-md text-xs text-slate-800 break-all">
                {enrollment.secret}
              </code>
              <button
                type="button"
                onClick={copySecret}
                aria-label="Copy secret"
                className="p-2 border border-slate-300 rounded-md text-slate-600 hover:bg-slate-50"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Account: {enrollment.account} · 6 digits · 30-second period
            </p>
          </div>

          <form onSubmit={handleActivate} className="space-y-4">
            <div>
              <label htmlFor="enroll-code" className="block text-sm font-medium text-slate-700 mb-1">
                Verification code
              </label>
              <input
                id="enroll-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={enrollCode}
                onChange={(e) => setEnrollCode(e.target.value.replace(/\D/g, ''))}
                className="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 bg-slate-50 font-mono tracking-[0.3em] text-center text-lg"
                placeholder="••••••"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || enrollCode.length !== 6}
              className="w-full bg-slate-900 text-white font-medium py-3 rounded-lg hover:bg-slate-800 transition-colors flex justify-center items-center disabled:opacity-60"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Activate authenticator'}
            </button>
          </form>
        </div>
      );
    }

    return (
      <>
        <h2 className="text-xl font-bold text-slate-800 mb-1">Authorized Access Only</h2>
        <p className="text-sm text-slate-500 mb-6">Sign in with your officer credentials — authenticator code only if MFA is enabled</p>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded flex items-start" role="alert">
            <ShieldAlert className="w-5 h-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-5">
          <div>
            <label htmlFor="officer" className="block text-sm font-medium text-slate-700 mb-1">Officer Email</label>
            <input
              id="officer"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              autoFocus
              placeholder="officer@ncrb.gov.in"
              className="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full px-4 py-2.5 pr-12 border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                title={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-slate-700 rounded-md hover:bg-slate-100 transition-colors"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div>
            <label htmlFor="mfa" className="block text-sm font-medium text-slate-700 mb-1 flex items-center">
              <KeyRound className="w-4 h-4 mr-1 text-slate-500" /> Authenticator code (if MFA enabled)
            </label>
            <input
              id="mfa"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
              className="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 bg-slate-50 font-mono tracking-[0.3em] text-center text-lg"
              placeholder="••••••"
            />
            <p className="text-xs text-slate-500 mt-1">
              Leave blank for password-only test accounts. Other accounts may also use a single-use backup code.
            </p>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-slate-900 text-white font-medium py-3 rounded-lg hover:bg-slate-800 transition-colors flex justify-center items-center disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Authenticate & Login'}
          </button>
        </form>
      </>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 pointer-events-none" />
      <div className="absolute -top-32 -right-32 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -left-32 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-md w-full relative">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-slate-800/80 border border-slate-700 mb-4 shadow-xl">
            <Shield className="w-10 h-10 text-cyan-400" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">LEXSECURE</h1>
          <p className="text-slate-400 mt-2">Secure Digital Document Management System</p>
          <div
            className={`mt-3 inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider px-3 py-1 rounded-full border ${
              !aiStatus
                ? 'bg-slate-500/10 text-slate-400 border-slate-500/30'
                : aiRemote
                  ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                  : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            }`}
            title={
              !aiStatus
                ? 'Checking how AI answers are generated…'
                : aiRemote
                  ? 'AI answers are generated by the configured external LLM. Only evidence chunks the signed-in officer is authorized to view are ever sent.'
                  : 'Answer synthesis runs locally on this machine.'
            }
          >
            {!aiStatus ? <Loader2 className="w-3 h-3 animate-spin" /> : aiRemote ? <Cloud className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
            {!aiStatus
              ? 'Checking AI processing mode…'
              : aiRemote
                ? `${aiStatus?.llm_provider || 'AI'} AI enabled — only authorized excerpts are sent`
                : 'Local synthesis — no evidence leaves this machine'}
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8 border border-slate-200">
          {renderCard()}

          <div className="mt-6 pt-5 border-t border-slate-100 grid grid-cols-2 gap-3 text-xs text-slate-500">
            <div className="flex items-center gap-1.5"><Fingerprint className="w-4 h-4 text-emerald-500" /> TOTP MFA enforced</div>
            <div className="flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-emerald-500" /> AES-256 + RSA-PSS</div>
          </div>
        </div>

        <p className="text-center text-xs text-slate-500 mt-4">
          Encrypted at rest · ABAC-enforced retrieval · every access audited
        </p>

        <div className="text-center mt-4">
          <Link
            to="/guide"
            className="inline-flex items-center text-xs text-slate-400 hover:text-cyan-400 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5 mr-1.5" />
            New here? Read the Guide
          </Link>
        </div>
      </div>
    </div>
  );
};
