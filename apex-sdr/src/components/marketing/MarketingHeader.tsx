"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, ArrowRight, Sparkles } from "lucide-react";

export function MarketingHeader() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { name: "Products", href: "/products/apex-sdr" },
    { name: "Platform", href: "/platform" },
    { name: "Solutions", href: "/solutions" },
    { name: "Customers", href: "#" },
    { name: "Company", href: "#" },
  ];

  return (
    <>
      {/* Announcement Banner */}
      <div className="w-full bg-[#E5D5C5] text-black text-xs font-semibold py-2 px-4 flex items-center justify-center gap-2 cursor-pointer hover:bg-[#d4c1ac] transition-colors">
        <span>Apex SDR 2.0 is Live — Experience Autonomous Growth</span>
        <ArrowRight size={14} />
      </div>

      {/* Sticky Navbar */}
      <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-black/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3">
            <img src="/logo.jpg" alt="Apex SDR Logo" className="h-10 w-10 rounded-lg shadow-lg" />
            <span className="font-bold text-xl tracking-tight text-white">Apex SDR</span>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="text-sm font-medium text-gray-400 hover:text-white transition-colors"
              >
                {link.name}
              </Link>
            ))}
          </nav>

          {/* CTA & Mobile Toggle */}
          <div className="flex items-center gap-4">
            <Link
              href="/demo"
              className="hidden md:flex items-center justify-center rounded-full bg-white text-black px-5 py-2 text-sm font-semibold hover:bg-gray-200 transition-colors"
            >
              Get a Live Demo
            </Link>
            <button
              className="md:hidden text-white p-2"
              onClick={() => setMobileMenuOpen(true)}
            >
              <Menu size={24} />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Menu Overlay */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed inset-0 z-[60] bg-black/95 backdrop-blur-3xl flex flex-col pt-20 px-6"
          >
            <button
              className="absolute top-6 right-6 text-white p-2"
              onClick={() => setMobileMenuOpen(false)}
            >
              <X size={24} />
            </button>

            <nav className="flex flex-col gap-6 mt-8">
              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-2xl font-semibold text-gray-300 hover:text-white transition-colors"
                >
                  {link.name}
                </Link>
              ))}
              <div className="mt-8 pt-8 border-t border-white/10 flex flex-col gap-4">
                <Link
                  href="/demo"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center justify-center rounded-full bg-white text-black px-6 py-4 text-lg font-semibold hover:bg-gray-200 transition-colors"
                >
                  Get a Live Demo
                </Link>
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
