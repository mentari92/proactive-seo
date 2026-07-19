export type ApiEnvelope<T> = {
  data: T;
  meta: { request_id: string; timestamp: string; cursor?: string; has_more?: boolean };
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export async function api<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(problem.detail ?? "Request failed");
  }
  return response.json() as Promise<ApiEnvelope<T>>;
}
