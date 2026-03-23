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
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://pactatalk.app"),
  title: "PACTA — AI-бот для сложных разговоров в паре",
  description:
    "PACTA — AI помогает парам проходить сложные разговоры в Telegram спокойнее, по очереди и без бесконечного хождения по кругу. Безопасное пространство для важного разговора.",
  openGraph: {
    title: "PACTA — AI-бот для сложных разговоров в паре",
    description:
      "Когда в паре пора обсудить важное, но самим удержать разговор уже не получается, PACTA — AI помогает пройти его спокойнее в Telegram.",
    type: "website",
    locale: "ru_RU",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "PACTA — AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "PACTA — AI-бот для сложных разговоров в паре",
    description: "Бот для пар, которым нужно обсудить важное без криков, перебиваний и хождения по кругу.",
    images: ["/twitter-image"],
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
