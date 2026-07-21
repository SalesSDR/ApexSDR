import React from 'react';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Live Demo | Apex SDR',
};

export default function DemoPage() {
  return (
    <div className="w-full flex flex-col lg:flex-row min-h-[calc(100vh-64px)]">
      {/* Left Column (Light) */}
      <div className="w-full lg:w-1/2 bg-white text-black p-8 md:p-12 lg:p-24 flex flex-col justify-center">
        <div className="max-w-xl mx-auto w-full">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6 flex items-center gap-3 flex-wrap">
            Grow <img src="/logo.jpg" alt="Apex Logo" className="h-12 w-12 md:h-16 md:w-16 rounded-xl shadow-md object-cover" /> faster.
          </h1>
          <p className="text-lg text-gray-700 mb-8 leading-relaxed font-medium">
            Curious what your pipeline looks like with Apex SDR behind it? Get in touch with our team to see the platform in action and walk through a plan built for you.
          </p>
          <p className="font-bold text-xl mb-10 text-black">Your team, but Apex SDR the output.</p>
          
          <form className="flex flex-col gap-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold text-gray-900">First name*</label>
                <input 
                  type="text" 
                  placeholder="Enter your first name" 
                  className="w-full px-5 py-4 rounded-full border border-gray-300 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-all placeholder:text-gray-400 font-medium"
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold text-gray-900">Last name*</label>
                <input 
                  type="text" 
                  placeholder="Enter your last name" 
                  className="w-full px-5 py-4 rounded-full border border-gray-300 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-all placeholder:text-gray-400 font-medium"
                  required
                />
              </div>
            </div>
            
            <div className="flex flex-col gap-2">
              <label className="text-sm font-bold text-gray-900">Business email*</label>
              <input 
                type="email" 
                placeholder="Enter your business email" 
                className="w-full px-5 py-4 rounded-full border border-gray-300 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-all placeholder:text-gray-400 font-medium"
                required
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold text-gray-900">What CRM do you use?</label>
                <select 
                  defaultValue=""
                  className="w-full px-5 py-4 rounded-full border border-gray-300 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-all bg-white text-gray-500 font-medium"
                >
                  <option value="" disabled>Select an option</option>
                  <option value="salesforce">Salesforce</option>
                  <option value="hubspot">HubSpot</option>
                  <option value="pipedrive">Pipedrive</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-bold text-gray-900">How did you hear about us?</label>
                <select 
                  defaultValue=""
                  className="w-full px-5 py-4 rounded-full border border-gray-300 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition-all bg-white text-gray-500 font-medium"
                >
                  <option value="" disabled>Select an option</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="twitter">Twitter / X</option>
                  <option value="google">Search</option>
                  <option value="referral">Referral</option>
                </select>
              </div>
            </div>
            
            <div className="mt-4">
              <button 
                type="button" 
                className="bg-[#8b8b8b] hover:bg-black text-white font-bold py-4 px-8 rounded-full transition-colors w-fit text-lg"
              >
                Book a Demo
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Right Column (Dark) */}
      <div className="w-full lg:w-1/2 bg-[#0c0c0c] text-white p-8 md:p-12 lg:p-24 flex flex-col justify-center border-l border-white/10 relative overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-white/5 rounded-full blur-[100px] pointer-events-none" />
        
        <div className="max-w-xl mx-auto w-full relative z-10">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tighter mb-16 leading-tight">
            How modern GTM teams<br/>are winning with Apex SDR.
          </h2>
          
          <div className="bg-[#24211d] rounded-2xl overflow-hidden flex flex-col md:flex-row shadow-2xl border border-white/5">
            {/* Quote Side */}
            <div className="p-8 md:w-2/3 flex flex-col justify-between">
              <p className="text-lg md:text-xl leading-relaxed text-[#e6e2db] mb-12 font-medium">
                "We chose Apex SDR for their commitment to partnership. They were willing to build with us, experiment, and learn what works. We didn't know what was possible at first, but the quality of the output now is incredibly impressive."
              </p>
              <div>
                <p className="font-bold text-3xl text-white flex items-center gap-2">
                  7x ROI <span className="text-gray-400 font-normal text-xl">↗</span>
                </p>
                <p className="text-xs font-bold tracking-widest text-gray-500 uppercase mt-3">
                  • From pipeline generated by Apex SDR
                </p>
              </div>
            </div>
            {/* Logo Side */}
            <div className="bg-[#1f1c18] md:w-1/3 p-8 flex items-center justify-center border-t md:border-t-0 md:border-l border-black/20">
               <span className="text-3xl font-extrabold tracking-tight text-white">checkr</span>
            </div>
          </div>
          
          <div className="mt-8 flex items-center gap-4 justify-end text-sm font-mono text-gray-500">
            <span>001</span>
          </div>
        </div>
      </div>
    </div>
  );
}
