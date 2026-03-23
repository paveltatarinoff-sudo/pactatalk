# GCS-45 Landing Page

Лендинг для продукта «Guided Couple Session 45».

## Стек
- Next.js 15 (App Router) + TypeScript + Tailwind CSS + Supabase

## Запуск локально
```bash
npm install
cp .env.example .env.local   # заполните значения
npm run dev
```
Открыть: http://localhost:3000

## Настройка Supabase
1. Создайте проект на supabase.com
2. В SQL Editor выполните:
```sql
CREATE TABLE waitlist (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  referrer TEXT,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```
3. Скопируйте SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY из Settings → API в .env.local

## Деплой на Vercel
```bash
vercel --prod --yes
```
Добавьте переменные окружения в Vercel Dashboard → Settings → Environment Variables.
