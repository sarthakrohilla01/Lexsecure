import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export const NotFoundPage = () => (
  <div className="max-w-md mx-auto bg-white p-10 rounded-xl border border-slate-200 text-center mt-10">
    <ShieldAlert className="w-12 h-12 text-slate-300 mx-auto mb-4" />
    <h2 className="font-bold text-xl text-slate-800">Page not found</h2>
    <p className="text-sm text-slate-500 mt-2">The requested section does not exist or you lack clearance to view it.</p>
    <Link to="/dashboard" className="inline-block mt-5 px-5 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">
      Return to Dashboard
    </Link>
  </div>
);
