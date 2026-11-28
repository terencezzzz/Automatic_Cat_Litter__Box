const visitId = /^auto-\d{8}-\d{6}-\d{6}$/;
const images = {'cat.jpg':'image/jpeg','waste-original.png':'image/png','detection.jpg':'image/jpeg'};
const recordHeaders = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
const json = (body,status=200) => Response.json(body,{status,headers:recordHeaders});
const keyFor = id => 'vision-visits/' + id;

function matchesSecret(provided, expected) {
  if (!expected || provided.length !== expected.length) return false;
  let difference = 0;
  for (let i=0; i<expected.length; i++) difference |= provided.charCodeAt(i) ^ expected.charCodeAt(i);
  return difference === 0;
}

function authorizedUpload(request,env) {
  return matchesSecret(request.headers.get('Authorization') || '', env.PAWLOG_UPLOAD_KEY ? 'Bearer ' + env.PAWLOG_UPLOAD_KEY : '');
}

async function upload(request, env) {
  if (!authorizedUpload(request,env)) {
    return json({error:'Unauthorized'},401);
  }
  const length = Number(request.headers.get('Content-Length'));
  if (!length || length > 6_000_000) return json({error:'Invalid upload size'},413);
  let record;
  try { record = await request.json(); } catch { return json({error:'Invalid JSON'},400); }
  if (!record || typeof record.id !== 'string' || !visitId.test(record.id) || typeof record.capturedAt !== 'string' ||
      !Number.isFinite(Date.parse(record.capturedAt)) || typeof record.wasteDetected !== 'boolean' ||
      Object.keys(images).some(name => typeof record.images?.[name] !== 'string' || !/^[A-Za-z0-9+/]+={0,2}$/.test(record.images[name]))) {
    return json({error:'Invalid visit'},400);
  }
  const {id,capturedAt,wasteDetected} = record;
  const storedImages = Object.fromEntries(Object.keys(images).map(name => [name,record.images[name]]));
  const stored = await env.BUCKET.put(keyFor(id),JSON.stringify(storedImages),{
    onlyIf:{etagDoesNotMatch:'*'},customMetadata:{id,capturedAt,wasteDetected:String(wasteDetected)}
  });
  if (!stored) return json({id},200);
  return json({id},201);
}

async function saveObservation(request,env,id) {
  if (!authorizedUpload(request,env)) return json({error:'Unauthorized'},401);
  const length = Number(request.headers.get('Content-Length'));
  if (!length || length > 2000) return json({error:'Invalid observation size'},413);
  let body;
  try { body = await request.json(); } catch { return json({error:'Invalid JSON'},400); }
  if (body?.status !== 'failed' && body?.status !== 'complete') {
    return json({error:'Invalid observation status'},400);
  }
  const visit = await env.BUCKET.head(keyFor(id));
  if (visit?.customMetadata?.wasteDetected !== 'true') return json({error:'Visit not found'},404);
  let metadata = {status:'failed'};
  if (body.status === 'complete') {
    const fields = ['color','shape','visible_details','limitations'];
    if (fields.some(field => typeof body.observation?.[field] !== 'string' ||
        !body.observation[field].trim() || body.observation[field].length > 160)) {
      return json({error:'Invalid observation fields'},400);
    }
    const categories = {
      appearance:['typical','atypical','unclear'],
      finding:['none','loose','hard','unusual_color'],
      blood:['none','possible_red','possible_tarry'],
    };
    const result = Object.fromEntries(fields.map(field=>[field,body.observation[field]]));
    if (Object.keys(categories).some(field=>Object.hasOwn(body.observation,field))) {
      for (const [field,values] of Object.entries(categories)) {
        if (!values.includes(body.observation[field])) return json({error:'Invalid observation categories'},400);
        result[field] = body.observation[field];
      }
      if (result.blood !== 'none' || result.finding !== 'none') result.appearance = 'atypical';
    }
    const observation = JSON.stringify(result);
    if (new TextEncoder().encode(observation).length > 1200) return json({error:'Observation too large'},400);
    metadata = {status:'complete',observation};
  }
  const key = keyFor(id) + '/observation';
  const options = {customMetadata:metadata};
  if (body.status === 'failed') options.onlyIf = {etagDoesNotMatch:'*'};
  await env.BUCKET.put(key,'',options);
  return json({id});
}

async function listVisits(env) {
  const objects = [];
  let cursor;
  do {
    const page = await env.BUCKET.list({prefix:'vision-visits/',include:['customMetadata'],cursor});
    objects.push(...page.objects);
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  const byKey = new Map(objects.map(object=>[object.key,object.customMetadata]));
  return json(objects.filter(object=>object.customMetadata?.id).map(({key,customMetadata:m})=>{
    const analysis = byKey.get(key+'/observation');
    return {
      id:m.id,capturedAt:m.capturedAt,wasteDetected:m.wasteDetected==='true',
      analysisStatus:analysis?.status,
      observation:analysis?.observation ? JSON.parse(analysis.observation) : undefined,
    };
  }).sort((a,b)=>Date.parse(b.capturedAt)-Date.parse(a.capturedAt)).slice(0,100));
}

export default {
  async fetch(request,env) {
    const path = new URL(request.url).pathname;
    const recordPath = path.match(/^\/api\/vision-visits\/(auto-\d{8}-\d{6}-\d{6})$/);
    if (recordPath) {
      if (request.method !== 'DELETE') return json({error:'Method not allowed'},405);
      if (!authorizedUpload(request,env)) return json({error:'Unauthorized'},401);
      const id = recordPath[1];
      const key = keyFor(id);
      const record = await env.BUCKET.head(key);
      if (!record) return json({error:'Visit not found'},404);
      if (record.customMetadata?.wasteDetected !== 'false') {
        return json({error:'Only negative detection records can be deleted'},409);
      }
      await env.BUCKET.delete([key,key+'/observation']);
      return json({id,deleted:true});
    }
    const observationPath = path.match(/^\/api\/vision-visits\/(auto-\d{8}-\d{6}-\d{6})\/observation$/);
    if (observationPath) {
      if (request.method !== 'POST') return json({error:'Method not allowed'},405);
      return saveObservation(request,env,observationPath[1]);
    }
    if (path==='/api/vision-visits' || path.startsWith('/visit-image/')) {
      if (path==='/api/vision-visits' && request.method==='POST') return upload(request,env);
      if (request.method!=='GET') return json({error:'Method not allowed'},405);
      if (path==='/api/vision-visits') return listVisits(env);
      const [, , id, name, extra] = path.split('/');
      if (!visitId.test(id) || !Object.hasOwn(images,name) || extra!==undefined) return json({error:'Not found'},404);
      const object = await env.BUCKET.get(keyFor(id));
      if (!object) return json({error:'Not found'},404);
      const stored = await object.json();
      const bytes = Uint8Array.from(atob(stored[name]), character=>character.charCodeAt(0));
      return new Response(bytes,{headers:{...recordHeaders,'Content-Type':images[name]}});
    }
    const asset = ASSETS[path==='/' ? '/index.html' : path];
    if (!asset || !Object.hasOwn(ASSETS,path==='/' ? '/index.html' : path)) return new Response('Not found',{status:404});
    if (request.method!=='GET' && request.method!=='HEAD') return new Response('Method not allowed',{status:405});
    const [type,body] = asset;
    return new Response(request.method==='HEAD' ? null : Uint8Array.from(atob(body), character=>character.charCodeAt(0)),{
      headers:{'Content-Type':type,'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'}
    });
  }
};
