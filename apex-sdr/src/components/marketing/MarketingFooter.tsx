import Image from "next/image";
import Link from "next/link";

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/10 bg-black pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-4 gap-12">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Image src="/logo.jpg" alt="Apex SDR Logo" width={32} height={32} className="h-8 w-8 rounded shadow-sm" />
            <span className="font-bold text-xl tracking-tight text-white">Apex SDR</span>
          </div>
          <p className="text-gray-400 text-sm">
            The autonomous AI growth agent that scales your outbound pipelines intelligently.
          </p>
        </div>
        
        <div className="flex flex-col gap-3">
          <h4 className="font-semibold text-white mb-2">Product</h4>
          <Link href="/products/apex-sdr" className="text-gray-400 hover:text-white text-sm">Apex Agent</Link>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Integrations</Link>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Pricing</Link>
        </div>

        <div className="flex flex-col gap-3">
          <h4 className="font-semibold text-white mb-2">Resources</h4>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Blog</Link>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Case Studies</Link>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Documentation</Link>
        </div>

        <div className="flex flex-col gap-3">
          <h4 className="font-semibold text-white mb-2">Company</h4>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">About</Link>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Careers</Link>
          <Link href="#" className="text-gray-400 hover:text-white text-sm">Contact</Link>
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-6 mt-16 pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between">
        <p className="text-gray-500 text-sm">© 2026 Apex SDR Inc. All rights reserved.</p>
        <div className="flex gap-4 mt-4 md:mt-0">
          <Link href="#" className="text-gray-500 hover:text-white text-sm">Privacy Policy</Link>
          <Link href="#" className="text-gray-500 hover:text-white text-sm">Terms of Service</Link>
        </div>
      </div>
    </footer>
  );
}
