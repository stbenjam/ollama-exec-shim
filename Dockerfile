# Use UBI9 minimal as a base
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

# Install python and clean up
RUN microdnf install -y python3 python3-pip && \
    microdnf clean all

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install the package and additional dependencies for scripts
RUN pip3 install --no-cache-dir . requests

# Expose the default Ollama port
EXPOSE 11434

# Set environment variables
# Listen on all interfaces so the port is reachable outside the container
ENV HOST="0.0.0.0"
ENV OLLAMA_EXEC_TOKEN=""
ENV OLLAMA_EXEC_ALLOWLIST=""

# Run the shim
ENTRYPOINT ["ollama-exec-shim"]
