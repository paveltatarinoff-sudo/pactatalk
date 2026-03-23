import { ImageResponse } from "next/og";

export const runtime = "nodejs";
export const alt = "PACTA — AI";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#f7f3ed",
          color: "#171717",
          padding: "48px",
          position: "relative",
          fontFamily: "system-ui",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: "26px",
            borderRadius: "40px",
            border: "12px solid #df5f4d",
            opacity: 0.92,
          }}
        />

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
            height: "100%",
            padding: "36px 40px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "22px" }}>
            <div style={{ display: "flex", alignItems: "center", position: "relative", width: "112px", height: "72px" }}>
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 6,
                  width: "58px",
                  height: "58px",
                  borderRadius: "22px",
                  background: "#2f3847",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  right: 0,
                  top: 0,
                  width: "62px",
                  height: "62px",
                  borderRadius: "22px",
                  background: "#ff5f4d",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: 34,
                  top: 24,
                  width: 0,
                  height: 0,
                  borderTop: "10px solid transparent",
                  borderBottom: "10px solid transparent",
                  borderLeft: "38px solid white",
                  transform: "skewX(-28deg)",
                }}
              />
            </div>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                lineHeight: 1,
              }}
            >
              <div
                style={{
                  fontFamily: "system-ui",
                  fontSize: 52,
                  fontWeight: 700,
                  letterSpacing: "-0.05em",
                }}
              >
                PACTA — AI
              </div>
              <div
                style={{
                  marginTop: 6,
                  fontSize: 22,
                  color: "#6b6b6b",
                }}
              >
                AI-фасилитатор для сложных разговоров в паре
              </div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "26px" }}>
            <div
              style={{
                display: "flex",
                fontFamily: "system-ui",
                fontSize: 84,
                lineHeight: 0.94,
                letterSpacing: "-0.06em",
                fontWeight: 700,
                maxWidth: "920px",
              }}
            >
              Трудные разговоры в паре — спокойнее и яснее
            </div>

            <div
              style={{
                display: "flex",
                fontSize: 32,
                lineHeight: 1.35,
                color: "#5d5d5d",
                maxWidth: "980px",
              }}
            >
              PACTA AI помогает парам проходить трудные разговоры по структуре: слышать друг друга, не терять суть и двигаться к большей ясности.
            </div>
          </div>

          <div style={{ display: "flex", gap: "14px" }}>
            {["В Telegram", "По очереди", "По структуре"].map((item) => (
              <div
                key={item}
                style={{
                  display: "flex",
                  padding: "14px 22px",
                  borderRadius: "999px",
                  border: "2px solid #e6d8cf",
                  background: "rgba(255,255,255,0.85)",
                  fontSize: 24,
                  color: "#2f3847",
                }}
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
    size,
  );
}
