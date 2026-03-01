FROM node:20-alpine

WORKDIR /app

# Instalar dependencias
COPY package.json ./
RUN npm install

# Copiar código fuente
COPY . .

# Crear directorio public si no existe (requerido por Next.js)
RUN mkdir -p public

ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

# Modo desarrollo — escuchar en todas las interfaces para Docker
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]
