# 🔑 Configuración de OpenAI API

## 📋 Pasos para conectar con ChatGPT:

### 1. **Obtener API Key de OpenAI:**
- Ve a: https://platform.openai.com/api-keys
- Inicia sesión en tu cuenta
- Crea una nueva API key
- Copia la clave (formato: sk-...)

### 2. **Configurar la clave en el sistema:**

**Opción A: Archivo .env** (Recomendado)
```bash
# Edita el archivo .env y cambia:
OPENAI_API_KEY=sk-tu_clave_aqui
```

**Opción B: Variable de entorno**
```bash
export OPENAI_API_KEY=sk-tu_clave_aqui
```

### 3. **Modelo configurado:**
```bash
OPENAI_MODEL=gpt-4o-mini    # Modelo económico para pruebas
OPENAI_MAX_TOKENS=500       # Respuestas cortas
OPENAI_TEMPERATURE=0.3      # Correcciones consistentes
```

### 4. **Reconstruir el sistema:**
```bash
docker compose up --build -d backend
```

---

## 🎯 **Estructura JSON del modelo:**

El sistema envía este prompt a ChatGPT:

```
PÁRRAFO A CORREGIR:
Este texto esta mal escrito a proposito.

Responder en JSON:
{
  "corrected_text": "Este texto está mal escrito a propósito.",
  "changes_made": ["Añadida tilde en 'está'", "Añadida tilde en 'propósito'"],
  "character_count": 45
}
```

---

## 💰 **Costos estimados (gpt-4o-mini):**

- **Entrada:** ~$0.00015 por cada 1,000 tokens
- **Salida:** ~$0.0006 por cada 1,000 tokens
- **Documento de 100 páginas:** ~$0.50 - $2.00
- **Muy económico para pruebas** 🎉

---

## 🔄 **Flujo del sistema:**

1. **LanguageTool** → ortografía y gramática
2. **ChatGPT** → estilo y coherencia con contexto
3. **Contexto acumulado** → últimos 3 párrafos corregidos
4. **JSON estructurado** → respuestas consistentes

---

## 🚀 **¿Listo para probar?**

1. **Añade tu API key** al archivo .env
2. **Reconstruye el backend**
3. **Ve a http://localhost:3000**
4. **Sube un documento y mira el "Flujo API"**

¡El sistema ya está completamente preparado! 🎉