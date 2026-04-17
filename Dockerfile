FROM python:3.11-slim

WORKDIR /app

# Install cron and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Copy crontab
COPY docker/crontab /etc/cron.d/harmonix-cron
RUN sed -i 's/\r$//' /etc/cron.d/harmonix-cron \
    && chmod 0644 /etc/cron.d/harmonix-cron \
    && crontab /etc/cron.d/harmonix-cron

# Create log directory
RUN mkdir -p /app/logs

EXPOSE 8000

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
