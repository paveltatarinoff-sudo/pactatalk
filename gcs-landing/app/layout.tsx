import type { Metadata } from "next";
import { Manrope, Rubik } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-manrope",
});

const rubik = Rubik({
  subsets: ["latin", "cyrillic"],
  variable: "--font-rubik",
});

export const metadata: Metadata = {
  title: "PACTA — AI-бот для сложных разговоров в паре",
  description:
    "PACTA — AI помогает парам проходить сложные разговоры в Telegram спокойнее, по очереди и без бесконечного хождения по кругу. Не терапия. Не судья. Структура для важного разговора.",
  openGraph: {
    title: "PACTA — AI-бот для сложных разговоров в паре",
    description:
      "Когда важный разговор снова идёт по кругу, PACTA — AI помогает пройти его спокойнее и по очереди прямо в Telegram.",
    type: "website",
    locale: "ru_RU",
  },
  twitter: {
    card: "summary_large_image",
    title: "PACTA — AI-бот для сложных разговоров в паре",
    description: "Бот для пар, которым нужно обсудить важное без криков, перебиваний и хождения по кругу.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className={`${manrope.variable} ${rubik.variable} antialiased`}>{children}</body>
    </html>
  );
}
