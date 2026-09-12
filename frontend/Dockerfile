# frontend/Dockerfile
# Multi-stage Node.js build for the Next.js frontend.
# Stage 1 (deps):   installs production + dev dependencies
# Stage 2 (builder): builds the Next.js application
# Stage 3 (runner):  lean runtime image with only what next start needs

# ── Stage 1: dependency installation ─────────────────────────────────────────
FROM node:20-alpine AS deps

# libc6-compat is required for certain native Node modules on Alpine
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy manifest files and install dependencies reproducibly
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# ── Stage 2: Next.js build ────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy node_modules from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy all source files
COPY . .

# Disable Next.js telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Stage 3: production runtime ───────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Copy only the output needed to run `next start`
COPY --from=builder /app/public ./public

# next/image optimisation cache directory — must be writable by nextjs user
RUN mkdir -p .next && chown nextjs:nodejs .next

# Standalone output (requires output: 'standalone' in next.config.js)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
