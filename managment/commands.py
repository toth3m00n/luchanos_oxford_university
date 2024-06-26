import requests
from envparse import Env
from loguru import logger

from reports.report import get_formatted_year_and_month

Env.read_envfile('env_vars/report.env')
env = Env()

TOKEN = env.str("TOKEN")
URL = 'https://cloud-api.yandex.net/v1/disk/resources'
headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'OAuth {TOKEN}'}


async def upload_file(loadfile, savefile, replace=True):
    logger.info(f"Загрузка {loadfile} на диск: {savefile} ")
    """Загрузка файла.
    loadfile: Путь к загружаемому файлу
    savefile: Путь к файлу на Диске
    replace: true or false Замена файла на Диске"""
    res = requests.get(f'{URL}/upload?path={savefile}&overwrite={replace}', headers=headers).json()
    with open(loadfile, 'rb') as f:
        try:
            requests.put(res['href'], files={'file': f})
        except KeyError:
            print(res)
            return res


async def upload_to_ydisk(loadfile, savefile):
    try:
        await upload_file(loadfile, savefile)
    except Exception as e:
        return f'Failed upload file {loadfile}: {e}'
    return f'OK'

