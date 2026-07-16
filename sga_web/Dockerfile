# SGA Web Application Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY sga_web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend modules from parent
COPY smart_label.py .
COPY generate_ghs_label.py .
COPY settings_manager.py .
COPY user_manager.py .
COPY history_manager.py .
COPY order_status_manager.py .
COPY resource_path.py .
COPY database_client.py .

# Copy optional SAP connector (will fail gracefully if not available)
COPY sap_connector.py . 2>/dev/null || true

# Copy web application
COPY sga_web/ ./sga_web/

# Copy data directories
COPY unified_db/ ./unified_db/
COPY assets/ ./assets/

# Copy user database
COPY users.json ./users.json 2>/dev/null || echo '{"users":[]}' > users.json

# Create directories
RUN mkdir -p generated_labels

# Set working directory to web app
WORKDIR /app/sga_web

# Expose port
EXPOSE 5000

# Production server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
