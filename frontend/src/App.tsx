import { useEffect, useState } from "react";
import { tenantService } from "./services/tenantService";
import type { Tenant } from "./types/tenant";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Button } from "./components/ui/button";

function App() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTenants();
  }, []);

  async function loadTenants() {
    try {
      setLoading(true);
      setError(null);
      const data = await tenantService.list();
      setTenants(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tenants');
      console.error('Failed to load tenants:', err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
            TriFlow AI - Tenant Management
          </h1>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-50">
            Tenants
          </h2>
          <Button onClick={loadTenants}>Refresh</Button>
        </div>

        {loading && (
          <div className="text-center py-12">
            <p className="text-slate-600 dark:text-slate-400">Loading tenants...</p>
          </div>
        )}

        {error && (
          <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
            <CardHeader>
              <CardTitle className="text-red-700 dark:text-red-400">Error</CardTitle>
              <CardDescription className="text-red-600 dark:text-red-500">
                {error}
              </CardDescription>
            </CardHeader>
          </Card>
        )}

        {!loading && !error && tenants.length === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>No Tenants</CardTitle>
              <CardDescription>
                No tenants found. Create your first tenant to get started.
              </CardDescription>
            </CardHeader>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {tenants.map((tenant) => (
            <Card key={tenant.tenant_id}>
              <CardHeader>
                <CardTitle>{tenant.name}</CardTitle>
                <CardDescription>/{tenant.slug}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="text-sm">
                    <span className="text-slate-500 dark:text-slate-400">ID: </span>
                    <span className="font-mono text-xs">{tenant.tenant_id}</span>
                  </div>
                  <div className="text-sm">
                    <span className="text-slate-500 dark:text-slate-400">Created: </span>
                    <span>{new Date(tenant.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="text-sm">
                    <span className="text-slate-500 dark:text-slate-400">Updated: </span>
                    <span>{new Date(tenant.updated_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}

export default App;
