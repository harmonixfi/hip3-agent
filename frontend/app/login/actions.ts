"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createHmac, timingSafeEqual } from "crypto";

export interface LoginState {
  error: string;
}

function makeSessionToken(password: string): string {
  return createHmac("sha256", password).update(password).digest("hex");
}

export async function login(formData: FormData): Promise<LoginState> {
  const submitted = (formData.get("password") ?? "") as string;
  const expected = process.env.DASHBOARD_PASSWORD;

  if (!expected) {
    return { error: "Authentication is not configured. Contact the admin." };
  }

  const submittedBuf = Buffer.from(submitted);
  const expectedBuf = Buffer.from(expected);

  // Pad to same length before timingSafeEqual (it requires equal lengths)
  const maxLen = Math.max(submittedBuf.length, expectedBuf.length);
  const a = Buffer.concat([submittedBuf, Buffer.alloc(maxLen - submittedBuf.length)]);
  const b = Buffer.concat([expectedBuf, Buffer.alloc(maxLen - expectedBuf.length)]);

  const match = timingSafeEqual(a, b) && submittedBuf.length === expectedBuf.length;

  if (!match) {
    return { error: "Incorrect password." };
  }

  const token = makeSessionToken(expected);
  const cookieStore = await cookies();
  cookieStore.set("auth_session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30, // 30 days
    path: "/",
  });

  redirect("/");
}
