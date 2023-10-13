# luchanos_oxford_university

Для поднятия сервисов баз для локальной разработки нужно запустить команду:

```
make up
```

Для накатывания миграций, если файла alembic.ini ещё нет, нужно запустить в терминале команду:

```
alembic init migrations
```

После этого будет создана папка с миграциями и конфигурационный файл для алембика.

- В alembic.ini нужно задать адрес базы данных, в которую будем катать миграции.
- Дальше идём в папку с миграциями и открываем env.py, там вносим изменения в блок, где написано

```
from myapp import mymodel
```

- Дальше вводим: ```alembic revision --autogenerate -m "comment"``` - делается при любых изменениях моделей
- Будет создана миграция
- Дальше вводим: ```alembic upgrade heads```

Для того, чтобы во время тестов нормально генерировались миграции нужно:
- сначала попробовать запустить тесты обычным образом. с первого раза все должно упасть
- если после падения в папке tests создались алембиковские файлы, то нужно прописать туда данные по миграхам
- если они не создались, то зайти из консоли в папку test и вызвать вручную команды на миграции, чтобы файлы появились

Локально:
```ssh -R 80:localhost:8000 nokey@localhost.run```

Вознкла проблема, при создании init миграции она была пустая.
удалить базу:
sudo dropdb -U postgres -h 0.0.0.0 postgres
нужно убить процессы с пользователем shumilin
sudo lsof -i :5432

Потом создать базу
createdb -U postgres -h 0.0.0.0 postgres

И сделать первую миграцию init:
```
alembic init migrations
```
При make makemigrations в файлу alembic.ini должно быть раскоментировано 
# local
sqlalchemy.url = postgresql://postgres:postgres@0.0.0.0:5432/postgres

Поменять .env
- Дальше вводим: ```alembic revision --autogenerate -m "comment"``` - делается при любых изменениях моделей
- Будет создана миграция
- Дальше вводим: ```alembic upgrade heads```

