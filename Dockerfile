# Landing «Lavori in corso» (branch produzione): pagina statica + piccolo server Node.
FROM node:22-alpine
WORKDIR /app
COPY apps/landing/package.json apps/landing/server.mjs ./
COPY apps/landing/public ./public
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "server.mjs"]
