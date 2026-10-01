(()=>{'use strict';
const PROXY='https://mrt-tiingo-proxy.onrender.com';
const nativeFetch=window.fetch.bind(window);
function tokenFromHeaders(headers){
  try{
    const h=new Headers(headers||{});
    const direct=(h.get('X-Tiingo-Token')||'').trim();
    if(direct)return direct;
    const auth=h.get('Authorization')||'';
    const m=auth.match(/^Token\s+(.+)$/i);
    return m?m[1].trim():'';
  }catch(_){return''}
}
window.fetch=function(input,init={}){
  let raw='';
  try{raw=input instanceof Request?input.url:String(input)}catch(_){return nativeFetch(input,init)}
  let u;
  try{u=new URL(raw,location.href)}catch(_){return nativeFetch(input,init)}
  if(u.origin!=='https://api.tiingo.com')return nativeFetch(input,init);

  const inputHeaders=input instanceof Request?input.headers:null;
  const token=tokenFromHeaders(init?.headers)||tokenFromHeaders(inputHeaders)||(u.searchParams.get('token')||'').trim();
  if(!token)return nativeFetch(input,init);

  u.searchParams.delete('token');
  const proxied=new URL(PROXY+u.pathname);
  proxied.search=u.search;

  const headers=new Headers(init?.headers||inputHeaders||{});
  headers.delete('Authorization');
  headers.delete('authorization');
  headers.delete('X-Tiingo-Token');
  headers.set('X-Tiingo-Token',token);
  headers.set('Accept','application/json');

  const next={...init,headers,cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer'};
  window.__MRT_TIINGO_CORS_MODE='render-proxy';
  window.__MRT_TIINGO_PROXY=PROXY;
  return nativeFetch(proxied.toString(),next);
};
})();
