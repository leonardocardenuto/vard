export type CameraStreamState = 'connecting' | 'connected' | 'error';

export function isMjpegStreamUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol)
      && /\/(?:video|video_feed|videofeed|mjpeg|mjpg|[^/]+\.mje?pg)\/?$/i.test(url.pathname);
  } catch { return false; }
}

// A multipart MJPEG response is an image source, not a WebView document.
// Wait for a decoded image instead of the end of an infinite HTTP response.
export function buildMjpegViewerHtml(source: string): string {
  const url = new URL(source);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Stream HTTP inválido.');
  const safeSource = JSON.stringify(url.toString()).replace(/</g, '\\u003c');
  return `<!doctype html><html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#000}img{display:block;width:100%;height:100%;object-fit:contain}</style>
    </head><body><img id="camera" alt="Câmera ao vivo"><script>
    (function(){
      var image=document.getElementById('camera');
      var ready=false;
      var failed=false;
      function report(type){
        document.documentElement.setAttribute('data-stream-status',type);
        if(window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({type:type}));
      }
      function check(){
        if(!ready && !failed && image.naturalWidth>0){ready=true;report('connected');}
      }
      image.onload=function(){failed=false;check();};
      image.onerror=function(){ready=false;failed=true;report('error');};
      image.src=${safeSource};
      var timer=setInterval(check,250);
      var timeout=setTimeout(function(){if(!ready){failed=true;report('error');}},15000);
      window.addEventListener('beforeunload',function(){clearInterval(timer);clearTimeout(timeout);image.src='';});
    })();</script></body></html>`;
}

export function parseCameraStreamMessage(data: string): CameraStreamState | null {
  try {
    const type: unknown = JSON.parse(data)?.type;
    return type === 'connected' || type === 'error' || type === 'connecting' ? type : null;
  } catch { return null; }
}
