"use client";

import { GridPattern } from "@/components/backgrounds/GridPattern";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { SectionDivider } from "@/components/ui/section-divider";
import { BlurFade } from "@/components/ui/blur-fade";

const faqs = [
  {
    question: "¿Qué formatos de archivo acepta STYLIA?",
    answer:
      "Actualmente STYLIA trabaja con archivos DOCX (Microsoft Word). Subes tu documento DOCX y recibes el archivo corregido en DOCX y PDF. El soporte para PDF nativos está planificado para futuras versiones.",
  },
  {
    question: "¿STYLIA modifica el formato original de mi documento?",
    answer:
      "No. STYLIA usa un enfoque DOCX-first: corrige directamente sobre el archivo original preservando tipografías, estilos, tablas, encabezados, pies de página y toda la maquetación. El texto cambia, el diseño permanece intacto.",
  },
  {
    question: "¿Cómo funciona el doble motor de corrección?",
    answer:
      "Cada párrafo pasa primero por LanguageTool, que aplica reglas gramaticales y ortográficas del español. Después, el texto post-LanguageTool se envía a GPT-4o-mini con contexto editorial (perfil, sección, párrafos anteriores) para correcciones de estilo, claridad y fluidez. Son dos capas complementarias.",
  },
  {
    question: "¿Qué son los perfiles editoriales?",
    answer:
      "Son configuraciones que indican a la IA cómo debe corregir tu texto. Incluyen género (novela, ensayo, artículo...), audiencia (adultos, jóvenes, especialistas), tono (formal, coloquial, neutro), nivel de intervención (conservador a agresivo) y términos protegidos que no deben modificarse. Hay 10 presets y puedes crear los tuyos propios.",
  },
  {
    question: "¿Mis documentos son privados?",
    answer:
      "STYLIA se ejecuta en tu propia infraestructura (Docker Compose). Tus archivos se almacenan en MinIO, un sistema S3-compatible que corre en tu servidor. No se envían a servicios de terceros excepto los párrafos individuales que se procesan vía OpenAI API para corrección de estilo. No se almacena el documento completo en ningún servicio externo.",
  },
  {
    question: "¿Qué son los quality gates?",
    answer:
      "Son 5 validaciones automáticas que se ejecutan después de cada corrección: texto no vacío, ratio de expansión (máximo 110%), ratio de reescritura, preservación de términos protegidos y legibilidad INFLESZ. Si un gate crítico falla, se preserva el texto original. Esto garantiza que la IA nunca destruya tu contenido.",
  },
  {
    question: "¿Cuánto cuesta en tokens de OpenAI?",
    answer:
      "STYLIA optimiza costos con un router inteligente que clasifica cada párrafo: SKIP (sin IA, costo cero), CHEAP (modelo ligero) o EDITORIAL (revisión profunda). Solo los párrafos que realmente necesitan corrección editorial consumen tokens. El sistema registra y muestra el costo exacto por documento.",
  },
  {
    question: "¿Puedo usar STYLIA sin conexión a OpenAI?",
    answer:
      "Sí, parcialmente. Sin API key de OpenAI, la corrección de LanguageTool (gramática y ortografía) sigue funcionando. Solo la corrección de estilo con IA se desactiva, usando un modo de simulación. En futuras versiones se soportarán modelos LLM locales.",
  },
  {
    question: "¿Qué tamaño de documento puedo procesar?",
    answer:
      "Por defecto: hasta 500 MB y 1000 páginas por documento. Estos límites son configurables en la configuración del sistema. El pipeline procesa página por página, así que documentos largos no saturan la memoria.",
  },
  {
    question: "¿STYLIA funciona con otros idiomas?",
    answer:
      "Actualmente está optimizado para español. LanguageTool y los perfiles editoriales están configurados para corrección en español. El soporte multiidioma es parte del roadmap futuro.",
  },
];

export function FAQ() {
  return (
    <section id="faq" className="relative section-padding overflow-hidden">
      <GridPattern strokeColor="rgba(212, 255, 0, 0.03)" cellSize={80} />
      <SectionDivider variant="dots" className="absolute top-0 left-0 right-0" />

      <div className="container-landing relative z-10">
        <BlurFade>
          <div className="text-center max-w-3xl mx-auto mb-16">
            <p className="text-caption text-krypton font-medium uppercase tracking-widest mb-4">
              Preguntas frecuentes
            </p>
            <h2 className="text-heading-1 text-bruma mb-6">
              Todo lo que necesitas saber
            </h2>
            <p className="text-body text-plomo-light">
              Las respuestas a las preguntas más comunes sobre STYLIA y su
              pipeline de corrección editorial.
            </p>
          </div>
        </BlurFade>

        <BlurFade delay={150}>
          <div className="max-w-3xl mx-auto">
            <Accordion type="single" collapsible className="w-full">
              {faqs.map((faq, i) => (
                <AccordionItem key={i} value={`faq-${i}`}>
                  <AccordionTrigger>{faq.question}</AccordionTrigger>
                  <AccordionContent>{faq.answer}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </BlurFade>
      </div>
    </section>
  );
}
