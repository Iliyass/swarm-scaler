FROM python:slim

WORKDIR /code

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY app.py ./

CMD python app.py