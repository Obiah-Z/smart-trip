FROM node:20-alpine AS build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./

ARG VITE_API_BASE=
ARG VITE_AMAP_JS_KEY=
ARG VITE_AMAP_SECURITY_JSCODE=
ARG VITE_MAP_PROVIDER=

ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_AMAP_JS_KEY=$VITE_AMAP_JS_KEY
ENV VITE_AMAP_SECURITY_JSCODE=$VITE_AMAP_SECURITY_JSCODE
ENV VITE_MAP_PROVIDER=$VITE_MAP_PROVIDER

RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
