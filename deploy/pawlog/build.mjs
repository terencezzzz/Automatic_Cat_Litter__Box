import {mkdir,readFile,readdir,writeFile} from 'node:fs/promises';
import {extname} from 'node:path';
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.jpg':'image/jpeg','.png':'image/png'};
const root=new URL('./dist/',import.meta.url);
const assets={};
async function collect(directory='') {
  for (const item of await readdir(new URL(directory,root),{withFileTypes:true})) {
    const path=directory+item.name;
    if (path==='server'||path==='.openai') continue;
    if (item.isDirectory()) await collect(path+'/');
    else if (types[extname(path)]) assets['/'+path]=[types[extname(path)],(await readFile(new URL(path,root))).toString('base64')];
  }
}
await collect();
await mkdir(new URL('server/',root),{recursive:true});
const source=await readFile(new URL('./worker.js',import.meta.url),'utf8');
await writeFile(new URL('server/index.js',root),'const ASSETS = '+JSON.stringify(assets)+';\n'+source);
