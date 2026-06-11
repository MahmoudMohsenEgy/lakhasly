# Study Lamp — Egyptian-Arabic content explainer (web)
#
# Built on the official Playwright Python image, which already ships headless
# Chromium plus all of its system libraries and a broad font set — exactly what
# the PDF renderer needs. This removes the single biggest source of deployment
# pain (Chromium deps + fonts).
#
# If PDF rendering ever fails with a "browser not found / version mismatch"
# error, align this tag with the Playwright version pip installs
# (`docker compose exec studylamp pip show playwright`).
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

WORKDIR /app

# Arabic font fallback. The study PDF requests "Cairo" from Google Fonts at render
# time, but bake a Noto Arabic face in as well so Arabic text never falls back to
# empty boxes if Google Fonts is unreachable during a render.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-noto-core fonts-noto-ui-core \
 && rm -rf /var/lib/apt/lists/*

# Install the app, then fetch the Chromium build matching the installed Playwright
# version (system deps are already present in the base image).
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && playwright install chromium

# Generated modules (PDFs, thumbnails, meta.json) live here; the compose file
# mounts a volume so they survive container rebuilds.
ENV OUTPUT_DIR=/app/output
RUN mkdir -p /app/output

EXPOSE 8000

# IMPORTANT: one worker only. Job state is in-memory (JobManager's dict + daemon
# threads), so multiple workers/replicas would not share running jobs. Bind to
# 0.0.0.0 inside the container (the host publishes it to localhost only).
CMD ["uvicorn", "explainer.web.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
