import type { Metadata } from "next";
import { Inter, Space_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: '--font-inter' });
const spaceMono = Space_Mono({ subsets: ["latin"], weight: ['400', '700'], variable: '--font-space-mono' });

export const metadata: Metadata = {
  title: "CogniDAO Space Dashboard",
  description: "AI-governed DAO for the future of decentralized communities",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${spaceMono.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
