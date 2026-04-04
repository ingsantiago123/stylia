# Especificaciones de Imágenes — STYLIA Landing Page

Todas las imágenes deben crearse manualmente y colocarse en `public/images/placeholders/`.
Los archivos placeholder ya existen (en blanco); reemplázalos con las imágenes reales.

---

## 1. Hero Screenshot

| Campo | Valor |
|-------|-------|
| **Archivo** | `hero-screenshot.png` |
| **Medida** | 1440 × 810 px (ratio 16:9) |
| **Resolución** | 2x para retina (exportar 2880 × 1620 y comprimir) |
| **Formato** | PNG o WebP con fondo oscuro |
| **Descripción** | Captura de pantalla de la interfaz principal de STYLIA mostrando: un documento cargado en el dashboard, el pipeline visual con etapas coloreadas (preferiblemente en estado "correcting" para mostrar actividad), y la lista de correcciones con diffs word-level visibles. Debe reflejar el tema dark con acento krypton (#D4FF00). Incluir datos realistas, no lorem ipsum. |
| **Notas** | Agregar una sombra suave y bordes redondeados es opcional (ya los aplica el CSS). Si usas una captura real del frontend, asegúrate de que muestre un documento procesado con correcciones visibles. |

---

## 2. Avatares de Testimonios

Todos los avatares comparten estas especificaciones:

| Campo | Valor |
|-------|-------|
| **Medida** | 80 × 80 px (se muestra a 40×40, el doble para retina) |
| **Formato** | PNG con fondo transparente o JPG con fondo neutro |
| **Forma** | Cuadrado (el CSS aplica `rounded-full` para hacer círculo) |

### avatar-1.png
- **Persona**: Mujer, ~35-45 años, aspecto profesional editorial
- **Nombre asociado**: Ana Martínez, Editora de ficción
- **Estilo**: Foto profesional tipo headshot, fondo neutro

### avatar-2.png
- **Persona**: Hombre, ~30-40 años, aspecto creativo/digital
- **Nombre asociado**: Carlos Vega, Director de contenidos
- **Estilo**: Foto profesional casual, fondo neutro

### avatar-3.png
- **Persona**: Mujer, ~28-38 años, aspecto freelance/independiente
- **Nombre asociado**: Laura Domínguez, Correctora freelance
- **Estilo**: Foto natural/casual, fondo neutro

### avatar-4.png
- **Persona**: Hombre, ~50-60 años, aspecto académico
- **Nombre asociado**: Miguel Ángel Ruiz, Profesor universitario
- **Estilo**: Foto formal/académica, fondo neutro

### avatar-5.png
- **Persona**: Mujer, ~40-50 años, aspecto ejecutivo/editorial
- **Nombre asociado**: Patricia Sánchez, Responsable editorial
- **Estilo**: Foto corporativa, fondo neutro

### avatar-6.png
- **Persona**: Hombre, ~25-35 años, aspecto creativo/escritor
- **Nombre asociado**: Diego Herrera, Escritor y blogger
- **Estilo**: Foto casual/creativa, fondo neutro

---

## Notas generales

- **Fallback**: Si no se cargan las imágenes, el código muestra automáticamente las iniciales del nombre sobre un fondo oscuro (avatares) o un ícono placeholder (hero).
- **Compresión**: Optimizar todas las imágenes con herramientas como TinyPNG, Squoosh o similar. Objetivo: <100KB por avatar, <500KB para hero.
- **Alternativa avatares**: En lugar de fotos reales, se pueden usar avatares generados con herramientas como UI Faces, Generated Photos, o similares para uso libre de derechos.
- **Paleta de referencia**: Background #0A0A0B, Accent #D4FF00, Text #F5F5F7, Secondary #8E8E93.
