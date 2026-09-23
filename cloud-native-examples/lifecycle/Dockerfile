# Simple "app" image for lifecycle demos.
# It intentionally serves a tiny static page so we can focus on container lifecycle concepts.
FROM nginx:1.27-alpine

# Optional: label to show this is a demo image
LABEL org.opencontainers.image.title="lifecycle-demo-app"

# Replace the default page with our demo page
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80
