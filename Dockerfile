FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create cloud directory
RUN mkdir -p cloud

# Expose port
EXPOSE 5000

# Production server
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]