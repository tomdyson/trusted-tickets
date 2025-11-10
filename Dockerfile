FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies explicitly (Django apps don't need editable install)
RUN uv pip install "django>=5.2.6,<5.3.0" "psycopg2-binary>=2.9.9" "dj-database-url>=2.1.0" "gunicorn>=21.2.0" "whitenoise>=6.6.0"

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create entrypoint script
RUN echo '#!/bin/bash\npython manage.py migrate\nexec gunicorn trusted_tickets.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Run migrations and start application
CMD ["/app/entrypoint.sh"]
