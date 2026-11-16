FROM python:3.12-slim

WORKDIR /app

# The repo root is the Python package (it has __init__.py and uses relative
# imports), so the tree is copied into a folder named Aaptivo2 and the app is
# run as Aaptivo2.main:app from /app.
COPY . ./Aaptivo2/

RUN pip install --no-cache-dir -r Aaptivo2/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "Aaptivo2.main:app", "--host", "0.0.0.0", "--port", "8000"]
