"use client";

import { useState, useEffect } from "react";
import { PresetInfo, listPresets, createProfile, processDocument } from "@/lib/api";
import { ProfileEditor } from "@/components/ProfileEditor";

interface ProfileSelectorProps {
  docId: string;
  filename: string;
  onProcessStarted: () => void;
  onCancel: () => void;
}

const ICON_MAP: Record<string, JSX.Element> = {
  child: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 01-6.364 0M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
    </svg>
  ),
  "book-open": (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
    </svg>
  ),
  users: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  ),
  feather: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
    </svg>
  ),
  "pen-tool": (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
    </svg>
  ),
  brain: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
    </svg>
  ),
  lightbulb: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
    </svg>
  ),
  settings: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
  megaphone: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 01-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 018.835 2.535M10.34 6.66a23.847 23.847 0 008.835-2.535m0 0A23.74 23.74 0 0018.795 3m.38 1.125a23.91 23.91 0 011.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 001.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 010 3.46" />
    </svg>
  ),
  "file-text": (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  ),
};

const INTERVENTION_COLORS: Record<string, string> = {
  minima: "text-emerald-400",
  sutil: "text-blue-400",
  moderada: "text-amber-400",
  agresiva: "text-red-400",
};

const INTERVENTION_LABELS: Record<string, string> = {
  minima: "Minima",
  sutil: "Sutil",
  moderada: "Moderada",
  agresiva: "Agresiva",
};

export function ProfileSelector({ docId, filename, onProcessStarted, onCancel }: ProfileSelectorProps) {
  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPresets()
      .then(setPresets)
      .catch(() => setError("Error cargando perfiles"))
      .finally(() => setLoading(false));
  }, []);

  const handleProcess = async (profileData?: Record<string, unknown>) => {
    setProcessing(true);
    setError(null);
    try {
      if (selectedKey || profileData) {
        await createProfile(docId, { preset_name: selectedKey, ...(profileData || {}) });
      }
      await processDocument(docId);
      onProcessStarted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar");
      setProcessing(false);
    }
  };

  const handleProcessGeneric = async () => {
    setProcessing(true);
    setError(null);
    try {
      await processDocument(docId);
      onProcessStarted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al procesar");
      setProcessing(false);
    }
  };

  if (showEditor) {
    return (
      <ProfileEditor
        presetKey={selectedKey}
        presets={presets}
        onSave={(data) => handleProcess(data)}
        onBack={() => setShowEditor(false)}
        processing={processing}
        error={error}
      />
    );
  }

  return (
    <div className="glass-card rounded-xl p-6 space-y-5 animate-scale-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-bruma">Perfil editorial</h3>
          <p className="text-sm text-plomo mt-1">
            Selecciona como quieres corregir <span className="text-krypton font-medium">{filename}</span>
          </p>
        </div>
        <button
          onClick={onCancel}
          className="text-plomo-dark hover:text-bruma transition-colors p-2 rounded-lg hover:bg-surface-hover"
          title="Cancelar"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Preset grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="bg-surface rounded-xl p-4 space-y-2">
              <div className="shimmer-bg w-8 h-8 rounded-lg" />
              <div className="shimmer-bg w-20 h-3 rounded" />
              <div className="shimmer-bg w-14 h-2 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {presets.map((preset, i) => {
            const isSelected = selectedKey === preset.key;
            return (
              <button
                key={preset.key}
                onClick={() => setSelectedKey(isSelected ? null : preset.key)}
                disabled={processing}
                className={`
                  relative text-left p-4 rounded-xl border transition-all duration-200 group animate-fade-in-up
                  ${isSelected
                    ? "border-krypton/40 bg-krypton/8 shadow-glow-sm"
                    : "border-border hover:border-border bg-surface hover:bg-surface-hover"
                  }
                  ${processing ? "opacity-50 cursor-wait" : "cursor-pointer"}
                `}
                style={{ animationDelay: `${i * 0.03}s` }}
              >
                <div className={`mb-2.5 ${isSelected ? "text-krypton" : "text-plomo group-hover:text-bruma"} transition-colors`}>
                  {ICON_MAP[preset.icon] || ICON_MAP["file-text"]}
                </div>

                <div className={`text-sm font-medium mb-0.5 ${isSelected ? "text-krypton" : "text-bruma"}`}>
                  {preset.name}
                </div>

                <div className={`text-[10px] font-medium ${INTERVENTION_COLORS[preset.intervention_level] || "text-plomo"}`}>
                  {INTERVENTION_LABELS[preset.intervention_level] || preset.intervention_level}
                </div>

                <div className="mt-1.5 text-[10px] text-plomo-dark line-clamp-2 leading-relaxed">
                  {preset.description}
                </div>

                {isSelected && (
                  <div className="absolute top-2.5 right-2.5">
                    <svg className="w-4 h-4 text-krypton" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={() => handleProcess()}
          disabled={!selectedKey || processing}
          className={`
            px-5 py-2 rounded-lg font-medium text-sm transition-all
            ${selectedKey && !processing
              ? "bg-krypton text-carbon hover:bg-krypton-200 shadow-glow-sm"
              : "bg-surface-elevated text-plomo-dark cursor-not-allowed"
            }
          `}
        >
          {processing ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Procesando...
            </span>
          ) : "Procesar con este perfil"}
        </button>

        <button
          onClick={() => setShowEditor(true)}
          disabled={processing}
          className="px-4 py-2 rounded-lg text-sm font-medium text-plomo hover:text-bruma border border-border hover:border-border hover:bg-surface-hover transition-all"
        >
          Personalizar
        </button>

        <button
          onClick={handleProcessGeneric}
          disabled={processing}
          className="px-4 py-2 rounded-lg text-sm text-plomo-dark hover:text-bruma transition-colors ml-auto"
        >
          Sin perfil
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/15 text-red-400 px-4 py-2.5 rounded-lg text-sm">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
