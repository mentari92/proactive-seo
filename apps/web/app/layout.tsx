import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

const APP_NAME = "ProActive SEO";
const APP_DESCRIPTION = "Agentic SEO operations across search, content, technical health, and outreach.";
const APP_URL = "https://seo.mentarich.com";

export const metadata: Metadata = {
  metadataBase: new URL(APP_URL),
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: APP_DESCRIPTION,
  openGraph: {
    title: APP_NAME,
    description: APP_DESCRIPTION,
    type: "website",
    siteName: APP_NAME,
    locale: "en_US",
    images: [{ url: "/og?v=2", width: 1200, height: 630 }]
  },
  twitter: {
    card: "summary_large_image",
    title: APP_NAME,
    description: APP_DESCRIPTION,
    images: ["/og?v=2"]
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
