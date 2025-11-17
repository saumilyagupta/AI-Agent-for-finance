FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install dependencies
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY static/ ./static/

# Initialize database
RUN python -c "from app.database.database import init_db; init_db()"

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

