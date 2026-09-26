# Frontend image for full-Docker mode:
#   stage 1 builds the React app with Node, stage 2 serves it with nginx.

FROM node:22-alpine AS build
WORKDIR /frontend
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html
EXPOSE 80
