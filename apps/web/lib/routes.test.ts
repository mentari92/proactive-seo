import { describe, expect, it } from "vitest";
import { ROUTES } from "./routes";

describe("documented application routes", () => {
  it("contains at least fifty unique product routes", () => {
    expect(ROUTES.length).toBeGreaterThanOrEqual(50);
    expect(new Set(ROUTES).size).toBe(ROUTES.length);
  });
});

