(()=>{'use strict';
// Tiingo CORS compatibility layer for static GitHub Pages.
// Tiingo officially supports authentication either by Authorization header or ?token=.
// Custom Authorization headers trigger a browser CORS preflight; query-token GETs do not.
const nativeFetch=window.fetch.bind(window);
function extractToken(headers){
  try{
    const h=new Headers(headers||{}),auth=h.get('Authorization')||'';
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
  const token=extractToken(init?.headers)||(input instanceof Request?extractToken(input.headers):'');
  if(!token)return nativeFetch(input,init);
  u.searchParams.set('token',token);
  const headers=new Headers(init?.headers||{});
  headers.delete('Authorization');
  headers.delete('authorization');
  const next={...init,headers,cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer'};
  window.__MRT_TIINGO_CORS_MODE='query-token-no-preflight';
  return nativeFetch(u.toString(),next);
};
})();
