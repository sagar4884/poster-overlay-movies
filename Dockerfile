# Use a Python base image that includes necessary system libraries and fonts
FROM python:3.11-slim

# Set environment variables for non-interactive commands
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies for Pillow (Image processing) and a standard font for the IMDB overlay
# DejaVuSans-Bold.ttf is required by the script for the IMDB rating box
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    fontconfig \
    ttf-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main script
COPY poster_processor.py .

# Command to run the script when the container starts
CMD ["python", "poster_processor.py"]