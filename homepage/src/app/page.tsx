import Image from "next/image";

export default function Home() {
  return (
    <main className="min-h-screen bg-black text-white overflow-hidden">
      {/* Main container */}
      <div className="relative h-screen w-full flex flex-col">
        {/* Header */}
        <header className="p-4 border-b border-teal-800/30 flex items-center justify-between bg-black/80">
          <div className="flex items-center">
            <div className="text-teal-400 font-mono text-lg">ESD CONTROL</div>
          </div>
          <nav className="flex space-x-6">
            {['CENTRAL', 'MAPPING', 'NETWORK', 'STATUS', 'METRICS', 'ENGINE', 'DATA', 'SATELLITE', 'CONSOLE'].map((item) => (
              <div key={item} className="text-teal-400/70 hover:text-teal-300 text-xs tracking-wide cursor-pointer">
                {item}
              </div>
            ))}
          </nav>
          <div className="text-teal-400/70 text-xs">ESD ONLINE</div>
        </header>

        {/* Main content */}
        <div className="flex-1 grid grid-cols-12 grid-rows-6 gap-2 p-4 bg-black/90 relative">
          {/* Decorative background grid */}
          <div className="absolute inset-0 grid grid-cols-[repeat(40,1fr)] grid-rows-[repeat(40,1fr)] opacity-20">
            {Array.from({ length: 1600 }).map((_, i) => (
              <div key={i} className="border-[0.5px] border-teal-900/20"></div>
            ))}
          </div>

          {/* Earth visualization */}
          <div className="col-span-4 row-span-6 relative border border-teal-800/50 bg-black/60 p-3 rounded-sm">
            <div className="absolute top-3 left-3 z-10 flex flex-col">
              <div className="text-teal-300 text-sm font-mono">ESD: EARTH</div>
              <div className="text-teal-400 text-xs font-mono">STATUS: ONLINE</div>
              <div className="text-teal-500/70 text-[10px] font-mono">ESD NETWORK GLOBAL SPACE BASE</div>
            </div>
            <div className="w-full h-full flex items-center justify-center">
              <div className="w-4/5 h-4/5 rounded-full bg-gradient-to-br from-teal-700 via-teal-900/70 to-teal-500/30 animate-pulse-slow relative overflow-hidden">
                {/* Simulated Earth globe with gradients instead of texture */}
                <div className="absolute inset-0 rounded-full bg-gradient-radial from-teal-500/30 to-transparent opacity-50"></div>
                {/* Grid overlay */}
                <div className="absolute inset-0 rounded-full border-[1px] border-teal-400/20 grid grid-cols-8 grid-rows-8">
                  {Array.from({ length: 64 }).map((_, i) => (
                    <div key={i} className="border-[0.5px] border-teal-400/10"></div>
                  ))}
                </div>
                {/* Random "continent" shapes */}
                <div className="absolute top-[20%] left-[30%] h-[15%] w-[25%] bg-teal-300/20 rounded-full blur-sm"></div>
                <div className="absolute top-[50%] left-[20%] h-[20%] w-[30%] bg-teal-300/20 rounded-full blur-sm"></div>
                <div className="absolute top-[30%] left-[60%] h-[25%] w-[15%] bg-teal-300/20 rounded-full blur-sm"></div>
              </div>
            </div>
            <div className="absolute bottom-3 left-3 flex flex-col gap-1">
              {['O: 2034', 'D: 0243', 'N: 9281'].map((item) => (
                <div key={item} className="text-teal-400/80 text-xs font-mono">{item}</div>
              ))}
            </div>
          </div>

          {/* Moon, Mars and other planets */}
          <div className="col-span-8 row-span-4 relative border border-teal-800/50 bg-black/60 p-3 rounded-sm flex items-center justify-center">
            <div className="absolute top-0 left-0 w-full h-full">
              {/* Orbit lines */}
              <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[90%] h-[90%] rounded-full border border-teal-800/30"></div>
              <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[70%] h-[70%] rounded-full border border-teal-800/30"></div>
              <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[40%] h-[40%] rounded-full border border-teal-800/30"></div>
              
              {/* Moon */}
              <div className="absolute top-[30%] left-[30%] w-16 h-16">
                <div className="absolute top-0 left-0 bg-gray-700/80 w-8 h-8 rounded-full"></div>
                <div className="absolute top-0 left-0 text-xs text-teal-400 font-mono whitespace-nowrap ml-10">
                  <div>ESD: MOON</div>
                  <div className="text-[10px]">STATUS: ONLINE</div>
                </div>
              </div>
              
              {/* Mars */}
              <div className="absolute top-[40%] left-[70%] w-16 h-16">
                <div className="absolute top-0 left-0 bg-red-900/80 w-10 h-10 rounded-full"></div>
                <div className="absolute top-0 left-0 text-xs text-teal-400 font-mono whitespace-nowrap ml-12">
                  <div>ESD: MARS</div>
                  <div className="text-[10px]">STATUS: ONLINE</div>
                </div>
              </div>
              
              {/* Rhea Moon */}
              <div className="absolute top-[70%] left-[75%] w-16 h-16">
                <div className="absolute top-0 left-0 bg-gray-500/80 w-6 h-6 rounded-full"></div>
                <div className="absolute top-0 left-0 text-xs text-teal-400 font-mono whitespace-nowrap ml-8">
                  <div>ESD: RHEA MOON</div>
                  <div className="text-[10px]">STATUS: ONLINE</div>
                </div>
              </div>
            </div>
          </div>

          {/* Data panels */}
          <div className="col-span-8 row-span-2 grid grid-cols-6 gap-2">
            {/* Data panels */}
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="border border-teal-800/50 bg-black/60 p-2 rounded-sm flex flex-col justify-between">
                <div className="text-teal-400/70 text-[10px] font-mono">DATA {i+1}</div>
                <div className="h-full flex items-center justify-center">
                  <div className="w-full h-3/4 bg-teal-900/20 rounded-sm border border-teal-700/30 relative overflow-hidden">
                    <div 
                      className="absolute bottom-0 left-0 w-full bg-teal-500/30 animate-pulse"
                      style={{ height: `${Math.random() * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Status indicators */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="w-8 h-8 rounded-full border border-teal-500/50 flex items-center justify-center bg-black/80">
                <div className="w-4 h-4 rounded-full bg-teal-500/70 animate-pulse"></div>
              </div>
            ))}
          </div>
        </div>
        </div>
      </main>
  );
}
