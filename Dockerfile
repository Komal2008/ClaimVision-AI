# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (e.g., for OpenCV)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
# Based on the repo structure, it's located in the code/ directory
COPY code/requirements.txt ./code/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r code/requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Set the working directory to where the app is located
WORKDIR /app/code

# Command to run the application
CMD ["streamlit", "run", "app.py"]
