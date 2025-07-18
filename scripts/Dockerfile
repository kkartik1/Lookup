FROM docker.repo1.uhc.com/python:latest

WORKDIR /app
COPY . /app
RUN chmod -R 777 /app
RUN pip install -r requirements.txt

EXPOSE 3463

#ENTRYPOINT ["streamlit run "]

CMD ["streamlit", "run", "fts.py", "--server.port=3464", "--server.address=0.0.0.0"]


