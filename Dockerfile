# Usar imagen base con Python
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Chrome
RUN apt-get update -qqy && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    unzip \
    wget \
    gnupg \
    xvfb \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libu2f-udev \
    libvulkan1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome y ChromeDriver (versiones compatibles de Chrome for Testing)
RUN LATEST=$(curl -sSL https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    echo "Installing Chrome and ChromeDriver version: $LATEST" && \
    wget -q -O chrome.zip https://storage.googleapis.com/chrome-for-testing-public/$LATEST/linux64/chrome-linux64.zip && \
    unzip chrome.zip && \
    mv chrome-linux64 /opt/chrome && \
    ln -s /opt/chrome/chrome /usr/local/bin/chrome && \
    rm chrome.zip && \
    wget -q -O chromedriver.zip https://storage.googleapis.com/chrome-for-testing-public/$LATEST/linux64/chromedriver-linux64.zip && \
    unzip chromedriver.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf chromedriver-linux64 chromedriver.zip

# Configurar directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Crear usuario no root para mayor seguridad
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Exponer el puerto
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "app:app"]
