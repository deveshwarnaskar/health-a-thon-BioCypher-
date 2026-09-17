import React, { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

export const AdminLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navigation = [
    {
      name: "Dashboard",
      href: "/",
      icon: (
        <svg className="h-5 w-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      ),
    },
    {
      name: "Facilities",
      href: "/facilities",
      icon: (
        <svg className="h-5 w-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      ),
    },
    {
      name: "Care Team",
      href: "/care-team",
      icon: (
        <svg className="h-5 w-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
    {
      name: "Patient Directory",
      href: "/patients",
      icon: (
        <svg className="h-5 w-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ),
    },
    {
      name: "Identity Mappings",
      href: "/identity-mappings",
      icon: (
        <svg className="h-5 w-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
      ),
    },
    {
      name: "Audit Trail",
      href: "/audit",
      icon: (
        <svg className="h-5 w-5 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Skip to Content Link for Keyboard Accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-indigo-600 focus:text-white focus:rounded-md shadow-lg"
      >
        Skip to main content
      </a>

      {/* Top Header */}
      <header className="bg-white border-b border-gray-200 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 mr-2"
                aria-label="Open main menu"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <Link to="/" className="flex items-center space-x-3">
                <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg">
                  T
                </div>
                <div>
                  <span className="text-lg font-bold text-gray-900 tracking-tight">Thali</span>
                  <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    Admin Console
                  </span>
                </div>
              </Link>
            </div>

            {/* Tenant and Operator Badge */}
            <div className="flex items-center space-x-4">
              <div className="hidden sm:flex flex-col items-end">
                <div className="text-xs text-gray-500">Authenticated Tenant</div>
                <div
                  title={user?.tenant_id}
                  className="text-xs font-mono font-medium text-gray-900 max-w-[140px] truncate bg-gray-50 px-2 py-0.5 rounded border border-gray-200"
                >
                  {user?.tenant_id}
                </div>
              </div>

              <div className="h-6 w-px bg-gray-200 hidden sm:block" />

              <div className="flex items-center space-x-3">
                <div className="hidden lg:block text-right">
                  <div className="text-xs font-medium text-gray-900">Operator: {user?.actor_id.slice(0, 8)}...</div>
                  <div className="text-[10px] text-green-600 font-semibold uppercase tracking-wider">Role: admin</div>
                </div>
                <button
                  onClick={logout}
                  className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 shadow-sm"
                  aria-label="Log out of admin console"
                >
                  <svg className="h-4 w-4 mr-1.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  Log out
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex gap-6">
        {/* Desktop Sidebar */}
        <aside aria-label="Sidebar Navigation" className="hidden md:block w-64 flex-shrink-0">
          <nav className="space-y-1 sticky top-6 bg-white p-3 rounded-lg border border-gray-200 shadow-sm">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                end={item.href === "/"}
                className={({ isActive }) =>
                  `flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive
                      ? "bg-indigo-50 text-indigo-700 font-semibold"
                      : "text-gray-700 hover:bg-gray-50 hover:text-gray-900"
                  }`
                }
              >
                {item.icon}
                {item.name}
              </NavLink>
            ))}

            <div className="pt-4 mt-4 border-t border-gray-200">
              <div className="px-3 py-2 rounded bg-amber-50 border border-amber-200 text-amber-900 text-xs">
                <span className="font-semibold block mb-0.5">Operational Boundary</span>
                Administrative controls only. Non-clinical. Zero clinical observations or AI diagnostic data.
              </div>
            </div>
          </nav>
        </aside>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-40 flex">
            <div
              className="fixed inset-0 bg-gray-600 bg-opacity-75"
              onClick={() => setMobileMenuOpen(false)}
              aria-hidden="true"
            />
            <div className="relative flex-1 flex flex-col max-w-xs w-full bg-white pt-5 pb-4">
              <div className="px-4 flex items-center justify-between">
                <span className="font-bold text-gray-900">Admin Menu</span>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1 rounded-md text-gray-400 hover:text-gray-500"
                  aria-label="Close menu"
                >
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <nav className="mt-5 px-2 space-y-1">
                {navigation.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    end={item.href === "/"}
                    onClick={() => setMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center px-3 py-2 text-base font-medium rounded-md ${
                        isActive
                          ? "bg-indigo-50 text-indigo-700"
                          : "text-gray-700 hover:bg-gray-50"
                      }`
                    }
                  >
                    {item.icon}
                    {item.name}
                  </NavLink>
                ))}
              </nav>
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 focus:outline-none">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
