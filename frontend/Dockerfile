# Frontend image for full-Docker mode:
#   stage 1 builds the React app with Node, stage 2 serves it with nginx.
# The generated API types (src/core/api/generated/) must exist before building;
# `make up` runs `make gen-api` first.

FROM node:22-alpine AS build
WORKDIR /frontend
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
RUN test -f src/core/api/generated/schema.d.ts \
    || (echo "Missing generated API types: run 'make gen-api' before building." && exit 1)
RUN npm run build

FROM nginx:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html
EXPOSE 80
