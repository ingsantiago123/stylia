"use client";

import { useState } from "react";
import { StyleProfileCreate } from "@/lib/api";

interface Question {
  id: string;
  text: string;
  options: { label: string; value: string; emoji: string; hint: string }[];
  mapTo: (value: string) => Partial<StyleProfileCreate>;
}

const QUESTIONS: Question[] = [
  {
    id: "audience",
    text: "¿A quién va dirigido tu texto?",
    options: [
      { label: "Niños y jóvenes", value: "young", emoji: "🧒", hint: "Hasta 17 años" },
      { label: "Adulto general", value: "general", emoji: "🧑", hint: "Lector no especializado" },
      { label: "Profesionales", value: "professional", emoji: "💼", hint: "Expertos en la materia" },
      { label: "Académico / Científico", value: "academic", emoji: "🎓", hint: "Publicación académica" },
    ],
    mapTo: (v) => ({
      audience_expertise: v === "young" ? "bajo" : v === "general" ? "medio" : v === "professional" ? "alto" : "experto",
      audience_type: v === "young" ? "adolescentes" : v === "general" ? "adultos_general" : v === "professional" ? "profesionales" : "especialistas",
    }),
  },
  {
    id: "tone",
    text: "¿Qué tono buscas para el texto?",
    options: [
      { label: "Cercano y cálido", value: "informal", emoji: "😊", hint: "Conversacional, próximo" },
      { label: "Equilibrado", value: "neutro", emoji: "📖", hint: "Ni muy formal ni coloquial" },
      { label: "Formal y claro", value: "formal_claro", emoji: "🤝", hint: "Serio pero accesible" },
      { label: "Técnico y preciso", value: "formal_tecnico", emoji: "📐", hint: "Para especialistas" },
    ],
    mapTo: (v) => ({ register: v }),
  },
  {
    id: "intervention",
    text: "¿Cuánto puede cambiar la IA tu texto?",
    options: [
      { label: "Lo mínimo posible", value: "minima", emoji: "🤫", hint: "Solo errores muy claros" },
      { label: "Solo lo necesario", value: "sutil", emoji: "✏️", hint: "Mejoras discretas" },
      { label: "Lo que mejore la lectura", value: "moderada", emoji: "🔧", hint: "Equilibrio corrección/estilo" },
      { label: "Todo lo que pueda mejorar", value: "agresiva", emoji: "⚡", hint: "Máximo impacto" },
    ],
    mapTo: (v) => ({ intervention_level: v }),
  },
  {
    id: "voice",
    text: "¿Es importante que se note que lo escribiste tú?",
    options: [
      { label: "Sí, es fundamental", value: "yes", emoji: "🎨", hint: "Proteger mi voz y estilo" },
      { label: "Me da igual", value: "no", emoji: "🔄", hint: "Priorizar claridad" },
    ],
    mapTo: (v) => ({ preserve_author_voice: v === "yes" }),
  },
];

interface AIAssistantChatProps {
  onProfileReady: (profile: Partial<StyleProfileCreate>) => void;
}

export function AIAssistantChat({ onProfileReady }: AIAssistantChatProps) {
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [accumulated, setAccumulated] = useState<Partial<StyleProfileCreate>>({});
  const [done, setDone] = useState(false);

  const question = QUESTIONS[currentQ];
  const progress = Math.round((currentQ / QUESTIONS.length) * 100);

  const handleAnswer = (value: string) => {
    const mapped = question.mapTo(value);
    const nextAccumulated = { ...accumulated, ...mapped };
    setAnswers((a) => ({ ...a, [question.id]: value }));
    setAccumulated(nextAccumulated);

    if (currentQ < QUESTIONS.length - 1) {
      setCurrentQ((q) => q + 1);
    } else {
      setDone(true);
      onProfileReady(nextAccumulated);
    }
  };

  const goBack = () => {
    if (currentQ > 0) setCurrentQ((q) => q - 1);
  };

  const restart = () => {
    setCurrentQ(0);
    setAnswers({});
    setAccumulated({});
    setDone(false);
  };

  if (done) {
    return (
      <div className="flex flex-col items-center text-center py-8 space-y-4 animate-scale-in">
        <div className="w-16 h-16 rounded-full bg-krypton/15 border border-krypton/30 flex items-center justify-center">
          <svg className="w-8 h-8 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <h3 className="text-heading-3 text-bruma mb-2">¡Perfil generado!</h3>
          <p className="text-sm text-plomo">
            Hemos configurado la IA a partir de tus respuestas.
            Puedes revisar y ajustar cada parámetro en el panel de abajo.
          </p>
        </div>
        <button
          type="button"
          onClick={restart}
          className="text-xs text-plomo hover:text-krypton transition-colors"
        >
          Volver a responder
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-plomo">
          <span>Pregunta {currentQ + 1} de {QUESTIONS.length}</span>
          <span>{progress}%</span>
        </div>
        <div className="h-1 bg-surface-elevated rounded-full overflow-hidden">
          <div
            className="h-full bg-krypton rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Chat bubble */}
      <div className="flex items-start gap-3 animate-fade-in-up" key={question.id}>
        <div className="w-8 h-8 rounded-full bg-krypton/15 border border-krypton/30 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-bold text-krypton">S</span>
        </div>
        <div className="flex-1 bg-surface-elevated border border-border rounded-2xl rounded-tl-sm px-4 py-3">
          <p className="text-sm text-bruma">{question.text}</p>
        </div>
      </div>

      {/* Options */}
      <div className="grid grid-cols-2 gap-2">
        {question.options.map((opt) => {
          const selected = answers[question.id] === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleAnswer(opt.value)}
              className={[
                "text-left p-4 rounded-xl border transition-all duration-150 space-y-1 group",
                selected
                  ? "border-krypton bg-krypton/10 shadow-glow-sm"
                  : "border-border bg-surface hover:border-krypton/40 hover:bg-krypton/5",
              ].join(" ")}
            >
              <div className="text-xl">{opt.emoji}</div>
              <div className="text-sm font-medium text-bruma">{opt.label}</div>
              <div className="text-[11px] text-plomo">{opt.hint}</div>
            </button>
          );
        })}
      </div>

      {/* Back */}
      {currentQ > 0 && (
        <div className="text-center">
          <button
            type="button"
            onClick={goBack}
            className="text-xs text-plomo hover:text-bruma transition-colors"
          >
            ← Cambiar respuesta anterior
          </button>
        </div>
      )}
    </div>
  );
}
