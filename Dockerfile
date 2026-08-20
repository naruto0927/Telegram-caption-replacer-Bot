# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install dependencies into a separate layer for better cache reuse
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainerregistry.image.title="Telegram Keyword Editor Bot" \
      org.opencontainerregistry.image.description="Auto-replaces keywords in a Telegram channel" \
      org.opencontainerregistry.image.licenses="MIT"

# Security: run as a non-root user
RUN useradd --no-create-home --shell /bin/false botuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source code
COPY . .

# Drop privileges
USER botuser

# The bot is fully headless — no ports are exposed
# All persistent state lives in MongoDB, not on the filesystem

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "bot.py"]
