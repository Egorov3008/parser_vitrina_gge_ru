# Server Deployment Guide

## Варианты запуска

### 1. Docker (рекомендуется)

```bash
# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

### 2. systemd (Linux сервис)

```bash
# Копирование сервиса
sudo cp systemd/vitrina-parser.service /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Запуск
sudo systemctl start vitrina-parser

# Автозагрузка при старте
sudo systemctl enable vitrina-parser

# Статус
sudo systemctl status vitrina-parser

# Логи
journalctl -u vitrina-parser -f
```

### 3. Прямой запуск

```bash
source venv/bin/activate
python -m src.main
```

## Структура

```
├── Dockerfile                 # Docker образ
├── docker-compose.yml         # Docker Compose конфигурация
├── .dockerignore              # Исключения для Docker
└── systemd/
    └── vitrina-parser.service # systemd сервис
```

## Тома (Docker)

| Том | Описание |
|-----|----------|
| `./data` | SQLite база данных |
| `./logs` | Лог файлы |
| `./.env` | Конфигурация (read-only) |
