# PACTA Landing v2

Актуальная публичная версия лендинга для `PACTA — AI`.

## Стек
- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS 4

## Локальный запуск
```bash
npm install
cp .env.example .env.local
npm run dev
```

Открыть в браузере:
`http://localhost:3000`

## Переменные окружения
Для локальной разработки достаточно:

```bash
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

Для production укажите публичный домен проекта, например:

```bash
NEXT_PUBLIC_SITE_URL=https://pactatalk.app
```

## Сборка
```bash
npm run build
npm run start
```

## Деплой
Лендинг рассчитан на деплой в Vercel как отдельный проект.
