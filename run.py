# for running the backend service in development mode
# uvicorn src.main:app --reload --port 8000 --host 0.0.0.0 
# here is the code to run the backend service in production mode
# gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app

