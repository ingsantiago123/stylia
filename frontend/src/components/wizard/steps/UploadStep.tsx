"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument } from "@/lib/api";

interface UploadStepProps {
  onUploaded: (docId: string, filename: string) => void;
}

export function UploadStep({ onUploaded }: UploadStepProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const res = await uploadDocument(file);
      onUploaded(res.id, res.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al subir el archivo.");
    } finally {
      setUploading(false);
    }
  }, [onUploaded]);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "application/pdf": [".pdf"],
    },
    maxFiles: 1,
    maxSize: 500 * 1024 * 1024,
    disabled: uploading,
  });

  return (
    <div className="flex flex-col items-center text-center max-w-lg mx-auto">
      <h2 className="text-heading-3 text-bruma mb-2">Sube tu documento</h2>
      <p className="text-sm text-plomo mb-8">
        Acepta archivos <span className="text-bruma font-medium">.docx</span> y{" "}
        <span className="text-bruma font-medium">.pdf</span> (digital) de hasta 500 MB.
        El formato original se preservará intacto.
      </p>

      <div
        {...getRootProps()}
        className={[
          "relative w-full rounded-2xl border-2 border-dashed p-12 cursor-pointer transition-all duration-200 group",
          isDragReject
            ? "border-red-500/60 bg-red-500/5"
            : isDragActive
            ? "border-krypton bg-krypton/5 shadow-glow-sm"
            : uploading
            ? "border-krypton/40 bg-krypton/5 cursor-not-allowed"
            : "border-border hover:border-krypton/50 hover:bg-krypton/5",
        ].join(" ")}
      >
        <input {...getInputProps()} aria-label="Seleccionar archivo DOCX o PDF" />

        {/* Icon */}
        <div className={[
          "mx-auto mb-5 w-16 h-16 rounded-2xl flex items-center justify-center transition-colors",
          isDragActive ? "bg-krypton/20" : "bg-surface-elevated group-hover:bg-krypton/10",
        ].join(" ")}>
          {uploading ? (
            <svg className="w-8 h-8 text-krypton animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : isDragActive ? (
            <svg className="w-8 h-8 text-krypton" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
          ) : (
            <svg className="w-8 h-8 text-plomo group-hover:text-krypton transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          )}
        </div>

        {/* Text */}
        <div className="space-y-1">
          {uploading ? (
            <p className="text-sm font-medium text-krypton">Subiendo documento…</p>
          ) : isDragReject ? (
            <p className="text-sm font-medium text-red-400">Solo se aceptan archivos .docx o .pdf (digital)</p>
          ) : isDragActive ? (
            <p className="text-sm font-medium text-krypton">Suelta aquí para subir</p>
          ) : (
            <>
              <p className="text-sm font-medium text-bruma">
                Arrastra tu <span className="text-krypton">.docx</span> o <span className="text-krypton">.pdf</span> aquí
              </p>
              <p className="text-xs text-plomo">
                o{" "}
                <span className="text-krypton underline underline-offset-2 decoration-dotted">
                  haz clic para explorar
                </span>
              </p>
            </>
          )}
        </div>

        {/* Drag active glow ring */}
        {isDragActive && (
          <div className="absolute inset-0 rounded-2xl ring-2 ring-krypton/30 pointer-events-none" />
        )}
      </div>

      {error && (
        <div className="mt-4 w-full rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400 flex items-center gap-2">
          <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}

      <p className="mt-6 text-[11px] text-plomo-dark">
        Tu archivo se almacena de forma privada y se elimina al finalizar la corrección.
      </p>
    </div>
  );
}
