FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Install Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Set working directory
WORKDIR /app

# Install Python Dependencies First
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node Dependencies and Build MCP Server
# We copy the playwright-mcp package first for caching
COPY playwright-mcp/package.json playwright-mcp/package-lock.json ./playwright-mcp/
WORKDIR /app/playwright-mcp
RUN npm install
# Ensure Playwright browsers are fully installed inside the node module
RUN npx playwright install --with-deps chromium

# Copy all source code
WORKDIR /app
COPY . .

# Compile the TypeScript MCP Server
WORKDIR /app/playwright-mcp
RUN npm run build

# Return to root for execution
WORKDIR /app

# Expose Streamlit Port
EXPOSE 8501

# Disable Streamlit telemetry and email prompt
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Start the Streamlit UI
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
