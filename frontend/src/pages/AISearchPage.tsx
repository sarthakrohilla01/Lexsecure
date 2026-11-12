import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ShieldCheck, FileText, Loader2 } from 'lucide-react';
import { apiClient, errorDetail } from '../api/client';
import { AiModeBadge, AiModeNote } from '../components/AiModeBadge';

export const AISearchPage = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);
    setError('');
    try {
      const res = await apiClient.post('/ai/search', { query, limit: 10 });
      setResults(res.data);
    } catch (err: any) {
      setResults([]);
      setError(errorDetail(err, 'Semantic search failed.'));
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="text-center py-10 bg-gradient-to-b from-slate-800 to-slate-900 rounded-2xl shadow-xl text-white">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-900/50 mb-4 border border-cyan-500/30">
          <Search className="w-8 h-8 text-cyan-400" />
        </div>
        <h2 className="text-3xl font-bold mb-3">AI Semantic Investigator</h2>
        <div className="flex justify-center mb-3">
          <AiModeBadge />
        </div>
        <p className="text-slate-400 max-w-2xl mx-auto mb-8">
          Search across all authorized evidentiary records using dense vector embeddings.
          <span className="block mt-2 text-emerald-400 text-sm font-semibold flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 mr-1" /> Strict ABAC security filters applied before ranking.
          </span>
          <AiModeNote />
        </p>

        <form onSubmit={handleSearch} className="max-w-2xl mx-auto px-4 relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="E.g., Which documents mention ransomware lateral movement?"
            className="w-full pl-6 pr-16 py-4 rounded-full text-slate-800 focus:outline-none focus:ring-4 focus:ring-cyan-500/50 shadow-lg text-lg"
          />
          <button
            type="submit"
            disabled={isSearching}
            className="absolute right-6 top-1/2 -translate-y-1/2 p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full transition-colors"
          >
            {isSearching ? <Loader2 className="w-6 h-6 animate-spin" /> : <Search className="w-6 h-6" />}
          </button>
        </form>
      </div>

      {hasSearched && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-slate-700 mb-4 border-b pb-2">
            {error ? 'Search Failed' : `${results.length} Evidence Matches Found`}
          </h3>

          {error && (
            <div className="bg-red-50 p-4 rounded-xl text-center text-red-700 border border-red-200 text-sm">
              {error}
            </div>
          )}

          {results.length === 0 && !isSearching && !error && (
            <div className="bg-white p-8 rounded-xl text-center text-slate-500 border border-slate-200">
              No matching records found within your authorized security clearance.
            </div>
          )}

          {results.map((r: any, idx: number) => (
            <div key={idx} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <Link to={`/documents/${r.document_id}`} className="font-bold text-lg text-indigo-700 hover:underline flex items-center">
                    {r.document_title} <span className="ml-2 text-xs font-normal text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">v{r.version_number}</span>
                  </Link>
                  <p className="text-sm text-slate-500 mt-1">Case: {r.case_id} • {r.document_type}</p>
                </div>
                <div className="flex flex-col items-end">
                  <span className="text-xs font-bold px-2 py-1 bg-emerald-100 text-emerald-700 rounded mb-1 border border-emerald-200 flex items-center">
                    <ShieldCheck className="w-3 h-3 mr-1" /> {r.access_status}
                  </span>
                  <span className="text-xs font-mono text-indigo-500 bg-indigo-50 px-2 rounded">Match: {(r.score * 100).toFixed(1)}%</span>
                </div>
              </div>

              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100 text-slate-700 text-sm italic whitespace-pre-wrap break-words relative">
                <span className="absolute -left-2 -top-2 text-4xl text-slate-300 font-serif">"</span>
                {r.content}
                <span className="absolute -right-2 -bottom-4 text-4xl text-slate-300 font-serif">"</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
