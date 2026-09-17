import React, { useId } from "react";

export interface Option {
  value: string;
  label: string;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: Option[];
  error?: string;
  helperText?: string;
}

export const Select: React.FC<SelectProps> = ({
  label,
  options,
  error,
  helperText,
  id,
  className = "",
  ...props
}) => {
  const autoId = useId();
  const selectId = id || autoId;
  const errorId = `${selectId}-error`;
  const helperId = `${selectId}-helper`;

  return (
    <div className="w-full">
      <label htmlFor={selectId} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {props.required && <span className="text-red-500 ml-1" aria-hidden="true">*</span>}
      </label>
      <select
        id={selectId}
        aria-invalid={!!error}
        aria-describedby={error ? errorId : helperText ? helperId : undefined}
        className={`block w-full rounded-md border shadow-sm sm:text-sm px-3 py-2 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 ${
          error
            ? "border-red-300 text-red-900 focus:ring-red-500 focus:border-red-500 bg-red-50/20"
            : "border-gray-300 text-gray-900 bg-white"
        } ${className}`}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
      {!error && helperText && (
        <p id={helperId} className="mt-1 text-xs text-gray-500">
          {helperText}
        </p>
      )}
    </div>
  );
};
