"use client";

import { useEffect, useState } from "react";
import {
  DocumentStructure,
  DocumentStructureGroup,
  DocumentStructureSection,
  fetchDocumentStructure,
} from "@/lib/api";

interface Props {
  docId: string;
}

export function StructuralTree({ docId }: Props) {
  const [structure, setStructure] = useState<DocumentStructure | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDocumentStructure(docId)
      .then((s) => {
        if (!cancelled) setStructure(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Error desconocido");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  if (loading) {
    return (
      <div className="glass-card rounded-xl p-6 text-center text-plomo text-sm">
        Cargando estructura del documento…
      </div>
    );
  }
  if (error) {
    return (
      <div className="glass-card rounded-xl p-6 text-center text-red-400 text-sm">
        Error al cargar estructura: {error}
      </div>
    );
  }
  if (!structure) {
    return null;
  }

  const hasContent =
    structure.sections.length > 0 || structure.orphan_groups.length > 0;
  if (!hasContent) {
    return (
      <div className="glass-card rounded-xl p-6 text-center text-plomo text-sm">
        Aún no se detectó estructura para este documento.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Totales */}
      <div className="glass-card rounded-xl p-4 flex items-center gap-6">
        <Stat label="Secciones" value={structure.totals.sections} />
        <Stat label="Listas" value={structure.totals.lists} />
        <Stat label="Tablas" value={structure.totals.tables} />
      </div>

      {/* Árbol */}
      <div className="glass-card rounded-xl p-4">
        <h3 className="text-sm font-semibold text-bruma mb-3">
          Árbol estructural
        </h3>
        <div className="font-mono text-xs leading-6 text-bruma/85 whitespace-pre-wrap">
          <div>Documento</div>
          {structure.sections.map((s, i) => (
            <SectionNode
              key={s.id}
              section={s}
              isLast={i === structure.sections.length - 1 && structure.orphan_groups.length === 0}
            />
          ))}
          {structure.orphan_groups.length > 0 && (
            <div className="mt-2">
              <div className="text-plomo">└─ Grupos sin sección detectada</div>
              <div className="ml-5">
                {structure.orphan_groups.map((g) => (
                  <GroupNode key={g.id} group={g} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-krypton">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-plomo">{label}</div>
    </div>
  );
}

function SectionNode({
  section,
  isLast,
}: {
  section: DocumentStructureSection;
  isLast: boolean;
}) {
  const branch = isLast ? "└─" : "├─";
  return (
    <div>
      <div className="text-bruma">
        {branch} <span className="text-purple-400 font-semibold">§{section.section_index + 1}</span>{" "}
        {section.section_title || "(sin título)"}
      </div>
      {section.groups.length > 0 && (
        <div className="ml-5">
          {section.groups.map((g) => (
            <GroupNode key={g.id} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}

function GroupNode({ group }: { group: DocumentStructureGroup }) {
  const icon = group.group_type === "list" ? "≡" : "▦";
  const statusColor: Record<string, string> = {
    pending: "text-plomo",
    in_progress: "text-yellow-400",
    completed: "text-emerald-400",
    partial_failure: "text-orange-400",
  };
  return (
    <div className="flex items-center gap-2">
      <span className="text-bruma/70">├─ {icon}</span>
      <span className="text-bruma">{group.label}</span>
      <span className="text-[10px] text-plomo">
        ({group.blocks_count} bloques · {group.patches_count} patches)
      </span>
      <span className={`text-[10px] ${statusColor[group.correction_status] || "text-plomo"}`}>
        [{group.correction_status}]
      </span>
    </div>
  );
}
