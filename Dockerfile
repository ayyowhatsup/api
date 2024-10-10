FROM python:3.12-alpine3.19

WORKDIR /app

# Copy the rest of the application code into the container
COPY . .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 8080

CMD ["fastapi", "run", "main.py", "--port", "8080"]