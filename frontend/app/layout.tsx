import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import NavSidebar from "@/components/NavSidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "OpenClaw Dashboard",
  description: "Delta-neutral funding arbitrage monitoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <NavSidebar />
        <main className="md:ml-56 min-h-screen p-4 md:p-6 pt-14 md:pt-6">
          {children}
        </main>
      </body>
    </html>
  );
}
