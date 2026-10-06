FROM node:22-bookworm-slim
WORKDIR /app
COPY example-remote-server/package*.json ./
RUN npm ci
COPY example-remote-server/ ./
COPY mcp/patch-introspect.js /tmp/patch-introspect.js
RUN node /tmp/patch-introspect.js && npm run build
ENV NODE_ENV=production
EXPOSE 3232
CMD ["node", "dist/index.js"]
