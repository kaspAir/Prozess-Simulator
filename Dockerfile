FROM python:3.12-slim

# Nicht als root laufen
RUN useradd --create-home --shell /bin/bash pros

WORKDIR /app

# Dependencies zuerst (Docker-Layer-Cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Quellcode
COPY --chown=pros:pros . .

# Entrypoint ausfuehrbar machen
RUN chmod +x /app/docker-entrypoint.sh

# Datenbankverzeichnis (wird als Volume gemountet)
RUN mkdir -p /app/data && chown pros:pros /app/data

USER pros

# SQLite im persistenten Volume (absoluter Pfad -> 4 Slashes)
ENV DATABASE_URL=sqlite:////app/data/prozess_simulator.db
ENV FLASK_DEBUG=0
ENV PORT=5000

EXPOSE 5000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Gunicorn: 2 Worker, 120s Timeout
CMD ["gunicorn", "run:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
