# Python Sandbox Runtime Image
# This image is used to execute untrusted Python code safely

FROM python:3.11-slim

# Install common Python packages that are safe to use
# Add more packages as needed for your use case
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.3 \
    requests==2.31.0 \
    matplotlib==3.7.2 \
    scipy==1.11.1 \
    openpyxl==3.1.2

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash sandbox

# Create output directory for user-generated files
RUN mkdir -p /tmp/output && chown sandbox:sandbox /tmp/output

# Set working directory
WORKDIR /app

# Switch to non-root user
USER sandbox

# Default command (will be overridden)
CMD ["python3"]
