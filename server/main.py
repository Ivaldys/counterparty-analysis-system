
#uvicorn main:app --reload
from fastapi import FastAPI
from routers.auth import router as auth_router
from routers.metrics import router as metrics_router
from routers.forgot import router as forgot_router
from routers.profile import router as profile_router
from routers.counterparties import router as counterparties_router
app = FastAPI(title="Контрагенты API")

app.include_router(auth_router)
app.include_router(counterparties_router)
app.include_router(metrics_router)
app.include_router(forgot_router)
app.include_router(profile_router)