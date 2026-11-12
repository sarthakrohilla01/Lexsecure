import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';


export const Markdown = React.memo(function Markdown({ content }: { content: string }) {
  if (!content) return null;

  return (
    <div className="text-[13.5px] leading-relaxed text-slate-700 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2.5 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
          em: ({ children }) => <em className="italic text-slate-600">{children}</em>,
          del: ({ children }) => <del className="line-through text-slate-400">{children}</del>,
          ul: ({ children }) => <ul className="list-disc pl-5 mb-2.5 space-y-1 marker:text-slate-400">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-2.5 space-y-1 marker:text-slate-400">{children}</ol>,
          li: ({ children }) => <li className="pl-0.5 leading-relaxed [&>p]:mb-1 [&>p:last-child]:mb-0">{children}</li>,
          h1: ({ children }) => <h1 className="text-base font-bold text-slate-900 mt-3 mb-2 first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="text-[15px] font-bold text-slate-900 mt-3 mb-2 first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-bold text-slate-900 mt-3 mb-1.5 first:mt-0">{children}</h3>,
          h4: ({ children }) => <h4 className="text-[13px] font-semibold text-slate-800 mt-2 mb-1 first:mt-0">{children}</h4>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-indigo-300 bg-indigo-50/50 pl-3 pr-2 py-1.5 my-2 text-slate-600 italic rounded-r">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-600 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-800"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="px-1 py-0.5 rounded bg-slate-100 border border-slate-200 text-[12px] font-mono text-rose-600">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-2.5 p-3 rounded-lg bg-slate-900 overflow-x-auto text-[12px] leading-relaxed [&>code]:bg-transparent [&>code]:border-0 [&>code]:p-0 [&>code]:text-slate-100">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-50 text-slate-600">{children}</thead>,
          th: ({ children }) => <th className="px-3 py-2 text-left font-semibold border-b border-slate-200">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 align-top border-b border-slate-100">{children}</td>,
          hr: () => <hr className="my-3 border-slate-200" />,
          br: () => <br />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
