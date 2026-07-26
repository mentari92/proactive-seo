import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const email = formData.get("email") as string;
    const password = formData.get("password") as string;

    if (!email || !password) {
      return NextResponse.redirect(new URL("/login?error=missing", request.url));
    }

    const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${apiUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      return NextResponse.redirect(new URL("/login?error=invalid", request.url));
    }

    const data = await response.json();
    const accessToken = data?.data?.tokens?.access_token;

    if (!accessToken) {
      return NextResponse.redirect(new URL("/login?error=invalid", request.url));
    }

    // Redirect to dashboard with the token as a query param
    // The ProductApp will pick it up
    const redirectUrl = new URL("/overview", request.url);
    redirectUrl.searchParams.set("token", accessToken);
    return NextResponse.redirect(redirectUrl);
  } catch {
    return NextResponse.redirect(new URL("/login?error=error", request.url));
  }
}
