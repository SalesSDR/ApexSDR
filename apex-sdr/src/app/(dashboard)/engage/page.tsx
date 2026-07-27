/* eslint-disable */
// @ts-nocheck
"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Download, Upload, Grid, List, Layout, Plus, MessageSquare, Mail, Phone, Settings, AlertCircle, ChevronDown } from "lucide-react";
import { API_BASE_URL } from "@/lib/config";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function SequencesPage() {
  const { data, error, mutate } = useSWR(`${API_BASE_URL}/sequences/current`, fetcher);

  const [saving, setSaving] = useState(false);

  // Default Fallbacks while loading
  const rules = data?.rule || {
    max_linkedin_msgs: 3,
    linkedin_interval_days: 2,
    max_emails: 4,
    email_interval_days: 3,
    max_calls: 2,
    call_interval_days: 4,
    response_handling_action: "PAUSE_AND_NOTIFY",
    ai_guided_calls: true,
    call_mode: "MANUAL",
    assigned_lead_owner_id: "Admin",
    auto_handover_to_admin: true,
    dev_mode: false
  };

  const steps = data?.steps || [];

  const handleRuleChange = async (key: string, value: any) => {
    if (!data) return;
    setSaving(true);
    const updatedRule = { ...rules, [key]: value };
    
    // Optimistic update
    mutate({ rule: updatedRule, steps }, false);
    
    try {
      await fetch(`${API_BASE_URL}/sequences/rules`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedRule)
      });
    } catch (e) {
      console.error("Failed to update rules", e);
    } finally {
      mutate();
      setSaving(false);
    }
  };

  if (error) return <div className="p-8 text-red-500">Failed to load sequence configuration. Ensure backend is running.</div>;
  if (!data) return <div className="p-8 text-neutral-400 animate-pulse">Loading sequence engine...</div>;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#0A0A0A] text-white font-sans overflow-hidden">
      
      {/* Header Context */}
      <header className="flex-none px-6 py-4 border-b border-white/10 flex items-center justify-between bg-black/40 backdrop-blur-md">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Engage Sequence: Tier 1 Outreach Apex SDR</h1>
          <p className="text-sm text-neutral-400 mt-1">Apex SDR Multi-Channel Autonomous Flow</p>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex bg-white/5 rounded-lg p-1 mr-4 border border-white/10">
            <button className="p-1.5 rounded-md bg-white/10 text-white"><Layout size={16} /></button>
            <button className="p-1.5 rounded-md text-neutral-400 hover:text-white"><Grid size={16} /></button>
            <button className="p-1.5 rounded-md text-neutral-400 hover:text-white"><List size={16} /></button>
          </div>
          
          <button className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-sm hover:bg-white/10 transition-colors">
            <Sparkles size={14} className="text-blue-400" />
            Research with Apex AI
          </button>
          <button className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-sm hover:bg-orange-500/20 transition-colors">
            Use Apollo AI
          </button>
          <div className="flex items-center gap-2 ml-2 border-l border-white/10 pl-4">
            <button className="p-2 text-neutral-400 hover:text-white"><Upload size={16} /></button>
            <button className="p-2 text-neutral-400 hover:text-white"><Download size={16} /></button>
          </div>
        </div>
      </header>

      {/* Main Canvas + Rules Panel */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Sequence Steps Canvas */}
        <div className="flex-1 overflow-x-auto overflow-y-auto p-6 flex gap-6 bg-[#0A0A0A] custom-scrollbar">
          
          {/* COLUMN 1: LINKEDIN */}
          <div className="flex-none w-80 flex flex-col gap-4">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2 text-blue-400 font-medium">
                <MessageSquare size={18} />
                <span>LinkedIn Steps</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-neutral-400">Max Messages:</span>
                <select 
                  className="bg-transparent border border-white/10 rounded px-1 py-0.5 outline-none text-xs"
                  value={rules.max_linkedin_msgs}
                  onChange={(e) => handleRuleChange("max_linkedin_msgs", parseInt(e.target.value))}
                >
                  {[0,1,2,3,4,5].map(d => <option key={d} value={d} className="bg-neutral-900">{d}</option>)}
                </select>
              </div>
            </div>
            
            <div className="text-xs text-neutral-400 px-1 flex items-center justify-between border-b border-white/5 pb-2">
              <span>Set default interval between messages:</span>
              <select 
                className="bg-transparent border border-white/10 rounded px-1 py-0.5 outline-none"
                value={rules.linkedin_interval_days}
                onChange={(e) => handleRuleChange("linkedin_interval_days", parseInt(e.target.value))}
              >
                {[1,2,3,4,5].map(d => <option key={d} value={d} className="bg-neutral-900">{d} Days</option>)}
              </select>
            </div>

            <SequenceCard title="Message 1 (AI-crafted connect)" badge="Step 1 (LinkedIn)" />
            <SequenceCard title="Message 2 (Follow-up 1)" delay={`After ${rules.linkedin_interval_days} Days`} />
            <SequenceCard title="Message 3 (Final Follow-up)" badge="Step 3 (LinkedIn)" delay={`After ${rules.linkedin_interval_days} Days`} />
            
            <button className="mt-2 py-3 border border-dashed border-white/20 rounded-xl text-neutral-400 flex items-center justify-center gap-2 hover:bg-white/5 hover:text-white transition-colors">
              <Plus size={16} /> Add Step
            </button>
          </div>

          {/* COLUMN 2: EMAIL */}
          <div className="flex-none w-80 flex flex-col gap-4">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <Mail size={18} />
                <span>Email Steps</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-neutral-400">Max Emails:</span>
                <select 
                  className="bg-transparent border border-white/10 rounded px-1 py-0.5 outline-none text-xs"
                  value={rules.max_emails}
                  onChange={(e) => handleRuleChange("max_emails", parseInt(e.target.value))}
                >
                  {[1,2,3,4,5].map(d => <option key={d} value={d} className="bg-neutral-900">{d}</option>)}
                </select>
              </div>
            </div>
            
            <div className="text-xs text-neutral-400 px-1 flex items-center justify-between border-b border-white/5 pb-2">
              <span>Set default interval between emails:</span>
              <select 
                className="bg-transparent border border-white/10 rounded px-1 py-0.5 outline-none"
                value={rules.email_interval_days}
                onChange={(e) => handleRuleChange("email_interval_days", parseInt(e.target.value))}
              >
                {[1,2,3,4,5].map(d => <option key={d} value={d} className="bg-neutral-900">{d} Days</option>)}
              </select>
            </div>

            <SequenceCard title="Email 1 (Intro)" badge="Step 1 (Email)" />
            <SequenceCard title="Email 2 (Case Study)" delay={`After ${rules.email_interval_days} Days`} />
            <SequenceCard title="Email 3 (Value Prop)" delay={`After ${rules.email_interval_days} Days`} />
            <SequenceCard title="Email 4 (Last Attempt)" delay={`After ${rules.email_interval_days} Days`} />
            
            <button className="mt-2 py-3 border border-dashed border-white/20 rounded-xl text-neutral-400 flex items-center justify-center gap-2 hover:bg-white/5 hover:text-white transition-colors">
              <Plus size={16} /> Add Step
            </button>
          </div>

          {/* COLUMN 3: CALL */}
          <div className="flex-none w-80 flex flex-col gap-4">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2 text-amber-400 font-medium">
                <Phone size={18} />
                <span>Call Steps</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-neutral-400">Max Calls:</span>
                <select 
                  className="bg-transparent border border-white/10 rounded px-1 py-0.5 outline-none text-xs"
                  value={rules.max_calls}
                  onChange={(e) => handleRuleChange("max_calls", parseInt(e.target.value))}
                >
                  {[1,2,3,4,5].map(d => <option key={d} value={d} className="bg-neutral-900">{d}</option>)}
                </select>
              </div>
            </div>
            
            <div className="text-xs text-neutral-400 px-1 flex items-center justify-between border-b border-white/5 pb-2">
              <span>Set default interval between calls:</span>
              <select 
                className="bg-transparent border border-white/10 rounded px-1 py-0.5 outline-none"
                value={rules.call_interval_days}
                onChange={(e) => handleRuleChange("call_interval_days", parseInt(e.target.value))}
              >
                {[1,2,3,4,5,7,10].map(d => <option key={d} value={d} className="bg-neutral-900">{d} Days</option>)}
              </select>
            </div>

            <SequenceCard title="Call Task 1" badge={`After ${rules.call_interval_days} Days`} />
            <SequenceCard title="Call Task 2" badge={`After ${rules.call_interval_days} Days`} />
            
            <button className="mt-2 py-3 border border-dashed border-white/20 rounded-xl text-neutral-400 flex items-center justify-center gap-2 hover:bg-white/5 hover:text-white transition-colors">
              <Plus size={16} /> Add Step
            </button>
          </div>

        </div>

        {/* Right Panel: Apex SDR Rules */}
        <div className="w-80 flex-none bg-[#111111] border-l border-white/10 flex flex-col shadow-2xl relative z-10">
          <div className="p-5 border-b border-white/10 flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 text-blue-400 rounded-lg">
              <Settings size={20} />
            </div>
            <h2 className="font-medium">Apex SDR Rules Panel</h2>
          </div>
          
          <div className="p-5 flex-1 overflow-y-auto flex flex-col gap-8">
            
            {/* DEV/TEST MODE TOGGLE */}
            <div className="p-4 bg-orange-500/10 border border-orange-500/30 rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-orange-400 font-semibold">
                  <Settings size={16} /> Dev/Test Mode
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={!!rules.dev_mode} 
                    onChange={(e) => handleRuleChange("dev_mode", e.target.checked)} 
                    className="sr-only peer" 
                  />
                  <div className="w-9 h-5 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-orange-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-orange-500"></div>
                </label>
              </div>
              <p className="text-xs text-orange-400/80 leading-relaxed">
                When enabled, all scheduling intervals (days/hours) are overridden to exactly <strong>60 seconds</strong> for rapid end-to-end pipeline testing.
              </p>
            </div>

            {/* Section 1: Response */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-neutral-300 flex items-center gap-2">
                <AlertCircle size={14} className="text-neutral-500"/> Response Handling
              </label>
              <div className="text-xs text-neutral-500 mb-2">If a prospect replies to an email / LinkedIn:</div>
              <div className="relative">
                <select 
                  className="w-full bg-[#1A1A1A] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none appearance-none cursor-pointer focus:border-blue-500/50 transition-colors"
                  value={rules.response_handling_action}
                  onChange={(e) => handleRuleChange("response_handling_action", e.target.value)}
                >
                  <option value="PAUSE_AND_NOTIFY">Pause sequence and notify admin</option>
                  <option value="CONTINUE">Continue sequence</option>
                  <option value="MARK_WARM_LEAD">Mark as Warm Lead & Handover</option>
                </select>
                <ChevronDown size={14} className="absolute right-3 top-3 pointer-events-none text-neutral-500" />
              </div>
            </div>

            {/* Section 2: Call Config */}
            <div className="space-y-4 pt-6 border-t border-white/5">
              <label className="text-sm font-medium text-neutral-300 flex items-center justify-between">
                <span>Call Configuration</span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" checked={rules.ai_guided_calls} onChange={(e) => handleRuleChange("ai_guided_calls", e.target.checked)} className="sr-only peer" />
                  <div className="w-9 h-5 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-500"></div>
                </label>
              </label>
              <div className="text-xs text-neutral-500 mb-2">AI-Guided Calls:</div>
              
              <div className="space-y-2">
                <label className="flex items-center gap-3 p-3 rounded-lg border border-white/5 hover:border-white/10 cursor-pointer bg-[#1A1A1A] transition-colors">
                  <input 
                    type="radio" 
                    name="callMode" 
                    value="MANUAL" 
                    checked={rules.call_mode === "MANUAL"}
                    onChange={() => handleRuleChange("call_mode", "MANUAL")}
                    className="w-4 h-4 text-blue-500 bg-black border-white/20 focus:ring-blue-500/20 focus:ring-2" 
                  />
                  <span className="text-sm text-neutral-300">Manual SDR Task</span>
                </label>
                <label className="flex items-center gap-3 p-3 rounded-lg border border-white/5 hover:border-white/10 cursor-pointer bg-[#1A1A1A] transition-colors">
                  <input 
                    type="radio" 
                    name="callMode" 
                    value="AUTOMATIC" 
                    checked={rules.call_mode === "AUTOMATIC"}
                    onChange={() => handleRuleChange("call_mode", "AUTOMATIC")}
                    className="w-4 h-4 text-blue-500 bg-black border-white/20 focus:ring-blue-500/20 focus:ring-2" 
                  />
                  <span className="text-sm text-neutral-300">Automatic (AI-assisted dialer)</span>
                </label>
              </div>
            </div>

            {/* Section 3: Lead Routing */}
            <div className="space-y-3 pt-6 border-t border-white/5">
              <label className="text-sm font-medium text-neutral-300">Lead Routing</label>
              <div className="text-xs text-neutral-500 mb-2">Route Warm Leads to:</div>
              <div className="relative">
                <select 
                  className="w-full bg-[#1A1A1A] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none appearance-none cursor-pointer focus:border-blue-500/50 transition-colors"
                  value={rules.assigned_lead_owner_id || "Admin"}
                  onChange={(e) => handleRuleChange("assigned_lead_owner_id", e.target.value)}
                >
                  <option value="Admin">Admin User</option>
                  <option value="SDR1">SDR 1</option>
                  <option value="SDR2">SDR 2</option>
                </select>
                <ChevronDown size={14} className="absolute right-3 top-3 pointer-events-none text-neutral-500" />
              </div>
              <label className="flex items-center gap-2 mt-3 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={rules.auto_handover_to_admin} 
                  onChange={(e) => handleRuleChange("auto_handover_to_admin", e.target.checked)}
                  className="w-4 h-4 rounded bg-[#1A1A1A] border-white/20 text-blue-500 focus:ring-blue-500/20" 
                />
                <span className="text-sm text-neutral-400">Automatically handover to Admin</span>
              </label>
            </div>
          </div>
          
          {saving && (
             <div className="absolute top-0 left-0 right-0 h-1 bg-blue-500/20 overflow-hidden">
                <div className="h-full bg-blue-500 w-1/3 animate-[slide_1s_ease-in-out_infinite]"></div>
             </div>
          )}
        </div>
      </div>

      {/* Footer Summary */}
      <footer className="flex-none px-6 py-3 border-t border-white/10 bg-[#0A0A0A] flex justify-between items-center text-xs text-neutral-400">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
          Summary of results: linked Silicon Valley, & Company Size parameters
        </div>
        <div className="flex items-center gap-4">
          <span>Active Prospects in Sequence: <strong className="text-white text-sm font-medium ml-1">60,902 leads</strong></span>
        </div>
      </footer>
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.2);
        }
      `}} />
    </div>
  );
}

function SequenceCard({ title, delay, badge }: { title: string, delay?: string, badge?: string }) {
  return (
    <motion.div 
      whileHover={{ y: -2 }}
      className="bg-[#1A1A1A] border border-white/10 rounded-xl p-4 shadow-lg cursor-grab active:cursor-grabbing hover:border-white/20 transition-colors relative overflow-hidden"
    >
      <div className="flex justify-between items-start mb-2 relative z-10">
        <span className="text-sm font-medium text-neutral-200">{title}</span>
        {badge && <span className="text-[10px] font-medium bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded shadow-sm">{badge}</span>}
      </div>
      {delay && (
        <div className="mt-3 inline-flex items-center gap-2 text-xs text-neutral-400 bg-white/5 border border-white/5 px-2.5 py-1 rounded-md relative z-10">
          <div className="w-1.5 h-1.5 rounded-full bg-neutral-500"></div>
          {delay}
        </div>
      )}
      
      {/* Subtle top gradient line */}
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>
    </motion.div>
  );
}
