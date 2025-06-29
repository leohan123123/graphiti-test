# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app

# Set the working directory in the container
WORKDIR $APP_HOME

# Install system dependencies
# - tesseract-ocr for pytesseract
# - libgl1-mesa-glx and libglib2.0-0 for potential CV/graphics operations by Pillow/PyMuPDF
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       libgl1-mesa-glx \
       libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY ./app $APP_HOME/app
# Copy the .env file. In production, prefer injecting environment variables via Docker Compose.
# This .env provides defaults if not overridden.
COPY .env $APP_HOME/.env

# Make port 8000 available to the world outside this container (as specified in .env and CMD)
EXPOSE 8000

# Command to run the application using Uvicorn directly
# This is often preferred in Docker for more explicit control over the server process.
# The app/main.py's __main__ block with dynamic port finding is more for local execution.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
