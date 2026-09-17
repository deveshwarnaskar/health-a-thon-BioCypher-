import React from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  emptyMessage?: string;
  caption?: string;
  ariaLabel?: string;
}

export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  isLoading = false,
  emptyMessage = "No records found.",
  caption,
  ariaLabel,
}: TableProps<T>): React.ReactElement {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
      <table
        className="min-w-full divide-y divide-gray-200 text-left text-sm"
        aria-label={ariaLabel}
        aria-busy={isLoading}
      >
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-gray-50 text-xs font-semibold text-gray-700 uppercase tracking-wider">
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col" className={`px-6 py-3 ${col.className || ""}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, idx) => (
              <tr key={`skeleton-${idx}`} className="animate-pulse">
                {columns.map((col) => (
                  <td key={col.key} className="px-6 py-4 whitespace-nowrap">
                    <div className="h-4 bg-gray-200 rounded w-3/4" />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-6 py-10 text-center text-sm text-gray-500"
              >
                <div className="flex flex-col items-center justify-center space-y-2">
                  <svg
                    className="h-8 w-8 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                    />
                  </svg>
                  <p>{emptyMessage}</p>
                </div>
              </td>
            </tr>
          ) : (
            data.map((item, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50 transition-colors">
                {columns.map((col) => (
                  <td key={col.key} className={`px-6 py-4 whitespace-nowrap ${col.className || ""}`}>
                    {col.render ? col.render(item) : (item[col.key] as React.ReactNode)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
