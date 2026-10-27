FROM node:20-alpine AS builder
WORKDIR /app

ARG VITE_API_URL=http://localhost:8001
ENV VITE_API_URL=$VITE_API_URL

# Stripe Payment Link URLs for the trial upgrade buttons on the Billing page.
ARG VITE_STRIPE_LINK_BUSINESS
ARG VITE_STRIPE_LINK_ENTERPRISE
ENV VITE_STRIPE_LINK_BUSINESS=$VITE_STRIPE_LINK_BUSINESS
ENV VITE_STRIPE_LINK_ENTERPRISE=$VITE_STRIPE_LINK_ENTERPRISE

COPY package*.json ./
RUN npm ci
COPY . .

# The /demo sales-demo page is left out of published images; same removal
# mirror-oss.yml applies to the OSS mirror. Build with
# --build-arg INCLUDE_DEMO=true to keep it.
ARG INCLUDE_DEMO=false
RUN if [ "$INCLUDE_DEMO" != "true" ]; then \
      rm -rf src/pages/demo src/api/demo.ts \
      && sed -i '/^import { DemoPage } from ".\/pages\/demo\/DemoPage";$/d' src/App.tsx \
      && sed -i '/<Route path="demo"/d' src/App.tsx; \
    fi
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.d/40-aicontrol-config.sh /docker-entrypoint.d/40-aicontrol-config.sh
RUN chmod +x /docker-entrypoint.d/40-aicontrol-config.sh
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
