FROM node:22-alpine

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/frontend

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN mkdir -p .next && sha256sum package-lock.json | cut -d ' ' -f 1 > node_modules/.package-lock-sha256

COPY docker-entrypoint.sh /usr/local/bin/ai-caller-frontend-entrypoint
RUN chmod +x /usr/local/bin/ai-caller-frontend-entrypoint

EXPOSE 3000
ENTRYPOINT ["/usr/local/bin/ai-caller-frontend-entrypoint"]
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
