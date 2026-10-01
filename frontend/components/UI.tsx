'use client';
export function Header({title,sub,children}:{title:string,sub?:string,children?:React.ReactNode}){return <div className="flex flex-wrap items-end justify-between gap-3 mb-6"><div><h1 className="text-2xl font-semibold">{title}</h1>{sub&&<p className="muted mt-1 text-sm">{sub}</p>}</div>{children}</div>}
export function Stat({label,value}:{label:string,value:any}){return <div className="card p-4"><div className="text-xs muted">{label}</div><div className="text-2xl font-semibold mt-1">{value??0}</div></div>}
export function Empty({text}:{text:string}){return <div className="card p-10 text-center muted">{text}</div>}
export function fmt(d?:string|null){return d?new Date(d).toLocaleString(): '—'}
