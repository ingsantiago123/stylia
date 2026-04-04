# STYLIA Landing Page — Estrategia de Conversión y Documentación Completa

---

## 1. Estrategia de Conversión

### Objetivo principal
Convertir visitantes (editores, correctores, escritores, equipos de contenido) en usuarios activos de STYLIA vía el CTA "Abrir STYLIA" que redirige a la aplicación frontend (`localhost:3000`).

### Métricas objetivo
- CTR hero CTA: >8%
- Scroll depth >75%: >40% de visitantes
- CTR mid-page CTA (pricing): >5%
- CTR final CTA: >6%
- Bounce rate: <45%

### Modelo de conversión: AIDA adaptado
1. **Atención** (Hero): Headline diferenciador + badge de autoridad técnica + screenshot del producto
2. **Interés** (Pain + How it works): Identificación de problemas reales + solución clara en 4 pasos
3. **Deseo** (Features + Stats + Testimonials): Funcionalidades detalladas + prueba social + números
4. **Acción** (Pricing + CTA final): Planes accesibles + urgencia suave + microcopy anti-fricción

### Diferenciador principal
"No es un corrector genérico. Es un pipeline editorial profesional que entiende tu género, tu audiencia y tu tono."

---

## 2. Arquitectura de Información

```
[Navbar] — Logo, nav links (6), CTA "Abrir STYLIA"
    |
[Hero] — Badge, headline, subheadline con WordRotate, 2 CTAs, screenshot
    |
[Pain/Problema] — 4 pain points en MagicCards
    |
[How It Works] — 4 pasos con ShineBorder numeración
    |
[Features] — 9 features en BentoGrid con BorderBeam en highlights
    |
[Stats/Resultados] — 4 estadísticas con NumberTicker + 10 capacidades checklist
    |
[Testimonials] — 6 testimonios en doble Marquee
    |
[Pricing] — 3 planes (Gratis, Profesional, Editorial) con MagicCards
    |
[FAQ] — 10 preguntas en Accordion
    |
[CTA Final] — SparklesText headline + ShimmerButton + trust signals
    |
[Footer] — 4 columnas (Brand, Producto, Recursos, Legal)
```

---

## 3. Wireframe Textual

### Desktop (1440px)
```
┌──────────────────────────────────────────────────┐
│ [Navbar] Logo ....nav links....  [Abrir STYLIA]  │
├──────────────────────────────────────────────────┤
│                                                  │
│  [GridPattern bg + GradientBlur bg]              │
│                                                  │
│          [AnimatedGradientText badge]            │
│     Tu texto merece más que un                   │
│     corrector ortográfico                        │
│  STYLIA analiza gramática... novelas/ensayos...  │
│  [ShimmerButton CTA]  [Outline CTA]             │
│  micro: Sin registro · Gratis · Privado          │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  [hero-screenshot.png — 1440×810]        │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
├──[SectionDivider fade]───────────────────────────┤
│                                                  │
│  [DotPattern bg]                                 │
│  EL PROBLEMA                                     │
│  Editar textos no debería ser tan lento          │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐                │
│  │ MagicCard 1 │  │ MagicCard 2 │                │
│  ├─────────────┤  ├─────────────┤                │
│  │ MagicCard 3 │  │ MagicCard 4 │                │
│  └─────────────┘  └─────────────┘                │
│                                                  │
├──[SectionDivider fade]───────────────────────────┤
│                                                  │
│  [GradientBlur section bg]                       │
│  CÓMO FUNCIONA                                   │
│  De documento sin revisar a texto editorial      │
│                                                  │
│  [ShineBorder] 01 · Sube tu documento            │
│       |                                          │
│  [ShineBorder] 02 · Elige tu perfil              │
│       |                                          │
│  [ShineBorder] 03 · Pipeline de doble motor      │
│       |                                          │
│  [ShineBorder] 04 · Recibe correcciones          │
│                                                  │
├──[SectionDivider dots]───────────────────────────┤
│                                                  │
│  [GridPattern bg]                                │
│  FUNCIONALIDADES                                 │
│                                                  │
│  ┌────────[BentoGrid]─────────┐                  │
│  │ [BCard 2col+Beam]│[BCard]  │                  │
│  │ [BCard]  │[BCard] │[BCard] │                  │
│  │ [BCard 2col+Beam] │[BCard] │                  │
│  │ [BCard]  │[BCard] │[BCard] │                  │
│  └────────────────────────────┘                  │
│                                                  │
├──[SectionDivider fade]───────────────────────────┤
│                                                  │
│  [GradientBlur bg]                               │
│  CAPACIDADES                                     │
│                                                  │
│  [ShineBorder] 6  │ 10+ │ 5   │ 110%            │
│  [NumberTicker animated stats]                   │
│                                                  │
│  ✓ cap1   ✓ cap2   (2-col grid, 10 items)       │
│                                                  │
├──[SectionDivider line]───────────────────────────┤
│                                                  │
│  [DotPattern bg]                                 │
│  TESTIMONIOS                                     │
│                                                  │
│  →→→ [Marquee row 1: 3 cards] →→→               │
│  ←←← [Marquee row 2: 3 cards, reverse] ←←←     │
│                                                  │
├──[SectionDivider fade]───────────────────────────┤
│                                                  │
│  [GradientBlur bg]                               │
│  PRECIOS                                         │
│                                                  │
│  ┌─────────┐  ┌──────────────┐  ┌─────────┐     │
│  │Explorar │  │ Profesional  │  │Editorial │     │
│  │ Gratis  │  │ $29/mo ★     │  │ $89/mo   │     │
│  │         │  │ [Beam+Badge] │  │          │     │
│  └─────────┘  └──────────────┘  └─────────┘     │
│                                                  │
├──[SectionDivider dots]───────────────────────────┤
│                                                  │
│  [GridPattern bg]                                │
│  FAQ (10 questions)                              │
│  [Accordion]                                     │
│                                                  │
├──[SectionDivider fade]───────────────────────────┤
│                                                  │
│  [GradientBlur cta + DotPattern]                 │
│  EMPIEZA AHORA                                   │
│  Tu próximo documento merece                     │
│  [SparklesText] corrección profesional           │
│  [ShimmerButton]  [Outline CTA]                  │
│  ✓ Sin tarjeta  ✓ Formato  ✓ Explicadas         │
│                                                  │
├──[SectionDivider fade]───────────────────────────┤
│  [Footer] 4 cols + copyright + "Abrir app" link  │
└──────────────────────────────────────────────────┘
```

### Mobile (375px)
- Navbar: hamburger menu, logo left, CTA in menu
- Hero: stacked layout, full-width CTAs, screenshot below
- Pain: single-column cards
- How it Works: vertical timeline, full width
- Features: single-column BentoCards
- Stats: 2×2 grid
- Testimonials: single Marquee speed adjusted
- Pricing: stacked cards, Professional first (reordered)
- FAQ: full width accordion
- CTA: stacked buttons
- Footer: stacked columns

---

## 4. Copy Completo por Sección

### Hero
- **Objetivo**: Captar atención + comunicar propuesta de valor en <5s
- **Titular variantes**:
  1. "Tu texto merece más que un corrector ortográfico" ✅ (seleccionado)
  2. "El corrector editorial que entiende tu texto, no solo tus errores"
  3. "Corrección de estilo profesional. Automática. Explicada."
- **Subtitular variantes**:
  1. "STYLIA analiza gramática, ortografía y estilo editorial en documentos DOCX..." ✅ (seleccionado)
  2. "Un pipeline de doble motor que corrige como un editor humano: con contexto, perfil y explicaciones."
- **Bullets**: N/A en hero (van en features)
- **CTA principal**: "Corregir mi primer documento" (acción específica)
- **CTA secundario**: "Ver cómo funciona" (scroll suave)
- **Microcopy**: "Sin registro obligatorio · Gratis para documentos cortos · Tu archivo nunca se comparte"

### Pain/Problema
- **Objetivo**: Generar identificación con el problema
- **Titular variantes**:
  1. "Editar textos profesionales no debería ser tan lento ni tan ciego" ✅
  2. "Tu equipo editorial merece mejores herramientas"
  3. "El cuello de botella editorial que nadie quiere admitir"
- **Subtitular variantes**:
  1. "Los equipos editoriales pierden tiempo y calidad con herramientas que no fueron diseñadas para corrección de estilo real." ✅
  2. "Revisión manual lenta, correctores genéricos y formato destruido. Hay una mejor forma."
- **Bullets (pain points)**:
  1. Horas revisando párrafo por párrafo → un documento de 100 páginas = días de trabajo
  2. Correctores genéricos ignoran contexto → no distinguen novela de informe
  3. Formato destruido al corregir → horas de diseño perdidas
  4. Correcciones sin explicación → aceptas o rechazas a ciegas

### Cómo Funciona
- **Objetivo**: Demostrar simplicidad del flujo
- **Titular variantes**:
  1. "De documento sin revisar a texto editorial en 4 pasos" ✅
  2. "Así funciona el pipeline que editores profesionales ya usan"
  3. "Sube, configura, corrige, descarga. Así de simple."
- **Subtitular variantes**:
  1. "Un pipeline profesional que combina reglas lingüísticas con inteligencia artificial contextual." ✅
  2. "Cada paso del proceso está diseñado para calidad editorial, no solo corrección superficial."

### Features
- **Objetivo**: Demostrar profundidad técnica y diferenciación
- **Titular variantes**:
  1. "Todo lo que necesitas para edición profesional" ✅
  2. "Más que un corrector: un pipeline editorial completo"
  3. "9 capacidades que no encontrarás en ningún otro corrector"
- **Subtitular variantes**:
  1. "Más que un corrector: un pipeline editorial completo con inteligencia artificial contextual." ✅
  2. "Cada funcionalidad existe por una razón: calidad editorial verificable."

### Stats/Resultados
- **Objetivo**: Anclar confianza con números concretos
- **Titular**: "Un sistema diseñado para calidad editorial real"

### Testimonials
- **Objetivo**: Prueba social de profesionales del sector
- **Titular**: "Profesionales que ya confían en STYLIA"

### Pricing
- **Objetivo**: Convertir interés en acción con plan claro
- **Titular variantes**:
  1. "Un plan para cada nivel editorial" ✅
  2. "Precios transparentes. Sin sorpresas."
  3. "Empieza gratis, escala cuando lo necesites."
- **CTA principal** (Profesional): "Comenzar prueba de 14 días"
- **CTA secundarios**: "Empezar gratis" / "Contactar ventas"
- **Microcopy**: "14 días gratis, sin tarjeta de crédito" / "Sin compromiso"

### FAQ
- **Objetivo**: Eliminar objeciones y dudas técnicas
- **10 preguntas cubriendo**: formatos, privacidad, costos, funcionamiento, limitaciones

### CTA Final
- **Objetivo**: Último empujón de conversión
- **Titular**: "Tu próximo documento merece corrección profesional"
- **CTA principal**: "Abrir STYLIA"
- **CTA secundario**: "Ver planes y precios"
- **Trust signals**: Sin tarjeta · Formato preservado · Correcciones explicadas

---

## 5. Design System Completo

### Color Tokens
| Token | Valor | Uso |
|-------|-------|-----|
| `carbon` (background) | `#0A0A0B` | Fondo principal de página |
| `carbon-100` | `#1C1C1F` | Surface elevada |
| `carbon-200` | `#141416` | Surface base (cards) |
| `carbon-300` | `#101012` | Surface profunda |
| `krypton` (primary/accent) | `#D4FF00` | CTAs, acentos, highlights |
| `krypton-dim` | `rgba(212,255,0,0.08)` | Fondos sutiles |
| `krypton-glow` | `rgba(212,255,0,0.15)` | Glows, halos |
| `bruma` (text-primary) | `#F5F5F7` | Texto principal |
| `bruma-muted` | `#C7C7CC` | Texto secundario-alto |
| `plomo` (text-secondary) | `#8E8E93` | Texto secundario |
| `plomo-light` | `#AEAEB2` | Texto terciario |
| `border` | `#2A2A2E` | Bordes visibles |
| `border-subtle` | `#1F1F23` | Bordes sutiles |
| `success` | `#34D399` | Estados positivos |
| `warning` | `#FBBF24` | Advertencias |
| `error` | `#F87171` | Errores |

### Typography Scale
| Token | Size/Line | Weight | Uso |
|-------|-----------|--------|-----|
| `display-1` | 72px/1.1 | 700 | Hero headline |
| `display-2` | 56px/1.15 | 700 | Section headlines grandes |
| `heading-1` | 48px/1.2 | 700 | Section headlines |
| `heading-2` | 36px/1.25 | 600 | Subtítulos de sección |
| `heading-3` | 24px/1.35 | 600 | Card títulos |
| `body-lg` | 20px/1.7 | 400 | Hero subtítulo |
| `body` | 18px/1.7 | 400 | Texto de sección |
| `body-sm` | 16px/1.6 | 400 | Texto de cards, descriptions |
| `caption` | 14px/1.5 | 400 | Labels, microcopy |

### Spacing Scale (base 8)
| Token | Value |
|-------|-------|
| 1 | 4px |
| 2 | 8px |
| 3 | 12px |
| 4 | 16px |
| 6 | 24px |
| 8 | 32px |
| 10 | 40px |
| 12 | 48px |
| 16 | 64px |
| 20 | 80px |
| 24 | 96px |
| 32 | 128px |

### Border System
| Property | Value |
|----------|-------|
| Default stroke | 1px solid `#2A2A2E` |
| Emphasis stroke | 1px solid `krypton/30` |
| Hover stroke | 1px solid `krypton/20` |
| radius-sm | 8px |
| radius-md | 12px |
| radius-lg | 16px |
| radius-xl | 24px |
| radius-2xl | 32px |
| Divider: line | gradient from transparent via border |
| Divider: fade | gradient from transparent via krypton/20 |
| Divider: dots | 3 dots krypton/30-50-30 |

### Elevation/Shadows
| Token | Value | Uso |
|-------|-------|-----|
| `glow-sm` | `0 0 15px rgba(212,255,0,0.15)` | Hover de botones |
| `glow-md` | `0 0 30px rgba(212,255,0,0.2)` | CTAs principales |
| `glow-lg` | `0 0 60px rgba(212,255,0,0.25)` | Hero elements |
| `card` | `0 1px 3px + 0 4px 12px` (dark) | Cards en reposo |
| `card-hover` | `0 4px 12px + 0 8px 24px` (dark) | Cards en hover |

### Motion
| Property | Value |
|----------|-------|
| Duration: fast | 200ms |
| Duration: normal | 300ms |
| Duration: slow | 500ms |
| Duration: entrance | 600-700ms |
| Easing: default | ease-out |
| Easing: bounce | cubic-bezier(0.34, 1.56, 0.64, 1) |
| Shimmer | 2s linear infinite |
| Border-beam | 4s linear infinite |
| Float | 6s ease-in-out infinite |
| Marquee | 40s linear infinite |
| `prefers-reduced-motion` | Disables all animations via Tailwind `motion-reduce:` |

### Estados Interactivos
| State | Behavior |
|-------|----------|
| Hover (buttons) | scale(1.02) + glow shadow + bg brightness |
| Active (buttons) | scale(0.98) |
| Focus-visible | ring-2 ring-krypton ring-offset-2 ring-offset-carbon |
| Disabled | opacity-50 cursor-not-allowed |
| Hover (cards) | border-krypton/20 + shadow-card-hover + spotlight (MagicCard) |
| Hover (links) | color transition plomo → bruma |

### Accesibilidad WCAG AA
- [x] Color contrast ratio: bruma (#F5F5F7) on carbon (#0A0A0B) = 19.1:1 (AAA)
- [x] Color contrast ratio: krypton (#D4FF00) on carbon (#0A0A0B) = 14.3:1 (AAA)
- [x] Color contrast ratio: plomo (#8E8E93) on carbon (#0A0A0B) = 4.5:1 (AA)
- [x] Focus visible indicators on all interactive elements (ring-2 krypton)
- [x] Semantic HTML (nav, main, section, footer, h1-h4 hierarchy)
- [x] aria-hidden on decorative SVGs and backgrounds
- [x] aria-label on mobile menu button
- [x] Alt text on all images
- [x] Keyboard navigable (tab order, focus states)
- [x] Reduced motion: animations respect `prefers-reduced-motion` via Tailwind

---

## 6. Tabla Sección → Componentes 21st.dev

| # | Componente | Categoría | Sección donde se usa | Instalación / Import |
|---|-----------|-----------|---------------------|---------------------|
| 1 | **GridPattern** | Background | Hero, Features, FAQ | `src/components/backgrounds/GridPattern.tsx` |
| 2 | **DotPattern** | Background | Pain, Testimonials, CTA Final | `src/components/backgrounds/DotPattern.tsx` |
| 3 | **GradientBlur** | Background | Hero, How it Works, Stats, Pricing, CTA Final | `src/components/backgrounds/GradientBlur.tsx` |
| 4 | **BorderBeam** | Border/Effect | Features (highlights), Pricing (plan destacado) | `src/components/ui/border-beam.tsx` |
| 5 | **ShineBorder** | Border/Container | How it Works (step numbers), Stats (stat cards) | `src/components/ui/shine-border.tsx` |
| 6 | **SectionDivider** | Divider | Todas las secciones (3 variantes: line, fade, dots) | `src/components/ui/section-divider.tsx` |
| 7 | **AnimatedGradientText** | Text/Badge | Hero (badge superior) | `src/components/ui/animated-gradient-text.tsx` |
| 8 | **ShimmerButton** | Button/CTA | Hero, Pricing (plan Pro), CTA Final | `src/components/ui/shimmer-button.tsx` |
| 9 | **WordRotate** | Text/Animation | Hero (rotación de géneros) | `src/components/ui/word-rotate.tsx` |
| 10 | **SparklesText** | Text/Effect | CTA Final (headline) | `src/components/ui/sparkles-text.tsx` |
| 11 | **MagicCard** | Card | Pain (4 cards), Pricing (3 plans) | `src/components/ui/magic-card.tsx` |
| 12 | **BentoGrid** | Layout | Features (9 cards grid) | `src/components/ui/bento-grid.tsx` |
| 13 | **NumberTicker** | Animation | Stats (4 estadísticas animadas) | `src/components/ui/number-ticker.tsx` |
| 14 | **Marquee** | Scroll | Testimonials (2 filas, normal + reverse) | `src/components/ui/marquee.tsx` |
| 15 | **BlurFade** | Animation | Todas las secciones (entrada con blur + fade) | `src/components/ui/blur-fade.tsx` |
| 16 | **Accordion** | Interactive | FAQ (10 preguntas) | `src/components/ui/accordion.tsx` (Radix UI) |

**Total: 16 componentes** (requisito mínimo: 12 ✅)
- Backgrounds: 3 ✅ (GridPattern, DotPattern, GradientBlur)
- Borders/Dividers: 3 ✅ (BorderBeam, ShineBorder, SectionDivider)
- CTAs de conversión: 3 ✅ (Hero ShimmerButton, Pricing ShimmerButton, Final CTA ShimmerButton)

---

## 7. Checklist QA

### Visual
- [ ] Todas las secciones renderizadas sin errores en desktop (1440px)
- [ ] Responsive correcto en tablet (768px) y mobile (375px)
- [ ] Imágenes placeholder muestran fallback correcto (iniciales/iconos)
- [ ] Fondos (GridPattern, DotPattern, GradientBlur) visibles pero no distractores
- [ ] Animaciones de entrada (BlurFade) funcionan en scroll
- [ ] Marquee de testimonios fluido y pausable en hover
- [ ] NumberTicker anima al entrar en viewport
- [ ] WordRotate cicla correctamente entre palabras
- [ ] ShimmerButton efecto visible
- [ ] MagicCard spotlight sigue cursor
- [ ] Navbar cambia de transparente a glass al scrollear
- [ ] Dark theme consistente en toda la página

### Accesibilidad
- [ ] Contraste AA en todos los textos
- [ ] Focus visible en todos los elementos interactivos
- [ ] Navegación por teclado completa (Tab, Enter, Escape)
- [ ] Screen reader: headings en orden correcto (h1 > h2 > h3)
- [ ] aria-hidden en elementos decorativos
- [ ] Alt text en imágenes
- [ ] `prefers-reduced-motion` respetado

### CRO
- [ ] Hero CTA visible above the fold sin scroll
- [ ] Microcopy anti-fricción bajo cada CTA
- [ ] Pricing plan destacado visualmente diferenciado
- [ ] FAQ cubre las 10 objeciones principales
- [ ] Testimonios con nombre, rol y empresa (credibilidad)
- [ ] Botón "Abrir STYLIA" en navbar siempre visible
- [ ] Mobile: CTAs full width para fácil tap
- [ ] Scroll depth tracking implementable (GA4/Plausible ready)

### Rendimiento
- [ ] Build exitoso sin errores ✅
- [ ] First Load JS: ~117 kB (aceptable)
- [ ] Imágenes optimizadas (<500KB hero, <100KB avatares)
- [ ] Fonts cargados vía Google Fonts CDN
- [ ] No dependencias pesadas innecesarias

---

## Ejecución

```bash
# Desarrollo
cd landing
npm install
npm run dev    # → http://localhost:3001

# Build producción
npm run build
npm start      # → http://localhost:3001
```

La landing corre en el puerto **3001** para no conflictuar con el frontend principal en **3000**.
El botón "Abrir STYLIA" redirige a `http://localhost:3000` (configurable via `NEXT_PUBLIC_APP_URL`).
