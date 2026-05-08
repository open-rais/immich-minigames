import { useCallback, useState } from 'react';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

interface UseApiOptions {
  onError?: (error: Error) => void;
  onSuccess?: () => void;
}

/**
 * Custom hook for API calls with loading and error states
 */
export function useApi<T>(options: UseApiOptions = {}) {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (fn: () => Promise<T>) => {
      setState({ data: null, loading: true, error: null });
      try {
        const result = await fn();
        setState({ data: result, loading: false, error: null });
        options.onSuccess?.();
        return result;
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error));
        setState({ data: null, loading: false, error: err });
        options.onError?.(err);
        throw err;
      }
    },
    [options]
  );

  return { ...state, execute };
}
