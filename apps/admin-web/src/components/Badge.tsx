import React from "react";

export interface BadgeProps {
  status: "active" | "inactive" | "pending" | "revoked" | "success" | "error";
  label?: string;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ status, label, className = "" }) => {
  const configs = {
    active: {
      bg: "bg-green-100 text-green-800 border-green-200",
      text: label || "Active",
      icon: (
        <svg className="h-3 w-3 mr-1 text-green-600" fill="currentColor" viewBox="0 0 8 8" aria-hidden="true">
          <circle cx="4" cy="4" r="3" />
        </svg>
      ),
    },
    success: {
      bg: "bg-green-100 text-green-800 border-green-200",
      text: label || "Success",
      icon: (
        <svg className="h-3 w-3 mr-1 text-green-600" fill="currentColor" viewBox="0 0 8 8" aria-hidden="true">
          <circle cx="4" cy="4" r="3" />
        </svg>
      ),
    },
    inactive: {
      bg: "bg-gray-100 text-gray-800 border-gray-200",
      text: label || "Inactive",
      icon: (
        <svg className="h-3 w-3 mr-1 text-gray-500" fill="currentColor" viewBox="0 0 8 8" aria-hidden="true">
          <circle cx="4" cy="4" r="3" stroke="currentColor" fill="none" />
        </svg>
      ),
    },
    pending: {
      bg: "bg-amber-100 text-amber-800 border-amber-200",
      text: label || "Pending",
      icon: (
        <svg className="h-3 w-3 mr-1 text-amber-600" fill="currentColor" viewBox="0 0 8 8" aria-hidden="true">
          <path d="M4 1v3h2" stroke="currentColor" strokeWidth="1.5" fill="none" />
        </svg>
      ),
    },
    revoked: {
      bg: "bg-red-100 text-red-800 border-red-200",
      text: label || "Revoked",
      icon: (
        <svg className="h-3 w-3 mr-1 text-red-600" fill="currentColor" viewBox="0 0 8 8" aria-hidden="true">
          <path d="M2 2l4 4m0-4L2 6" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      ),
    },
    error: {
      bg: "bg-red-100 text-red-800 border-red-200",
      text: label || "Error",
      icon: (
        <svg className="h-3 w-3 mr-1 text-red-600" fill="currentColor" viewBox="0 0 8 8" aria-hidden="true">
          <path d="M2 2l4 4m0-4L2 6" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      ),
    },
  }[status];

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${configs.bg} ${className}`}
    >
      {configs.icon}
      {configs.text}
    </span>
  );
};
