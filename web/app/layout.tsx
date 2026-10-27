import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Factory Bench",
  description: "Test bench for swappable MRTA (task allocation and scheduling) and MAPF (multi-robot path finding) algorithms.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
