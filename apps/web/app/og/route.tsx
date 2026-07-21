import { ImageResponse } from "next/og";

export const runtime = "edge";

export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #1e1b4b 0%, #312e81 25%, #581c87 50%, #831843 75%, #1e1b4b 100%)",
          color: "white",
          fontFamily: "system-ui, -apple-system, sans-serif",
          padding: "60px 80px"
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "20px",
            marginBottom: "20px"
          }}
        >
          <div
            style={{
              width: "80px",
              height: "80px",
              borderRadius: "20px",
              background: "linear-gradient(135deg, #a855f7, #ec4899)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "40px",
              fontWeight: 800,
              color: "white"
            }}
          >
            P
          </div>
          <div style={{ fontSize: "52px", fontWeight: 700, letterSpacing: "-0.5px" }}>
            ProActive SEO
          </div>
        </div>
        <div
          style={{
            fontSize: "22px",
            color: "#c4b5fd",
            textAlign: "center",
            maxWidth: "700px",
            lineHeight: 1.4,
            marginTop: "10px"
          }}
        >
          Agentic SEO operations across search, content, technical health, and outreach
        </div>
        <div
          style={{
            display: "flex",
            gap: "30px",
            marginTop: "40px",
            fontSize: "18px",
            color: "#a78bfa"
          }}
        >
          <span>8 specialized agents</span>
          <span>Multi-engine search</span>
          <span>Automated outreach</span>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630
    }
  );
}
