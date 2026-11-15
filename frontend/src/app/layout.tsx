// AeroLaminate Pro - root layout. Author, owner and maintainer: Anwesh Ajitabh Dash.
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AeroLaminate Pro",
  description: "Composite laminate analysis and optimisation workspace. Author, owner and maintainer: Anwesh Ajitabh Dash.",
  authors: [{ name: "Anwesh Ajitabh Dash" }],
  creator: "Anwesh Ajitabh Dash",
  applicationName: "AeroLaminate Pro",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head><meta name="author" content="Anwesh Ajitabh Dash" /></head>
      <body className="font-sans">{children}</body>
    </html>
  );
}
