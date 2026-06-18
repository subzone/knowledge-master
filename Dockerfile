FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY knowledge_master/ knowledge_master/

RUN pip install --no-cache-dir .

EXPOSE 9999

ENTRYPOINT ["km"]
CMD ["serve", "--port", "9999"]
