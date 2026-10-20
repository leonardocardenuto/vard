export function normalizeLocalCameraUrl(input: string): string {
  const value = input.trim();
  if (!value) throw new Error('Informe o IP ou URL da câmera local.');
  const hasScheme = /^[a-z][a-z\d+.-]*:\/\//i.test(value);
  let url: URL;
  try { url = new URL(hasScheme ? value : `http://${value}`); }
  catch { throw new Error('Informe um IP ou URL válido, como 192.168.15.131:8080.'); }
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('A câmera local deve usar HTTP ou HTTPS.');
  const authority = value.split(/[/?#]/)[0];
  if (!hasScheme && !url.port && !/:\d+$/.test(authority)) url.port = '8080';
  if (url.pathname === '/' || url.pathname === '/browserfs.html') url.pathname = '/video';
  url.hash = '';
  return url.toString();
}
