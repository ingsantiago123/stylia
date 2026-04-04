"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument } from "@/lib/api";

interface Props {
  onSuccess: () => void;
  onUploaded?: (docId: string, filename: string) => void;
}

export function DocumentUploader({ onSuccess, onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      if (!file.name.toLowerCase().endsWith(".docx")) {
        setError("Solo se aceptan archivos .docx en el MVP");
        return;
      }

      setUploading(true);
      setError(null);
      setMessage(null);

      try {
        const result = await uploadDocument(file);
        setMessage(`${result.filename} — ${result.message}`);
        if (onUploaded) {
          onUploaded(result.id, result.filename);
        } else {
          onSuccess();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error al subir");
      } finally {
        setUploading(false);
      }
    },
    [onSuccess, onUploaded]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`
          relative glass-card rounded-xl px-8 py-12 text-center cursor-pointer
          transition-all duration-300 group overflow-hidden
          ${isDragActive
            ? "border-krypton/40 glow-krypton-sm"
            : "hover:border-krypton/20"
          }
          ${uploading ? "opacity-60 cursor-wait" : ""}
        `}
      >
        <input {...getInputProps()} />

        {/* Animated background on drag */}
        {isDragActive && (
          <div className="absolute inset-0 bg-gradient-to-br from-krypton/5 via-transparent to-krypton/5 animate-fade-in" />
        )}

        <div className="relative space-y-4">
          <div className={`
            mx-auto w-14 h-14 rounded-2xl flex items-center justify-center transition-all duration-300
            ${isDragActive ? "bg-krypton/15 scale-110" : "bg-surface-hover group-hover:bg-surface-elevated"}
          `}>
            {uploading ? (
              <svg className="animate-spin h-6 w-6 text-krypton" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className={`w-6 h-6 transition-all duration-300 ${isDragActive ? "text-krypton -translate-y-1" : "text-plomo group-hover:text-bruma"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
            )}
          </div>

          {uploading ? (
            <div>
              <p className="text-bruma font-medium">Subiendo documento...</p>
              <p className="text-plomo text-sm mt-1">Esto puede tardar unos segundos</p>
            </div>
          ) : isDragActive ? (
            <div>
              <p className="text-krypton font-semibold text-lg">Suelta aqui</p>
              <p className="text-krypton/50 text-sm mt-1">Se procesara automaticamente</p>
            </div>
          ) : (
            <div>
              <p className="text-bruma font-medium">
                Arrastra un archivo <span className="text-gradient-krypton font-semibold">.docx</span>
              </p>
              <p className="text-plomo text-sm mt-1">
                o haz clic para seleccionar &middot; Max. 500 MB
              </p>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 glass-card rounded-lg border-red-500/20 text-red-400 px-4 py-2.5 text-sm">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}
      {message && (
        <div className="flex items-center gap-2 glass-card rounded-lg border-krypton/20 text-krypton px-4 py-2.5 text-sm">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          {message}
        </div>
      )}
    </div>
  );
}
