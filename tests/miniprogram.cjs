const {PYTHON,createSchema,dropSchema,stopServer}=require('./runtime.cjs');
// Run native page controllers against the real API using a minimal wx adapter.
// This checks data/navigation contracts, not WeChat's native rendering engine.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),store=new Map(),events=[];let currentRoute='pages/entry/index',navigation='';
global.getCurrentPages=()=>[{route:currentRoute}];
global.wx={getStorageSync:k=>store.get(k)||'',setStorageSync:(k,v)=>store.set(k,v),removeStorageSync:k=>store.delete(k),showToast:x=>events.push(x),redirectTo:x=>{navigation=x.url;},navigateTo:x=>{navigation=x.url;},reLaunch:x=>{navigation=x.url;},
 request:o=>{fetch(o.url,{method:o.method,headers:o.header,...(o.method==='POST'?{body:JSON.stringify(o.data)}:{})}).then(async r=>o.success({statusCode:r.status,data:await r.json()})).catch(o.fail);}};
function loadPage(name){const file=path.join(root,'miniprogram/pages',name,'index.js');delete require.cache[require.resolve(file)];let definition;global.Page=d=>definition=d;require(file);const page={...definition,data:structuredClone(definition.data),setData(values){for(const [key,val]of Object.entries(values)){const parts=key.split('.');let target=this.data;for(const p of parts.slice(0,-1)){if(!target[p])target[p]={};target=target[p];}target[parts.at(-1)]=val;}}};currentRoute='pages/'+name+'/index';return page;}
(async()=>{const temp=fs.mkdtempSync(path.join(os.tmpdir(),'hehu-mini-'));const base='http://127.0.0.1:8768';const schema=createSchema();const server=spawn(PYTHON,[path.join(root,'server.py')],{env:{...process.env,PORT:'8768',HOST:'127.0.0.1',HEHU_DB_SCHEMA:schema,SEED_DEMO:'1'},stdio:'ignore'});let entry;
try{
 for(let i=0;i<60;i++){try{await fetch(base+'/api/config');break;}catch{await new Promise(r=>setTimeout(r,100));}}
 require('../miniprogram/config').apiBase=base;
 const session=require('../miniprogram/utils/session'),api=require('../miniprogram/utils/api');
 assert.equal(session.capture({scene:'../invalid'}),false);assert.equal(session.pending(),'');
 entry=loadPage('entry');entry.onLoad({scene:'nutrition'});entry.setData({phone:'13300133000'});await entry.sendCode();assert.match(entry.data.devCode,/^\d{6}$/);await entry.login();entry.onUnload();assert.ok(store.get('hehu.token'));assert.equal(navigation,'/pages/children/index');assert.equal(session.pending(),'nutrition');
 const children=loadPage('children');await children.onShow();assert.equal(children.data.children.length,0);
 const add=loadPage('child-new');add.setData({form:{name:'小程序演示患儿',sex:'女',birth:'2025-01-01',feeding:'普通膳食',allergies:'不清楚',history:'足月出生'},consent:true});await add.save();const query=Object.fromEntries(new URL('http://example.test'+navigation).searchParams);assert.equal(query.kind,'nutrition');
 const form=loadPage('questionnaire');await form.onLoad(query);assert.equal(form.data.child.name,'小程序演示患儿');form.input({currentTarget:{dataset:{key:'concerns'}},detail:{value:'小程序草稿测试'}});await form.save({currentTarget:{dataset:{status:'draft'}}});assert.ok(form.data.draftId);
 const resumed=loadPage('questionnaire');await resumed.onLoad(query);assert.equal(resumed.data.answers.concerns,'小程序草稿测试');resumed.symptoms({detail:{value:['暂无明显不适']}});resumed.symptoms({detail:{value:['暂无明显不适','皮肤不适']}});assert.deepEqual(resumed.data.answers.symptoms,['皮肤不适']);await resumed.save({currentTarget:{dataset:{status:'submitted'}}});assert.ok(navigation.startsWith('/pages/result/'));assert.equal(session.pending(),'');
 const health=loadPage('health');health.onLoad({child:query.child});await health.onShow();assert.equal(health.data.detail.questionnaires.length,1);assert.equal(health.data.detail.questionnaires[0].status,'submitted');health.setData({body:'来自小程序的留言'});await health.send();assert.equal(health.data.detail.messages[0].body,'来自小程序的留言');health.setData({measure:{day:'2026-01-01',height:'78',weight:'9.2'}});await health.measure();assert.equal(health.data.detail.measurements.length,1);
 await assert.rejects(()=>api.request('/children/1'),/无权/);
 const token=store.get('hehu.token');await api.request('/auth/logout',{});await assert.rejects(()=>api.request('/me'),/登录/);assert.equal(store.has('hehu.token'),false);assert.notEqual(token,'');
 // Every declared page must be present with native page assets and valid JSON.
 const app=JSON.parse(fs.readFileSync(path.join(root,'miniprogram/app.json')));
 for(const page of app.pages)for(const ext of ['js','json','wxml'])assert.ok(fs.existsSync(path.join(root,'miniprogram',page+'.'+ext)));
 console.log('PASS: native mini-program controllers + real API: scan intent, phone verification, bearer session, child creation, draft restore, submission, growth, messages, ownership and logout.');
}finally{if(entry)entry.onUnload();await stopServer(server);dropSchema(schema);fs.rmSync(temp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1);});
