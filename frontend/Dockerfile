# --- deps ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# --- build ---
FROM node:20-alpine AS build
WORKDIR /app
# Brauzer uchun backend manzili — build vaqtida kodga yoziladi (.env.local image'ga kirmaydi, .dockerignore).
# Bo'sh = sahifa ochilgan host'ning 8000-porti (lib/config.ts). docker-compose: loyiha ildizidagi .env dan.
ARG NEXT_PUBLIC_API_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

# --- runtime (standalone) ---
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# server.js HOSTNAME'da tinglaydi; Docker uni konteyner ID'si qilib qo'yadi — aniq beramiz. Tashqariga faqat
# docker-compose'dagi "127.0.0.1:3000:3000" orqali chiqadi.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
