import json
import logging
from time import sleep

import sentry_sdk
import uvicorn
import aiohttp
from fastapi import FastAPI, Request, Depends
from fastapi.routing import APIRouter
from fastapi_utils.tasks import repeat_every
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.staticfiles import StaticFiles
from starlette_exporter import handle_metrics
from starlette_exporter import PrometheusMiddleware

import settings
from api.actions.visit import _create_new_visit, _check_visit
from api.handlers import user_router
from api.login_handler import login_router
from api.schemas import VisitCreate
from api.service import service_router
from db.models import User
from db.models import Point as Points
from db.session import get_db
from managment.dump import dump_db
from pages.router import router as router_pages
from schemas import Answer

from geopy.distance import distance
from geopy.point import Point

from swh import TG_API

# sentry configuration
sentry_sdk.init(
    dsn=settings.SENTRY_URL,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production,
    traces_sample_rate=1.0,
)

#########################
# BLOCK WITH API ROUTES #
#########################

# create instance of the app
app = FastAPI(title="luchanos-oxford-university")

# Логгирование
logger.remove()
logger.add("info.log", format="Log: {time} -- {level} -- {message} -- {file}:{line} {function}", level="INFO",
           enqueue=True)

# origins = [
#     "http://localhost:3000",
# ]
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PATCH", "PUT"],
#     allow_headers=["Content-Type", "Set-Cookie", "Access-Control-Allow-Headers", "Access-Control-Allow-Origin",
#                    "Authorization"],
# )

app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", handle_metrics)

# create the instance for the routes
main_api_router = APIRouter()

# set routes to the app instance
main_api_router.include_router(user_router, prefix="/user", tags=["user"])
main_api_router.include_router(login_router, prefix="/login", tags=["login"])
main_api_router.include_router(service_router, tags=["service"])
app.include_router(main_api_router)

###########################
# BLOCK WITH PAGES ROUTES #
###########################
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router_pages)

################
# TG BOT #######
################
LOCATIONS = [
    {
        'name': 'Алкон',
        'location': {
            'latitude': 55.805278,
            'longitude': 37.520588,
        }
    },
    {
        'name': 'Сколково',
        'location': {
            'latitude': 55.685162,
            'longitude': 37.350982,
        }
    }
]


def get_point(latitude: float, longitude: float) -> Point:
    return Point(latitude=latitude, longitude=longitude)


async def check_user(obj, db):
    # проверяем есть ли пользователь в системе приславший локацию
    received_username = f'@{obj.message.from_tg.username}'
    answer: str | None = None
    try:
        for _ in range(10):
            query = select(User).where(User.tg_username == received_username)
            user = await db.scalar(query)
        sleep(1)
    except Exception as err:
        print(err)
        logging.error(f"Ошибка при выполнении запроса к базе данных: {err}")
        user = None

    if user is None:
        answer = 'Вы не зарегистрированы в системе. Свяжитесь с администратором для регистрации.'
        print(answer)
        logger.error(answer)

    return user, answer


async def check_dist(obj, db):
    answer: str | None = None
    target_point = get_point(obj.message.location.latitude, obj.message.location.longitude)
    points = await db.execute(select(Points).where(Points.is_active == True))
    points = points.scalars().all()

    for point in points:
        try:
            latitude = point.coordinates.split(":")[0]
            longitude = point.coordinates.split(":")[1]
        except:
            continue

        dist = int(distance(
            target_point,
            get_point(latitude, longitude)
        ).m)
        if dist < 500:
            return point, answer

    answer = f'Не находитесь на объекте'
    return None, answer


@app.post("/")
async def read_root(request: Request, db: AsyncSession = Depends(get_db)):
    result = await request.json()
    obj = Answer.parse_obj(result)
    print(obj)

    reply_markup = {
        "keyboard":
            [
                [
                    {
                        "request_location": True,
                        "text": "Отправить локацию",
                    }
                ],
            ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }

    # проверка, есть ли геоданные
    point_name: str = ""
    answer: str = "Ответ сервера"
    answer_position: str = "Ответ сервера (геопозиция)"
    if obj.message.location == None:
        answer = 'Для отправки геоданных нажмите кнопку "Отправить локацию"'
    else:
        user, answer = await check_user(obj, db)
        if user:
            point, answer = await check_dist(obj, db)
            if point:
                # записываем визит в базу
                body: VisitCreate = VisitCreate.parse_obj(
                    {
                        "user_id": user.user_id,
                        "point": point.id,
                    }
                )
                try:
                    if not await _check_visit(user.user_id, db):
                        answer = 'Начало смены\n'
                    else:
                        answer = 'Конец смены\n'
                    answer_position = f'Данные записаны. Местоположение: {point.name}\n'
                    print(answer)
                    res = await _create_new_visit(body, db)
                    print(res)
                except:
                    answer = 'Возникла ошибка при записи данных. Попробуйте еще раз.'
                    print(answer)
            # except IntegrityError as err:
            #     logger.error(err)
    data = {
        'chat_id': obj.message.chat.id,
        'text': answer,
        'reply_markup': json.dumps(reply_markup)
    }

    data_position = {
        'chat_id': obj.message.chat.id,
        'text': answer_position,
        'reply_markup': json.dumps(reply_markup)
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
                f'https://api.telegram.org/bot{TG_API}/sendMessage',
                data=data
        ) as response:
            print(f"Shift info message status: {response.status}")

    async with aiohttp.ClientSession() as session:
        async with session.post(
                f'https://api.telegram.org/bot{TG_API}/sendMessage',
                data=data_position
        ) as response:
            print(f"Position info message status: {response.status}")

    return {'status': 'OK'}


### Регулярные таски ###
@app.on_event("startup")
@repeat_every(seconds=60 * 60 * 24)  # 24 часа
async def regular_dump_task():
    """Дамп базы раз в день"""
    logger.info("Начало регулярного дампа")
    try:
        await dump_db()
    except Exception as e:
        logger.error(f"Во время регулярного дампа произошла ошибка: {e}")


if __name__ == "__main__":
    # run app on the host and port
    uvicorn.run(app, host="0.0.0.0", port=settings.APP_PORT)
