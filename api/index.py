# Vercel Serverless Function для FastAPI
import os
from mangum import Mangum

# Импортировать FastAPI приложение
from backend.app.main import app

# Адаптер для Vercel serverless
handler = Mangum(app, lifespan="off")
