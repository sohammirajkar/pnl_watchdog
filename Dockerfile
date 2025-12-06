# Build Stage
FROM python:3.11-slim as builder

# Install system dependencies for Rust and Python
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Maturin
RUN pip install maturin

# Copy Project
WORKDIR /app
COPY . .

# Build Rust Core
WORKDIR /app/pnl_watchdog_lib
RUN maturin build --release

# Runtime Stage
FROM python:3.11-slim

WORKDIR /app

# Install Runtime Deps (Postgres client)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheel from builder
COPY --from=builder /app/pnl_watchdog_lib/target/wheels/*.whl /tmp/

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install /tmp/*.whl

# Copy Application Code
COPY pnl_watchdog_lib /app/pnl_watchdog_lib

# Environment Variables
ENV DATABASE_URL="postgresql+asyncpg://user:password@db:5432/pnl_watchdog"
ENV PYTHONPATH=/app

# Expose Port
EXPOSE 8000

# Start Command
CMD ["uvicorn", "pnl_watchdog_lib.api.main:app", "--host", "0.0.0.0", "--port", "8000"]