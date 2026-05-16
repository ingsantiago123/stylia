"use client";

import { useState } from "react";
import { createProfile, processDocument, StyleProfileCreate } from "@/lib/api";
import { UploadStep } from "./steps/UploadStep";
import { ProfileGalleryStep } from "./steps/ProfileGalleryStep";
import { QuickAdjustmentsStep } from "./steps/QuickAdjustmentsStep";

type WizardStep = "upload" | "profile" | "adjustments";

interface WizardState {
  step: WizardStep;
  docId: string | null;
  filename: string;
  selectedPreset: string | null;
  adjustments: Partial<StyleProfileCreate>;
}

const STEPS: { id: WizardStep; label: string; index: number }[] = [
  { id: "upload", label: "Documento", index: 0 },
  { id: "profile", label: "Perfil", index: 1 },
  { id: "adjustments", label: "Ajustes", index: 2 },
];

interface DocumentWizardProps {
  onProcessStarted: () => void;
  onReset?: () => void;
}

function StepIndicator({ current }: { current: WizardStep }) {
  const currentIndex = STEPS.find((s) => s.id === current)?.index ?? 0;
  return (
    <nav aria-label="Pasos del proceso" className="flex items-center justify-center gap-0 mb-10">
      {STEPS.map((step, i) => {
        const done = i < currentIndex;
        const active = step.id === current;
        return (
          <div key={step.id} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                aria-current={active ? "step" : undefined}
                className={[
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300",
                  done
                    ? "bg-krypton text-carbon"
                    : active
                    ? "bg-krypton/20 border-2 border-krypton text-krypton"
                    : "bg-surface-elevated border border-border text-plomo",
                ].join(" ")}
              >
                {done ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={[
                  "mt-1.5 text-[10px] font-medium whitespace-nowrap",
                  active ? "text-krypton" : done ? "text-bruma" : "text-plomo",
                ].join(" ")}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={[
                  "h-px w-12 mx-2 mb-5 transition-colors duration-300",
                  done ? "bg-krypton/50" : "bg-border",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}

export function DocumentWizard({ onProcessStarted, onReset }: DocumentWizardProps) {
  const [state, setState] = useState<WizardState>({
    step: "upload",
    docId: null,
    filename: "",
    selectedPreset: null,
    adjustments: {},
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const goTo = (step: WizardStep) => setState((s) => ({ ...s, step }));

  const handleUploaded = (docId: string, filename: string) => {
    setState((s) => ({ ...s, docId, filename, step: "profile" }));
  };

  const handleSelectPreset = (key: string) => {
    setState((s) => ({ ...s, selectedPreset: key }));
  };

  const handleConfirm = async () => {
    if (!state.docId || !state.selectedPreset) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createProfile(state.docId, {
        preset_name: state.selectedPreset,
        ...state.adjustments,
      });
      await processDocument(state.docId);
      onProcessStarted();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Error al iniciar la corrección.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="glass-card rounded-2xl p-8 animate-fade-in-up">
      <StepIndicator current={state.step} />

      <div className="min-h-[420px] flex flex-col">
        {state.step === "upload" && (
          <UploadStep onUploaded={handleUploaded} />
        )}

        {state.step === "profile" && (
          <ProfileGalleryStep
            filename={state.filename}
            selectedKey={state.selectedPreset}
            onSelect={handleSelectPreset}
            onNext={() => goTo("adjustments")}
            onBack={() => goTo("upload")}
          />
        )}

        {state.step === "adjustments" && (
          <QuickAdjustmentsStep
            presetKey={state.selectedPreset!}
            adjustments={state.adjustments}
            onChange={(adj) => setState((s) => ({ ...s, adjustments: adj }))}
            onConfirm={handleConfirm}
            onBack={() => goTo("profile")}
            loading={submitting}
          />
        )}
      </div>

      {submitError && (
        <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400 flex items-center gap-2">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {submitError}
        </div>
      )}

      {onReset && state.step !== "upload" && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => {
              setState({ step: "upload", docId: null, filename: "", selectedPreset: null, adjustments: {} });
              onReset();
            }}
            className="text-xs text-plomo hover:text-bruma transition-colors"
          >
            Cancelar y volver al inicio
          </button>
        </div>
      )}
    </div>
  );
}
