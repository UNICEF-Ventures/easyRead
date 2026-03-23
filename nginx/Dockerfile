# Multi-stage nginx image with bundled frontend
FROM node:20-alpine AS frontend_build

WORKDIR /app/frontend

ARG VITE_API_BASE_URL=/api
ARG VITE_MEDIA_BASE_URL=
ARG VITE_DEBUG_VALIDATION=false
ARG VITE_USE_EXTERNAL_PDF_CONVERTER=false
ARG VITE_PDF_CONVERTER_URL=
ARG VITE_PDF_CONVERTER_API_KEY=
ARG VITE_PDF_CONVERTER_TOKEN=
ARG VITE_PDF_CONVERTER_EMAIL=
ARG VITE_API_STAGE=
ARG VITE_PROJECT_KEY=
ARG VITE_BASE_URL=/easyread/
ARG VITE_BASE_URL_PROD=/easyread/

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_MEDIA_BASE_URL=$VITE_MEDIA_BASE_URL \
    VITE_DEBUG_VALIDATION=$VITE_DEBUG_VALIDATION \
    VITE_USE_EXTERNAL_PDF_CONVERTER=$VITE_USE_EXTERNAL_PDF_CONVERTER \
    VITE_PDF_CONVERTER_URL=$VITE_PDF_CONVERTER_URL \
    VITE_PDF_CONVERTER_API_KEY=$VITE_PDF_CONVERTER_API_KEY \
    VITE_PDF_CONVERTER_TOKEN=$VITE_PDF_CONVERTER_TOKEN \
    VITE_PDF_CONVERTER_EMAIL=$VITE_PDF_CONVERTER_EMAIL \
    VITE_API_STAGE=$VITE_API_STAGE \
    VITE_PROJECT_KEY=$VITE_PROJECT_KEY \
    VITE_BASE_URL=$VITE_BASE_URL \
    VITE_BASE_URL_PROD=$VITE_BASE_URL_PROD

COPY frontend/package*.json ./
COPY frontend/vendor ./vendor
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend_build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
