import { NextRequest, NextResponse } from "next/server";
import { getSupabaseClient } from "@/lib/supabase";

// In-memory rate limiter: IP → [timestamps]
const rateLimitMap = new Map<string, number[]>();
const RATE_LIMIT = 5;
const WINDOW_MS = 10 * 60 * 1000; // 10 minutes

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const timestamps = (rateLimitMap.get(ip) || []).filter((t) => now - t < WINDOW_MS);
  if (timestamps.length >= RATE_LIMIT) return true;
  timestamps.push(now);
  rateLimitMap.set(ip, timestamps);
  return false;
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export async function POST(req: NextRequest) {
  const ip =
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    req.headers.get("x-real-ip") ||
    "unknown";

  // Rate limit
  if (isRateLimited(ip)) {
    return NextResponse.json(
      { message: "Слишком много запросов. Попробуйте позже." },
      { status: 429 }
    );
  }

  const body = await req.json();
  const { email, website, referrer, utm_source, utm_medium, utm_campaign } = body;

  // Honeypot check
  if (website) {
    return NextResponse.json({ ok: true }); // silently accept bots
  }

  // Email validation
  if (!email || !isValidEmail(email)) {
    return NextResponse.json(
      { message: "Некорректный email." },
      { status: 400 }
    );
  }

  // Supabase
  const supabase = getSupabaseClient();
  if (!supabase) {
    return NextResponse.json(
      { error: "storage_not_configured" },
      { status: 503 }
    );
  }

  // Check duplicate
  const { data: existing } = await supabase
    .from("waitlist")
    .select("id")
    .eq("email", email.toLowerCase().trim())
    .maybeSingle();

  if (existing) {
    return NextResponse.json(
      { message: "Email уже зарегистрирован." },
      { status: 409 }
    );
  }

  // Insert
  const { error } = await supabase.from("waitlist").insert({
    email: email.toLowerCase().trim(),
    referrer: referrer || null,
    utm_source: utm_source || null,
    utm_medium: utm_medium || null,
    utm_campaign: utm_campaign || null,
  });

  if (error) {
    console.error("Supabase insert error:", error);
    return NextResponse.json(
      { message: "Ошибка при сохранении. Попробуйте позже." },
      { status: 500 }
    );
  }

  return NextResponse.json({ ok: true }, { status: 201 });
}
