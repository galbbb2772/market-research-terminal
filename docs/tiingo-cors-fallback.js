(()=>{'use strict';
const PROXY='https://mrt-tiingo-proxy.onrender.com';
const nativeFetch=window.fetch.bind(window);
function rawHeaderValue(headers,name){
  if(!headers)return'';
  try{
    if(headers instanceof Headers)return headers.get(name)||'';
    if(Array.isArray(headers)){let row=headers.find(x=>Array.isArray(x)&&String(x[0]).toLowerCase()===name.toLowerCase());return row?String(row[1]||''):''}
    if(typeof headers==='object'){
      let key=Object.keys(headers).find(k=>k.toLowerCase()===name.toLowerCase());
      return key?String(headers[key]||''):'';
    }
  }catch(_){return''}
  return'';
}
function cleanToken(raw){
  let s=String(raw||'').trim().replace(/^Token\s+/i,'').trim();
  s=s.replace(/[\u200B-\u200D\uFEFF]/g,'');
  return s;
}
function tokenFrom(input,init,u){
  let h1=rawHeaderValue(init?.headers,'X-Tiingo-Token')||rawHeaderValue(init?.headers,'Authorization');
  let h2=input instanceof Request?(rawHeaderValue(input.headers,'X-Tiingo-Token')||rawHeaderValue(input.headers,'Authorization')):'';
  return cleanToken(h1||h2||u.searchParams.get('token')||'');
}
window.fetch=function(input,init={}){
  let raw='';
  try{raw=input instanceof Request?input.url:String(input)}catch(_){return nativeFetch(input,init)}
  let u;
  try{u=new URL(raw,location.href)}catch(_){return nativeFetch(input,init)}
  if(u.origin!=='https://api.tiingo.com')return nativeFetch(input,init);

  const token=tokenFrom(input,init,u);
  if(!token)return nativeFetch(input,init);
  if(!/^[\x21-\x7E]+$/.test(token)){
    return Promise.reject(new Error('Tiingo API Token 含有中文、全角符号或不可见字符。请从 Tiingo 控制台重新复制纯 Token，不要带“Token ”、引号或说明文字。'));
  }

  u.searchParams.delete('token');
  const proxied=new URL(PROXY+u.pathname);
  proxied.search=u.search;
  const headers=new Headers();
  headers.set('X-Tiingo-Token',token);
  headers.set('Accept','application/json');
  const next={method:init?.method||'GET',headers,cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer'};
  if(init?.body!=null)next.body=init.body;
  window.__MRT_TIINGO_CORS_MODE='render-proxy';
  window.__MRT_TIINGO_PROXY=PROXY;
  return nativeFetch(proxied.toString(),next);
};
})();
