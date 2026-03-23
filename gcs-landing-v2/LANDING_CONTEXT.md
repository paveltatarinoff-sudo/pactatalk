# PACTA Landing Context

Короткий контекст-файл для работы с текущим лендингом без истории диалога.

## Что это
- Актуальный публичный лендинг продукта `PACTA — AI`
- Отдельный Next.js-проект
- Основной production-домен: `https://pactatalk.app`
- Vercel project: `pactatalk-app`

## Где главное
- Основная страница: [app/page.tsx](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/app/page.tsx)
- Метаданные и social preview: [app/layout.tsx](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/app/layout.tsx)
- Open Graph image: [app/opengraph-image.tsx](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/app/opengraph-image.tsx)
- Twitter image: [app/twitter-image.tsx](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/app/twitter-image.tsx)
- Глобальные стили: [app/globals.css](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/app/globals.css)

## Текущая структура страницы
1. Hero с CTA в Telegram
2. Telegram mockup
3. Pain block
4. Два визуальных фотоблока
5. How it works
6. Topics
7. Trust block
8. FAQ
9. Final CTA

## Важные локальные ассеты
- Левый фотоблок: [public/landing/left-conflict-selected.png](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/public/landing/left-conflict-selected.png)
- Правый фотоблок: [public/landing/right-relief-selected.jpg](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/public/landing/right-relief-selected.jpg)
- Аватары в Telegram mockup:
  - [public/landing/avatars/male.jpg](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/public/landing/avatars/male.jpg)
  - [public/landing/avatars/female.jpg](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/public/landing/avatars/female.jpg)
- Логотип в шапке:
  - [public/landing/brand/logo-header.png](/Users/pashkamoroz/Documents/Ai%20family%20coach/gcs-landing-v2/public/landing/brand/logo-header.png)

## Что важно не сломать
- CTA ведёт на `https://t.me/PactaTalkBot`
- `metadataBase` должен оставаться `https://pactatalk.app`, не `localhost`
- Social preview должен ссылаться на `/opengraph-image` и `/twitter-image`
- Не возвращать старый waitlist/Supabase слой

## Локальная проверка
```bash
cd "/Users/pashkamoroz/Documents/Ai family coach/gcs-landing-v2"
npm install
npm run dev
```

## Базовые проверки
```bash
npm run build
npm run lint
```

## Деплой
```bash
vercel deploy --prod --yes
```

## Что уже вычищено
- Старая папка `gcs-landing` удалена
- Старый waitlist/Supabase код удалён
- Внешние ссылки на изображения из основного UI убраны
