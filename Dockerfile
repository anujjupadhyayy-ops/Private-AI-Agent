# Use Python 3.12 on slim Linux — same version as your Mac
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies
# ffmpeg — required by Whisper for voice transcription
# build-essential — required to compile some Python packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker caches this layer
# If requirements.txt hasn't changed, Docker skips reinstalling packages
# This makes rebuilds significantly faster
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application files
COPY . ./

# Create data directories
# documents subdirectories match your domain structure
RUN mkdir -p documents/personal documents/finance documents/work \
    outputs vectorstore logs

# Expose Streamlit port to the host machine
EXPOSE 8501

# Start command — setup database then launch Streamlit
CMD python setup_postgres.py && \
    streamlit run app.py --server.headless true