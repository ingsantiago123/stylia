"use client";

import { useEffect, useState } from "react";
import { listPresets, PresetInfo } from "@/lib/api";
import { RichProfileCard } from "@/components/wizard/RichProfileCard";

interface ProfileGalleryStepProps {
  selectedKey: string | null;
  onSelect: (key: string) => void;
  onNext: () => void;
  onBack: () => void;
  filename: string;
}

export function ProfileGalleryStep({
  selectedKey,
  onSelect,
  onNext,
  onBack,
  filename,
}: ProfileGalleryStepProps) {
  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPresets()
      .then(setPresets)
      .catch(() => setPresets([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-heading-3 text-bruma mb-2">¿Qué tipo de texto es?</h2>
        <p className="text-sm text-plomo">
          Selecciona el perfil que mejor describe{" "}
          <span className="text-bruma font-medium">{filename}</span>.
          Podrás ajustar los detalles en el siguiente paso.
        </p>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-border p-5 space-y-3">
              <div className="shimmer-bg h-4 w-3/4 rounded" />
              <div className="shimmer-bg h-3 w-full rounded" />
              <div className="shimmer-bg h-3 w-2/3 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 overflow-y-auto pb-2 flex-1">
          {presets.map((preset) => (
            <RichProfileCard
              key={preset.key}
              preset={preset}
              selected={selectedKey === preset.key}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between mt-6 pt-6 border-t border-border">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-plomo hover:text-bruma transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Volver
        </button>

        <div className="flex items-center gap-3">
          {selectedKey && (
            <span className="text-xs text-krypton animate-fade-in">
              ✓ Perfil seleccionado
            </span>
          )}
          <button
            type="button"
            onClick={onNext}
            disabled={!selectedKey}
            className={[
              "flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200",
              selectedKey
                ? "bg-krypton text-carbon hover:bg-krypton-400 shadow-glow-sm"
                : "bg-surface-elevated text-plomo cursor-not-allowed",
            ].join(" ")}
          >
            Ajustar detalles
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
