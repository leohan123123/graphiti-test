# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# Add any other system dependencies that your application might need
# RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY ./app /app/app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable for the application module
ENV MODULE_NAME="app.main"
ENV VARIABLE_NAME="app"

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
