import type { TavilySource } from "../types";

export default function SourceCard({ source }: { source: TavilySource }) {
  return (
    <div className="border border-[#30363d] rounded-lg p-3 bg-[#0d1117]">
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[#58a6ff] text-sm font-medium hover:underline block truncate"
      >
        {source.title}
      </a>
      <p className="text-xs text-[#c9d1d9] mt-1 line-clamp-3 leading-relaxed">
        {source.content}
      </p>
      <p className="text-xs text-[#8b949e] mt-1.5 truncate">{source.url}</p>
    </div>
  );
}
