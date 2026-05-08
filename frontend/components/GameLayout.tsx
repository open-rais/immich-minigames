'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  showBackButton?: boolean;
}

export default function GameLayout({ children, title, showBackButton = true }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white dark:from-gray-900 dark:to-black">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {showBackButton && (
              <Link
                href="/games"
                className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
              >
                ← Back
              </Link>
            )}
            {title && (
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
            )}
          </div>
          <Link
            href="/settings"
            className="text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            Settings
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">{children}</main>
    </div>
  );
}
