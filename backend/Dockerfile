FROM python:3.11-slim

# Instalar LibreOffice headless para conversión DOCX→PDF
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice-writer \
        libreoffice-core \
        fonts-liberation \
        fonts-noto-core \
        curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir openai==1.51.0 httpx==0.27.2

# Copiar código
COPY . .

# Puerto por defecto de uvicorn
EXPOSE 8000

# Comando por defecto: servidor API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
