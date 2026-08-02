"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Settings, Save, Check, KeyRound } from "lucide-react";
import { fetchApi, getAuthCredential, setAuthCredential, clearAuthCredential } from "@/lib/api";

interface WorkspaceSettings {
  timezone: string;
  working_hours_start: string;
  working_hours_end: string;
  exclude_weekends: boolean;
  dev_mode: boolean;
  follow_up_delay_hours: number;
  max_follow_ups: number;
}

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [credentialInput, setCredentialInput] = useState("");
  const [hasStoredCredential, setHasStoredCredential] = useState(false);
  const [credentialSaved, setCredentialSaved] = useState(false);

  useEffect(() => {
    fetchApi("/campaigns/settings")
      .then((res) => setSettings(res.data))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load settings"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    // Reads localStorage, which only exists client-side - this can only run
    // as an effect, not during render (would mismatch SSR/hydration output).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHasStoredCredential(!!getAuthCredential());
  }, []);

  const handleSaveCredential = () => {
    if (!credentialInput.trim()) return;
    setAuthCredential(credentialInput.trim());
    setHasStoredCredential(true);
    setCredentialInput("");
    setCredentialSaved(true);
    setTimeout(() => setCredentialSaved(false), 2000);
  };

  const handleClearCredential = () => {
    clearAuthCredential();
    setHasStoredCredential(false);
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const res = await fetchApi("/campaigns/settings", {
        method: "PUT",
        body: JSON.stringify(settings),
      });
      setSettings(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Header showViewSwitcher={false} showAddProspect={false} />
      <div className="flex-1 overflow-y-auto p-6" style={{ background: "var(--apex-bg)" }}>
        <div className="flex items-center gap-2 mb-6">
          <Settings size={20} style={{ color: "var(--apex-accent)" }} />
          <h1 className="text-lg font-bold" style={{ color: "var(--apex-text)" }}>Workspace Settings</h1>
        </div>

        <div className="max-w-md rounded-xl p-5 flex flex-col gap-3 mb-6" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
          <div className="flex items-center gap-2">
            <KeyRound size={16} style={{ color: "var(--apex-accent)" }} />
            <h2 className="text-sm font-bold" style={{ color: "var(--apex-text)" }}>API Credential</h2>
          </div>
          <p className="text-xs" style={{ color: "var(--apex-text-dim)" }}>
            A signed JWT or provisioned API key, issued by an operator. Sent as an
            <code className="mx-1">Authorization: Bearer</code>
            header on every request - this is the only source of tenant identity, there is no tenant-ID header.
          </p>
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--apex-text-dim)" }}>
            Status:
            <span style={{ color: hasStoredCredential ? "var(--apex-success, #22c55e)" : "var(--apex-danger, #ef4444)" }}>
              {hasStoredCredential ? "Credential configured" : "No credential configured"}
            </span>
          </div>
          <input
            type="password"
            value={credentialInput}
            onChange={(e) => setCredentialInput(e.target.value)}
            placeholder="Paste JWT or API key"
            className="w-full text-sm px-3 py-2 rounded-lg"
            style={{ background: "var(--apex-bg)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
          />
          <div className="flex items-center gap-2">
            <button
              onClick={handleSaveCredential}
              disabled={!credentialInput.trim()}
              className="flex items-center justify-center gap-2 text-sm font-medium px-4 py-2 rounded-lg"
              style={{ background: "var(--apex-accent)", color: "white", opacity: credentialInput.trim() ? 1 : 0.6 }}
            >
              {credentialSaved ? <Check size={14} /> : <Save size={14} />}
              {credentialSaved ? "Saved" : "Save Credential"}
            </button>
            {hasStoredCredential && (
              <button
                onClick={handleClearCredential}
                className="text-sm font-medium px-4 py-2 rounded-lg"
                style={{ background: "var(--apex-bg)", border: "1px solid var(--apex-border)", color: "var(--apex-text-dim)" }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {loading && <p className="text-sm" style={{ color: "var(--apex-muted)" }}>Loading settings…</p>}
        {error && <p className="text-sm mb-4" style={{ color: "var(--apex-danger, #ef4444)" }}>{error}</p>}

        {settings && (
          <div className="max-w-md rounded-xl p-5 flex flex-col gap-4" style={{ background: "var(--apex-surface)", border: "1px solid var(--apex-border)" }}>
            <div>
              <label className="text-xs font-medium block mb-1" style={{ color: "var(--apex-text-dim)" }}>Timezone</label>
              <input
                type="text"
                value={settings.timezone}
                onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                className="w-full text-sm px-3 py-2 rounded-lg"
                style={{ background: "var(--apex-bg)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: "var(--apex-text-dim)" }}>Working Hours Start</label>
                <input
                  type="text"
                  value={settings.working_hours_start}
                  onChange={(e) => setSettings({ ...settings, working_hours_start: e.target.value })}
                  className="w-full text-sm px-3 py-2 rounded-lg"
                  style={{ background: "var(--apex-bg)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
                />
              </div>
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: "var(--apex-text-dim)" }}>Working Hours End</label>
                <input
                  type="text"
                  value={settings.working_hours_end}
                  onChange={(e) => setSettings({ ...settings, working_hours_end: e.target.value })}
                  className="w-full text-sm px-3 py-2 rounded-lg"
                  style={{ background: "var(--apex-bg)", border: "1px solid var(--apex-border)", color: "var(--apex-text)" }}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs" style={{ color: "var(--apex-text-dim)" }}>
              <input
                type="checkbox"
                checked={settings.exclude_weekends}
                onChange={(e) => setSettings({ ...settings, exclude_weekends: e.target.checked })}
              />
              Exclude weekends from outreach scheduling
            </label>

            <label className="flex items-center gap-2 text-xs" style={{ color: "var(--apex-text-dim)" }}>
              <input
                type="checkbox"
                checked={settings.dev_mode}
                onChange={(e) => setSettings({ ...settings, dev_mode: e.target.checked })}
              />
              Dev mode (bypass send failures, shorten delays)
            </label>

            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center justify-center gap-2 text-sm font-medium px-4 py-2 rounded-lg mt-2"
              style={{ background: "var(--apex-accent)", color: "white", opacity: saving ? 0.6 : 1 }}
            >
              {saved ? <Check size={14} /> : <Save size={14} />}
              {saved ? "Saved" : saving ? "Saving…" : "Save Settings"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
