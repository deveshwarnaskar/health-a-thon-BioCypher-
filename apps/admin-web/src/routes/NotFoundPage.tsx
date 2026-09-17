import React from "react";
import { Link } from "react-router-dom";

export const NotFoundPage: React.FC = () => (
  <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
    <div className="rounded-full bg-gray-100 p-3 mb-4 text-gray-400">
      <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </div>
    <h1 className="text-xl font-bold text-gray-900 mb-1">Page Not Found</h1>
    <p className="text-sm text-gray-500 mb-6">
      The requested administrative control-plane route does not exist.
    </p>
    <Link
      to="/"
      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
    >
      Return to Dashboard
    </Link>
  </div>
);
