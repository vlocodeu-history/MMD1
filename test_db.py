from sqlalchemy import create_engine
url = "postgresql+pg8000://postgres:00000@localhost:5432/MMDproject"
eng = create_engine(url, future=True, pool_pre_ping=True)
with eng.connect() as c:
    print("OK:", c.exec_driver_sql("select version()").scalar())
