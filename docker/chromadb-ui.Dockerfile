FROM node:22-alpine AS build

ARG CHROMADB_UI_COMMIT=1b0b0de7014c9e28d60da2c81fdc2d88bb515bf5

RUN apk add --no-cache git
RUN git clone https://github.com/BlackyDrum/chromadb-ui.git /app \
    && git -C /app checkout --detach "${CHROMADB_UI_COMMIT}"

WORKDIR /app
RUN npm ci
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
