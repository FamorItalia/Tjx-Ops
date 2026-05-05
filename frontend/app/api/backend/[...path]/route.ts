import { NextRequest, NextResponse } from "next/server";

const BACKEND = (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function proxy(request: NextRequest, path: string[]) {
  const search = request.nextUrl.search || "";
  const url = `${BACKEND}/api/v1/${path.join("/")}${search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  const incomingAuth = request.headers.get("authorization");
  const tokenFromCookie = request.cookies.get("ops_session_token")?.value;
  if (incomingAuth) {
    headers.set("authorization", incomingAuth);
  } else if (tokenFromCookie) {
    headers.set("authorization", `Bearer ${tokenFromCookie}`);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const response = await fetch(url, init);
  const noBodyStatus = response.status === 204 || response.status === 205 || response.status === 304;
  if (noBodyStatus) {
    return new NextResponse("", { status: 200 });
  }

  const contentTypeOut = response.headers.get("content-type") || "application/json";
  const contentDisposition = response.headers.get("content-disposition");
  const isJsonLike = contentTypeOut.includes("application/json") || contentTypeOut.includes("text/");

  if (!isJsonLike) {
    const bytes = await response.arrayBuffer();
    const headersOut: Record<string, string> = { "Content-Type": contentTypeOut };
    if (contentDisposition) {
      headersOut["Content-Disposition"] = contentDisposition;
    }
    return new NextResponse(bytes, {
      status: response.status,
      headers: headersOut,
    });
  }

  const text = await response.text();

  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": contentTypeOut,
    },
  });
}

export async function GET(request: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(request, ctx.params.path || []);
}

export async function POST(request: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(request, ctx.params.path || []);
}

export async function PATCH(request: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(request, ctx.params.path || []);
}

export async function DELETE(request: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(request, ctx.params.path || []);
}
