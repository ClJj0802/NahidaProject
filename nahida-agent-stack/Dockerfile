FROM ghcr.io/openclaw/openclaw:2026.9.2

USER root

ENV PLAYWRIGHT_BROWSERS_PATH=/home/node/.cache/ms-playwright

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fonts-liberation \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        xvfb \
    && install -d -m 0755 -o node -g node /home/node/.cache \
    && mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" \
    && node /app/node_modules/playwright-core/cli.js install --with-deps chromium \
    && chown -R node:node /home/node/.cache \
    && rm -rf /var/lib/apt/lists/*

USER node

ENV HOME=/home/node
ENV OPENCLAW_HOME=/home/node
ENV OPENCLAW_STATE_DIR=/home/node/.openclaw
ENV OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json
ENV OPENCLAW_WORKSPACE_DIR=/workspace

COPY --chown=node:node openclaw.json /home/node/.openclaw/openclaw.json

WORKDIR /app