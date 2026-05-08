'use client';

import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  clickable?: boolean;
  onClick?: () => void;
}

export function Card({ children, className = '', clickable = false, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        bg-white dark:bg-gray-900 rounded-lg shadow-md
        border border-gray-200 dark:border-gray-800
        ${clickable ? 'cursor-pointer hover:shadow-lg transition-shadow' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  );
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  children: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) {
  const baseStyles =
    'font-medium rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700',
    secondary:
      'bg-gray-200 text-gray-900 hover:bg-gray-300 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700',
    danger: 'bg-red-600 text-white hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-700',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</label>
      )}
      <input
        className={`
          px-3 py-2 border border-gray-300 dark:border-gray-600
          rounded-lg bg-white dark:bg-gray-800
          text-gray-900 dark:text-white
          placeholder-gray-500 dark:placeholder-gray-400
          focus:outline-none focus:ring-2 focus:ring-blue-500
          ${error ? 'border-red-500' : ''}
          ${className}
        `}
        {...props}
      />
      {error && <span className="text-sm text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}

interface AlertProps {
  variant?: 'info' | 'success' | 'warning' | 'error';
  children: ReactNode;
  className?: string;
}

export function Alert({ variant = 'info', children, className = '' }: AlertProps) {
  const variants = {
    info: 'bg-blue-50 text-blue-800 border border-blue-200 dark:bg-blue-900 dark:text-blue-100 dark:border-blue-700',
    success:
      'bg-green-50 text-green-800 border border-green-200 dark:bg-green-900 dark:text-green-100 dark:border-green-700',
    warning:
      'bg-yellow-50 text-yellow-800 border border-yellow-200 dark:bg-yellow-900 dark:text-yellow-100 dark:border-yellow-700',
    error:
      'bg-red-50 text-red-800 border border-red-200 dark:bg-red-900 dark:text-red-100 dark:border-red-700',
  };

  return (
    <div className={`rounded-lg p-4 ${variants[variant]} ${className}`}>{children}</div>
  );
}

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingSpinner({ size = 'md' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
  };

  return (
    <div className="flex items-center justify-center">
      <div
        className={`${sizeClasses[size]} border-4 border-gray-200 dark:border-gray-700 border-t-blue-600 dark:border-t-blue-500 rounded-full animate-spin`}
      />
    </div>
  );
}
