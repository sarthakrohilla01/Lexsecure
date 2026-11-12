import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpen, Rocket, Users, Compass, ListTree, HelpCircle, AlertTriangle,
  ShieldCheck, KeyRound, FileText, Download, ArrowRight, Terminal,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

type Section = 'start' | 'accounts' | 'tour' | 'controls' | 'glossary' | 'trouble';

const SECTIONS: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'start', label: 'Start here', icon: <Rocket /> },
  { id: 'accounts', label: 'Accounts', icon: <Users /> },
  { id: 'tour', label: 'App tour', icon: <Compass /> },
  { id: 'controls', label: 'Every control', icon: <ListTree /> },
  { id: 'glossary', label: 'Glossary', icon: <BookOpen /> },
  { id: 'trouble', label: 'Troubleshooting', icon: <AlertTriangle /> },
];

const DEMO_ACCOUNTS = [
  { email: 'demo.admin@lexsecure.local', role: 'Administrator', sees: 'everything' },
  { email: 'demo.supervisor@lexsecure.local', role: 'Supervisor', sees: 'every case' },
  { email: 'demo.investigator@lexsecure.local', role: 'Investigator', sees: 'CASE-2026-001 only' },
  { email: 'demo.forensic@lexsecure.local', role: 'Forensic Expert', sees: 'CASE-2026-001, -002' },
  { email: 'demo.legal@lexsecure.local', role: 'Legal Officer', sees: 'CASE-2026-002, -003' },
];

const SEEDED_ACCOUNTS = [
  { email: 'investigator@lexsecure.local', role: 'Investigator' },
  { email: 'forensic@lexsecure.local', role: 'Forensic Expert' },
  { email: 'legal@lexsecure.local', role: 'Legal Officer' },
  { email: 'supervisor@lexsecure.local', role: 'Supervisor' },
  { email: 'admin@lexsecure.local', role: 'Administrator' },
];

const TOUR = [
  { img: '02-dashboard.png', name: 'Dashboard', route: '/dashboard', what: 'System metrics, your pending approvals and the health of every subsystem. The LIVE FEED badge in the top bar means the real-time event stream is connected.' },
  { img: '03-cases.png', name: 'Cases', route: '/cases', what: 'Every case, badged AUTHORIZED or NO ACCESS depending on your assignment. The boundary is enforced in the API, not in the UI.' },
  { img: '04-case-detail.png', name: 'Case detail', route: '/cases/CASE-2026-001', what: 'Documents, assigned officers and the Court Package (65B) button that generates a court-ready evidentiary manifest.' },
  { img: '05-documents.png', name: 'Documents', route: '/documents', what: 'Every document you are cleared to see, with version, status, the SEALED badge and a live integrity indicator.' },
  { img: '06-document-detail.png', name: 'Document detail', route: '/documents', what: 'The cryptographic identity — SHA-256 hash, RSA-2048 signature — plus preview, version history, notes and the custody audit.' },
  { img: '07-integrity-ledger.png', name: 'Integrity Ledger', route: '/integrity', what: 'The append-only custody chain. Every block links to the one before it, so altering any historical block breaks every link that follows.' },
  { img: '08-ai-search.png', name: 'AI Search', route: '/search', what: 'Semantic search over the evidence corpus. The access filter runs before ranking, so unauthorized chunks are never scored.' },
  { img: '09-ai-assistant.png', name: 'AI Assistant', route: '/assistant', what: 'Ask questions in plain language and get an answer with inline source citations. Only documents within your clearance are ever read.' },
  { img: '10-audit-trail.png', name: 'Audit Trail', route: '/audit', what: 'Every security event — including failures. Export CSV or JSON and the response carries a SHA-256 attestation of the exact bytes you received.' },
  { img: '11-administration.png', name: 'Administration', route: '/admin', what: 'Officer directory, live AI provider health and the RBAC + ABAC policy matrix. Supervisors and Administrators only.' },
  { img: '12-leak-investigator.png', name: 'Leak Investigator', route: '/leak', what: 'Upload a file found outside the system and the scan reveals whose download it came from. Text documents only.' },
];

const CONTROLS = [
  { group: 'Header', items: [
    ['LIVE FEED', 'The WebSocket to the server is connected — tamper alerts and uploads arrive instantly. FEED OFFLINE means it is reconnecting.'],
    ['MFA VERIFIED', 'Your second factor was confirmed for this session.'],
    ['Avatar (D)', 'Opens your profile: name, role, badge number, MFA state and the cases you are assigned to. Sign Out lives here.'],
  ]},
  { group: 'Documents list', items: [
    ['SEALED', 'The document is under the Two-Man Rule. A supervisor must grant access before it opens.'],
    ['SECURE / ⚠ ALERT', 'Green means the payload still matches its hash, signature and ledger anchor. Red means verification failed.'],
    ['v1, v2', 'Each version is separately hashed, signed and anchored, so history is provable.'],
  ]},
  { group: 'Document detail', items: [
    ['SHA-256 Document Hash', 'The fingerprint of this exact version. One changed byte changes the whole hash.'],
    ['Verify Document Integrity', 'Re-checks three independent anchors: the decrypted bytes, the RSA signature, and the ledger block.'],
    ['Run Tamper Drill', 'Supervisor/Admin only. Genuinely alters the stored bytes so the detection stack is exercised end to end — not a simulated flag.'],
    ['Restore Clean Document', 'Puts the sealed original back and re-verifies it.'],
    ['Sign / Unsign', 'Sign notarises your approval on the ledger. Unsign removes it — and the revocation is itself notarised and audited.'],
  ]},
  { group: 'Upload dialog', items: [
    ['Case (assigned only)', 'Only cases you are assigned to are listed.'],
    ['Evidence File', 'pdf, txt, docx, jpg, png up to 50 MB. Scanned before anything is stored.'],
    ['Type / Classification', 'Leave the type blank and it is auto-classified from the content. SECRET and above need lead clearance to read.'],
  ]},
  { group: 'Two-Man Rule', items: [
    ['Request Supervisor Access', 'Sealed documents need a second, senior officer. The page unlocks automatically once granted.'],
    ['Grant Access', 'Issues a 2-hour unlock token bound to that officer and that document. Audit-logged.'],
  ]},
  { group: 'Audit Trail', items: [
    ['Export CSV / JSON', 'Downloads the filtered trail with an X-Export-SHA256 header attesting to the exact bytes shipped. The export is written back into the trail.'],
  ]},
];

const GLOSSARY = [
  ['ABAC', 'Attribute-Based Access Control — access depends on your assignment to a case, not only your job title.'],
  ['RBAC', 'Role-Based Access Control — access depends on your role.'],
  ['TOTP', 'The 6-digit authenticator code (RFC 6238). Changes every 30 seconds.'],
  ['MFA / 2FA', 'Password plus something you hold.'],
  ['Hash (SHA-256)', 'A one-way fingerprint of a file.'],
  ['Signature (RSA-PSS)', 'Proof that this officer approved this exact hash.'],
  ['AES-256-GCM', 'Encryption with authentication — tampered ciphertext fails to decrypt.'],
  ['Two-Man Rule', 'A document stays sealed until a second, senior officer grants access.'],
  ['Ledger block', 'One entry in the append-only custody chain.'],
  ['Genesis block', 'Block B0 — the anchor that starts the chain.'],
  ['Replay protection', 'A TOTP code cannot be used twice, even inside its time window.'],
  ['Vault', 'The encrypted local storage where document bytes live.'],
  ['Embedding', 'A numeric vector representing the meaning of a piece of text.'],
  ['RAG', 'Retrieval-Augmented Generation — look up relevant evidence, then answer from it.'],
  ['Leak tracker', 'The invisible zero-width stamp inside downloaded text documents.'],
];

const TROUBLE = [
  ['"Backend API unreachable" banner', 'The API on port 8000 is not running.', 'Run ./start.sh'],
  ['"Incorrect email or password"', 'Typo, or the demo password was changed.', 'backend/venv/bin/python backend/scripts/create_demo_accounts.py'],
  ['"This account requires an authenticator code."', 'MFA is on and the code field was left blank.', 'Get a code with backend/venv/bin/python backend/scripts/list_accounts.py'],
  ['"Invalid or already-used verification code."', 'The code expired (30 s) or was already spent.', 'Codes are single-use — take a fresh one.'],
  ['"Too many failed attempts"', '10 failures triggers a 5-minute lockout on IP + account.', 'Wait 5 minutes. It is stored in the database, so restarting does not help.'],
  ['Pages are empty with no error', 'The database has no seed data.', 'cd backend && venv/bin/python seed.py'],
  ['AI answers take 30-45 seconds', 'The NaraRouter free tier queues requests.', 'Expected. The deterministic fallback answers instantly.'],
  ['Badge says "Local synthesis"', 'No NARA_API_KEY in backend/.env.', 'Add the key and restart.'],
  ['uvicorn: command not found', 'The venv is missing or was moved.', 'cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt'],
];

function Row({ items }: { items: string[][] }) {
  return (
    <>
      {items.map(([k, v]) => (
        <div key={k} className="py-2.5 border-b border-slate-100 last:border-0">
          <p className="text-sm font-semibold text-slate-800">{k}</p>
          <p className="text-sm text-slate-500 mt-0.5 leading-relaxed">{v}</p>
        </div>
      ))}
    </>
  );
}

export const GuidePage = () => {
  const [section, setSection] = useState<Section>('start');
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800 flex items-center">
          <BookOpen className="w-6 h-6 mr-3 text-indigo-500" /> Guide
        </h2>
        <p className="text-slate-500">
          Everything about this system — what each screen does, what each control
          means, and how to sign in.{' '}
          {user ? (
            <>
              Signed in as{' '}
              <span className="font-medium text-slate-700">{user.email}</span>{' '}
              (<span className="font-medium text-slate-700">{user.role}</span>).
            </>
          ) : (
            <>
              You are not signed in — read as much as you like, then{' '}
              <Link to="/login" className="text-indigo-600 hover:underline">
                sign in
              </Link>{' '}
              to try it.
            </>
          )}
        </p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {SECTIONS.map(s => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            className={`flex items-center px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
              section === s.id
                ? 'bg-slate-900 text-white'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            <span className="w-4 h-4 mr-2 flex items-center justify-center">{s.icon}</span>
            {s.label}
          </button>
        ))}
      </div>

      {section === 'start' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-bold text-lg text-slate-800">What this actually is</h3>
            <p className="text-slate-600 mt-2 leading-relaxed">
              LEXSECURE is a secure document management system for investigative
              teams. Evidence — FIRs, forensic reports, witness statements,
              charge sheets — has to survive being emailed, printed and copied
              around. The problem is proving afterwards that the file you are
              looking at today is the file that was seized.
            </p>
            <div className="grid sm:grid-cols-3 gap-4 mt-5">
              {[
                ['Tamper detection', 'Every file is hashed, signed and encrypted on the way in, so you can prove the bytes were not altered.'],
                ['Access control', 'Each officer sees only the cases assigned to them. A junior officer cannot open a confidential informant statement.'],
                ['Chain of custody', 'Every event is appended to a hash-chained ledger, so you can prove the order and completeness of the record.'],
              ].map(([t, d]) => (
                <div key={t} className="bg-slate-50 rounded-lg p-4">
                  <p className="font-semibold text-sm text-slate-800 flex items-center">
                    <ShieldCheck className="w-4 h-4 mr-2 text-emerald-600" />{t}
                  </p>
                  <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{d}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-bold text-lg text-slate-800">Your first five minutes</h3>
            <ol className="mt-4 space-y-3">
              {[
                ['Open Cases and press Court Package (65B)', 'Generates the evidentiary manifest for CASE-2026-001 — every version, its SHA-256, its signatures and the ledger block that notarised it.'],
                ['Open the CFSL Forensic Report and press Verify Document Integrity', 'All three anchors must pass: the decrypted bytes, the RSA signature and the ledger block.'],
                ['Open Integrity Ledger', 'The chain starts at B0 GENESIS and every block links to the one before it.'],
                ['AI Search: "malware exhibit telegram wallet recovery"', 'Note the match scores and the AUTHORIZED badges on each result.'],
                ['AI Assistant: "What evidence was recovered from the forensic exhibits?"', 'The answer cites its sources inline. Expect 30–45 s on the free tier.'],
                ['Audit Trail → Export CSV', 'The confirmation line shows a SHA-256 attestation of the exact file you received.'],
              ].map(([t, d], i) => (
                <li key={t} className="flex gap-3">
                  <span className="w-6 h-6 rounded-full bg-slate-900 text-white text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</span>
                  <span>
                    <span className="text-sm font-semibold text-slate-800">{t}</span>
                    <span className="block text-sm text-slate-500 mt-0.5 leading-relaxed">{d}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-bold text-lg text-slate-800">Signing in</h3>
            <p className="text-slate-600 mt-2">
              Email, password, and — only for accounts with MFA switched on — the
              6-digit code from your authenticator app. The demo accounts below
              need no code at all.
            </p>
            <div className="mt-4 flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg p-4">
              <KeyRound className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-amber-800">
                <p className="font-semibold">No authenticator app?</p>
                <p className="mt-1">Get a live code in your terminal instead — it rotates every 30 seconds:</p>
                <code className="block mt-2 bg-white border border-amber-200 rounded px-3 py-2 text-xs font-mono">
                  backend/venv/bin/python backend/scripts/list_accounts.py
                </code>
              </div>
            </div>
          </div>
        </div>
      )}

      {section === 'accounts' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="p-4 border-b bg-slate-50 font-bold text-slate-800">
              Demo accounts — password only, no authenticator app
            </div>
            <div className="p-4 text-sm text-slate-600 border-b border-slate-100">
              Every one of these uses the password{' '}
              <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">Demo@LexSecure2026</code>{' '}
              and never expires. Leave the authenticator code blank.
            </div>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs border-b border-slate-200">
                  <th className="p-3 font-medium">Email</th>
                  <th className="p-3 font-medium">Role</th>
                  <th className="p-3 font-medium">Cases visible</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_ACCOUNTS.map(a => (
                  <tr key={a.email} className="border-b border-slate-100 last:border-0">
                    <td className="p-3 font-mono text-xs text-indigo-700">{a.email}</td>
                    <td className="p-3 text-slate-700">{a.role}</td>
                    <td className="p-3 text-slate-500">{a.sees}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="p-4 border-b bg-slate-50 font-bold text-slate-800">
              Seeded officer accounts — real authenticator required
            </div>
            <div className="p-4 text-sm text-slate-600 border-b border-slate-100">
              Password <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">LexSecure@2026</code>{' '}
              plus a 6-digit TOTP code.
            </div>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs border-b border-slate-200">
                  <th className="p-3 font-medium">Email</th>
                  <th className="p-3 font-medium">Role</th>
                </tr>
              </thead>
              <tbody>
                {SEEDED_ACCOUNTS.map(a => (
                  <tr key={a.email} className="border-b border-slate-100 last:border-0">
                    <td className="p-3 font-mono text-xs text-indigo-700">{a.email}</td>
                    <td className="p-3 text-slate-700">{a.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-bold text-lg text-slate-800">The clearest way to see the access control</h3>
            <p className="text-slate-600 mt-2 leading-relaxed">
              Sign in as <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">demo.investigator@lexsecure.local</code>{' '}
              and try to open CASE-2026-002. You get a red{' '}
              <strong>Access Restricted</strong> panel. Then sign in as{' '}
              <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-xs">demo.supervisor@lexsecure.local</code>{' '}
              and open the same case — it opens. That contrast is the whole point
              of the system.
            </p>
            <div className="mt-4 rounded-lg border border-slate-200 overflow-hidden">
              <img src="/docs/14-access-denied.png" alt="Access Restricted" className="w-full" />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-bold text-lg text-slate-800">Manage the accounts from the terminal</h3>
            <div className="mt-4 space-y-3 font-mono text-xs">
              {[
                ['backend/scripts/list_accounts.py', 'Every account, its role, its state, its case assignments and a live TOTP code.'],
                ['backend/scripts/create_demo_accounts.py', 'Recreate or reset the demo accounts, their passwords and their case assignments.'],
                ['backend/scripts/provision_mfa.py', 'Issue fresh TOTP secrets for the seeded officers and print a QR sheet.'],
              ].map(([c, d]) => (
                <div key={c} className="bg-slate-900 text-slate-200 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                    <span>{c}</span>
                  </div>
                  <p className="text-slate-400 mt-1.5 font-sans">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {section === 'tour' && (
        <div className="space-y-6">
          <p className="text-slate-600">
            Twelve screens, each with a live capture of this build. Click any name
            to jump straight to it.
          </p>
          {TOUR.map(t => (
            <div key={t.name} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <p className="font-bold text-slate-800">{t.name}</p>
                  <p className="text-sm text-slate-500 mt-0.5 leading-relaxed">{t.what}</p>
                </div>
                <Link
                  to={t.route}
                  className="ml-4 flex-shrink-0 flex items-center px-3 py-2 bg-slate-900 text-white text-xs rounded-lg hover:bg-slate-800"
                >
                  Open <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Link>
              </div>
              <img src={`/docs/${t.img}`} alt={t.name} className="w-full border-t border-slate-100" />
            </div>
          ))}
        </div>
      )}

      {section === 'controls' && (
        <div className="space-y-6">
          {CONTROLS.map(g => (
            <div key={g.group} className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-bold text-lg text-slate-800 mb-2">{g.group}</h3>
              <Row items={g.items} />
            </div>
          ))}
        </div>
      )}

      {section === 'glossary' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="font-bold text-lg text-slate-800 mb-2">Terms explained</h3>
          <Row items={GLOSSARY} />
        </div>
      )}

      {section === 'trouble' && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="p-4 border-b bg-slate-50 font-bold text-slate-800">Common problems</div>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-500 text-xs border-b border-slate-200">
                <th className="p-3 font-medium w-1/3">Symptom</th>
                <th className="p-3 font-medium w-1/3">Cause</th>
                <th className="p-3 font-medium">Fix</th>
              </tr>
            </thead>
            <tbody>
              {TROUBLE.map(([s, c, f]) => (
                <tr key={s} className="border-b border-slate-100 last:border-0 align-top">
                  <td className="p-3 text-slate-800 font-medium">{s}</td>
                  <td className="p-3 text-slate-500">{c}</td>
                  <td className="p-3 text-indigo-700 font-mono text-xs">{f}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-slate-900 text-slate-300 rounded-xl p-6">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-cyan-400 flex-shrink-0" />
          <p className="font-semibold text-white">Full documentation in the repository</p>
        </div>
        <p className="text-sm mt-2 leading-relaxed">
          This guide is the quick reference. The repository carries the complete
          set: a step-by-step getting-started guide, a screen-by-screen tour, the
          UI reference, the architecture guide and the API reference.
        </p>
        <div className="flex flex-wrap gap-3 mt-4">
          {[
            ['docs/GETTING_STARTED.md', 'Getting Started'],
            ['docs/APP_TOUR.md', 'App Tour'],
            ['docs/UI_REFERENCE.md', 'UI Reference'],
            ['docs/ARCHITECTURE.md', 'Architecture'],
            ['docs/API.md', 'API Reference'],
          ].map(([f, label]) => (
            <span key={f} className="flex items-center bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs">
              <Download className="w-3.5 h-3.5 mr-2 text-cyan-400" />{label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
