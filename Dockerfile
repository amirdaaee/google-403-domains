FROM python:3.9-slim
WORKDIR /app
COPY ./requirements.txt .
RUN set -x && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
CMD [ "python","script.py" ]
