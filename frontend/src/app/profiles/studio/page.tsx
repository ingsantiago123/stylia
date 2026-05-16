"use client";

import { useState } from "react";
import Link from "next/link";
import { AIAssistantChat } from "@/components/profiles/AIAssistantChat";
import { SafePromptInput } from "@/components/ui/SafePromptInput";
import { HumanizedTooltip, METRIC_GLOSSARY } from "@/components/ui/HumanizedTooltip";
import { StyleProfileCreate } from "@/lib/api";

// Mapeo de valores técnicos a etiquetas amigables
const INTERVENTION_LABELS: Record<string, string> = {
  minima: "Mínima — solo errores obvios",
  sutil: "Sutil — mejoras discretas",
  moderada: "Moderada — equilibrio corrección/estilo",
  agresiva: "Agresiva — máximo impacto",
};

const REGISTER_LABELS: Record<string, string> = {
  informal: "Cercano y cálido",
  neutro: "Equilibrado",
  neutro_claro: "Equilibrado y claro",
  formal_claro: "Formal y accesible",
  formal_tecnico: "Técnico y preciso",
  persuasivo: "Persuasivo",
  informal_claro: "Informal claro",
};

const AUDIENCE_LABELS: Record<string, string> = {
  bajo: "Lector no especializado",
  medio: "Lector general",
  alto: "Profesional",
  experto: "Especialista / Académico",
};

function ProfileSummaryCard({ profile }: { profile: Partial<StyleProfileCreate> }) {
  if (!profile.intervention_level && !profile.register) return null;
  return (
    <div className="glass-card rounded-2xl p-5 space-y-4 animate-scale-in">
      <div className="flex items-center gap-2">
        <div className="w-1.5 h-5 bg-krypton rounded-full" />
        <h3 className="text-sm font-semibold text-bruma uppercase tracking-wider">Perfil generado</h3>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {profile.intervention_level && (
          <div className="space-y-0.5">
            <HumanizedTooltip config={METRIC_GLOSSARY.intervention_level}>
              <p className="text-[10px] text-plomo uppercase tracking-wider">Intervención</p>
            </HumanizedTooltip>
            <p className="text-sm text-bruma">{INTERVENTION_LABELS[profile.intervention_level] ?? profile.intervention_level}</p>
          </div>
        )}
        {profile.register && (
          <div className="space-y-0.5">
            <p className="text-[10px] text-plomo uppercase tracking-wider">Registro</p>
            <p className="text-sm text-bruma">{REGISTER_LABELS[profile.register] ?? profile.register}</p>
          </div>
        )}
        {profile.audience_expertise && (
          <div className="space-y-0.5">
            <p className="text-[10px] text-plomo uppercase tracking-wider">Audiencia</p>
            <p className="text-sm text-bruma">{AUDIENCE_LABELS[profile.audience_expertise] ?? profile.audience_expertise}</p>
          </div>
        )}
        {typeof profile.preserve_author_voice === "boolean" && (
          <div className="space-y-0.5">
            <HumanizedTooltip config={METRIC_GLOSSARY.preserve_author_voice}>
              <p className="text-[10px] text-plomo uppercase tracking-wider">Voz del autor</p>
            </HumanizedTooltip>
            <p className="text-sm text-bruma">{profile.preserve_author_voice ? "Protegida" : "Sin restricción"}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProfileStudioPage() {
  const [chatProfile, setChatProfile] = useState<Partial<StyleProfileCreate>>({});
  const [extraRule, setExtraRule] = useState("");
  const [extraRuleValid, setExtraRuleValid] = useState(true);
  const [phase, setPhase] = useState<"chat" | "refine">("chat");

  const handleChatDone = (profile: Partial<StyleProfileCreate>) => {
    setChatProfile(profile);
    setPhase("refine");
  };

  const canCopy = Object.keys(chatProfile).length > 0 && extraRuleValid;
  const jsonPreview = JSON.stringify(
    { ...chatProfile, ...(extraRule ? { extra_rule: extraRule } : {}) },
    null,
    2
  );

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-8 animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-plomo">
        <Link href="/" className="hover:text-bruma transition-colors">Inicio</Link>
        <span>/</span>
        <span className="text-bruma">Profile Studio</span>
      </div>

      {/* Hero */}
      <div>
        <h1 className="text-heading-2 text-bruma mb-2">Profile Studio</h1>
        <p className="text-sm text-plomo leading-relaxed">
          Responde unas preguntas sencillas y generaremos automáticamente el perfil editorial
          óptimo para tu texto. Luego puedes afinar cada parámetro antes de copiar la configuración.
        </p>
      </div>

      {/* Chat section */}
      <section className="glass-card rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-xl bg-krypton/15 border border-krypton/30 flex items-center justify-center">
            <svg className="w-4 h-4 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-bruma">Diagnóstico inteligente</h2>
            <p className="text-xs text-plomo">Stylia te hace 4 preguntas clave</p>
          </div>
          {phase === "refine" && (
            <button
              type="button"
              onClick={() => setPhase("chat")}
              className="ml-auto text-xs text-plomo hover:text-krypton transition-colors"
            >
              Repetir diagnóstico
            </button>
          )}
        </div>
        <AIAssistantChat onProfileReady={handleChatDone} />
      </section>

      {/* Profile summary */}
      {phase === "refine" && <ProfileSummaryCard profile={chatProfile} />}

      {/* Extra rule */}
      {phase === "refine" && (
        <section className="glass-card rounded-2xl p-6 space-y-4 animate-fade-in-up">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-5 bg-plomo rounded-full" />
            <h2 className="text-sm font-semibold text-bruma uppercase tracking-wider">Regla adicional (opcional)</h2>
          </div>
          <SafePromptInput
            value={extraRule}
            onChange={(val, isValid) => { setExtraRule(val); setExtraRuleValid(isValid); }}
            hint="Escribe en lenguaje natural. Ej: Nunca uses la palabra 'paradigma'."
          />
        </section>
      )}

      {/* JSON preview */}
      {phase === "refine" && (
        <section className="glass-card rounded-2xl p-6 space-y-4 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-5 bg-plomo/50 rounded-full" />
              <h2 className="text-sm font-semibold text-bruma uppercase tracking-wider">Vista técnica</h2>
            </div>
            {canCopy && (
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(jsonPreview)}
                className="text-xs text-plomo hover:text-krypton transition-colors flex items-center gap-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Copiar JSON
              </button>
            )}
          </div>
          <pre className="text-[11px] font-mono text-plomo bg-surface rounded-xl p-4 overflow-x-auto border border-border leading-relaxed">
            {jsonPreview}
          </pre>
          <p className="text-[11px] text-plomo-dark">
            Estos valores se envían al backend como cuerpo del POST{" "}
            <code className="text-krypton/80">/api/v1/documents/&#123;id&#125;/profile</code>.
          </p>
        </section>
      )}

      {/* CTA */}
      {phase === "refine" && (
        <div className="text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-krypton text-carbon text-sm font-semibold shadow-glow-sm hover:bg-krypton-400 transition-all"
          >
            Ir al Wizard con este perfil
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      )}
    </div>
  );
}
