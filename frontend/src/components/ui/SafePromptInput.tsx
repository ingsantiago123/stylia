"use client";

import { useState, useCallback } from "react";

const MAX_CHARS = 250;
const BLOCKED_KEYWORDS = ["system", "ignore", "instructions", "prompt", "jailbreak", "override", "disregard", "forget"];

interface ValidationResult {
  ok: boolean;
  error: string | null;
}

function validatePrompt(text: string): ValidationResult {
  if (text.length > MAX_CHARS) {
    return { ok: false, error: `Máximo ${MAX_CHARS} caracteres permitidos.` };
  }
  const lower = text.toLowerCase();
  const hit = BLOCKED_KEYWORDS.find((kw) => lower.includes(kw));
  if (hit) {
    return {
      ok: false,
      error: `El texto contiene palabras no permitidas ("${hit}"…). Por favor reformula la regla.`,
    };
  }
  return { ok: true, error: null };
}

interface SafePromptInputProps {
  value: string;
  onChange: (val: string, isValid: boolean) => void;
  placeholder?: string;
  label?: string;
  hint?: string;
  disabled?: boolean;
}

export function SafePromptInput({
  value,
  onChange,
  placeholder = "Ej: Usar siempre la forma 'usted' en los diálogos formales.",
  label = "Regla editorial adicional",
  hint = "Escribe en lenguaje natural. Max. 250 caracteres.",
  disabled = false,
}: SafePromptInputProps) {
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const validate = useCallback((text: string) => {
    const result = validatePrompt(text);
    setError(result.error);
    return result.ok;
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const isValid = validate(val);
    onChange(val, isValid);
  };

  const hasError = touched && !!error;
  const charsLeft = MAX_CHARS - value.length;
  const isNearLimit = charsLeft <= 30;

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-xs font-semibold text-bruma uppercase tracking-wider">
          {label}
        </label>
      )}
      <div className="relative">
        <textarea
          value={value}
          onChange={handleChange}
          onBlur={() => { setTouched(true); validate(value); }}
          disabled={disabled}
          rows={3}
          placeholder={placeholder}
          aria-invalid={hasError}
          aria-describedby={hasError ? "safe-prompt-error" : "safe-prompt-hint"}
          className={[
            "w-full resize-none rounded-xl bg-surface border px-4 py-3 text-sm text-bruma placeholder:text-plomo-dark",
            "focus:outline-none focus:ring-2 transition-all duration-150",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            hasError
              ? "border-red-500/60 focus:ring-red-500/30 focus:border-red-500"
              : "border-border focus:ring-krypton/30 focus:border-krypton/60",
          ].join(" ")}
        />
        <div
          className={[
            "absolute bottom-2.5 right-3 text-[11px] font-mono tabular-nums transition-colors",
            isNearLimit ? (charsLeft < 0 ? "text-red-400" : "text-amber-400") : "text-plomo-dark",
          ].join(" ")}
        >
          {charsLeft}
        </div>
      </div>

      {hasError ? (
        <p id="safe-prompt-error" role="alert" className="text-xs text-red-400 flex items-start gap-1.5">
          <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </p>
      ) : (
        <p id="safe-prompt-hint" className="text-[11px] text-plomo-dark">
          {hint}
        </p>
      )}
    </div>
  );
}
