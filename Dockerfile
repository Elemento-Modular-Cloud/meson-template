FROM python:3.13-alpine

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN python -m venv venv
RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENTRYPOINT ["python3", "entrypoint.py"]