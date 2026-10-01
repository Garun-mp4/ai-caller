const API=process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
export function token(){if(typeof window==='undefined')return '';return localStorage.getItem('token')||''}
export async function api(path:string,options:RequestInit={}){
 const headers=new Headers(options.headers); if(token())headers.set('Authorization','Bearer '+token()); if(!(options.body instanceof FormData))headers.set('Content-Type','application/json');
 const r=await fetch(API+path,{...options,headers,cache:'no-store'}); if(r.status===401 && typeof window!=='undefined'){localStorage.removeItem('token'); if(location.pathname!='/login') location.href='/login'}
 if(!r.ok){let detail='Request failed';try{const j=await r.json();detail=j.detail||detail}catch{} throw new Error(detail)}
 if(r.status===204)return null; return r.json();
}
export {API};
