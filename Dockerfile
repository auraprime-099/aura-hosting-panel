FROM python:3.11-slim

# Install PHP CLI & common extensions for PHP bot support
RUN apt-get update && apt-get install -y --no-install-recommends \
    php-cli \
    php-curl \
    php-mbstring \
    php-xml \
    php-zip \
    procps \
    ffmpeg \
    git \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 120 app:app"]
