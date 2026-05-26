'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Card, Input, Alert, LoadingSpinner } from '@/components/ui';
import { apiClient } from '@/lib/api-client';
import { storage } from '@/lib/storage';
import { ImmichSettings } from '@/types/api';

export default function Settings() {
  const router = useRouter();
  const [settings, setSettings] = useState<ImmichSettings>({
    immichUrl: '',
    apiKey: '',
  });
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    async function loadSettings() {
      try {
        const loaded = await apiClient.getSettings();
        setSettings(loaded);
      } catch {
        // Settings might not exist yet
      }
    }
    loadSettings();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setSettings(prev => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleTest = async () => {
    if (!settings.immichUrl || !settings.apiKey) {
      setError('Please fill in all fields');
      return;
    }

    setTesting(true);
    setError(null);

    try {
      await apiClient.testImmichConnection(settings.immichUrl, settings.apiKey);
      setSuccess('✓ Connection successful! Settings are valid.');
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection failed';
      setError(`Connection test failed: ${message}`);
      setSuccess(null);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!settings.immichUrl || !settings.apiKey) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.updateSettings(settings);
      storage.setSettingsConfigured(true);
      setSuccess('✓ Settings saved successfully!');

      setTimeout(() => {
        router.push('/games');
      }, 1500);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save settings';
      setError(`Error: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white dark:from-gray-900 dark:to-black py-12">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Immich Connection Settings
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Configure your Immich instance to start playing games with your photos.
          </p>
        </div>

        <Card className="p-8">
          <div className="space-y-6">
            <div>
              <Input
                label="Immich URL"
                name="immichUrl"
                placeholder="https://immich.example.com"
                value={settings.immichUrl}
                onChange={handleChange}
                disabled={loading || testing}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                The URL where your Immich instance is hosted
              </p>
            </div>

            <div>
              <Input
                label="API Key"
                name="apiKey"
                type="password"
                placeholder="Your Immich API key"
                value={settings.apiKey}
                onChange={handleChange}
                disabled={loading || testing}
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                Get this from your Immich account settings → Account → API Keys
              </p>
            </div>

            {error && <Alert variant="error">{error}</Alert>}
            {success && <Alert variant="success">{success}</Alert>}

            <div className="flex gap-4">
              <Button
                onClick={handleTest}
                variant="secondary"
                disabled={loading || testing || !settings.immichUrl || !settings.apiKey}
              >
                {testing ? <LoadingSpinner size="sm" /> : 'Test Connection'}
              </Button>
              <Button
                onClick={handleSave}
                disabled={loading || testing || !settings.immichUrl || !settings.apiKey}
              >
                {loading ? <LoadingSpinner size="sm" /> : 'Save Settings'}
              </Button>
            </div>
          </div>
        </Card>

        <div className="mt-8 p-6 bg-blue-50 dark:bg-blue-900 rounded-lg border border-blue-200 dark:border-blue-700">
          <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">
            📚 How to get your API Key
          </h3>
          <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
            <li>Log in to your Immich instance</li>
            <li>Go to Account Settings (usually in the top right)</li>
            <li>Select "API Keys" or "Developers"</li>
            <li>Click "Create API Key"</li>
            <li>Copy and paste it here</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
