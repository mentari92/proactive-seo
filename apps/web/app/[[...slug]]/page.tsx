import { ProductApp } from "@/components/product-app";

export default async function CatchAllPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const resolved = await params;
  const route = `/${resolved.slug?.join("/") ?? "overview"}`;
  return <ProductApp route={route} />;
}
