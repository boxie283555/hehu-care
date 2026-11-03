const {PYTHON,createSchema,dropSchema,stopServer}=require('./runtime.cjs');
const {chromium}=require('playwright');
const jsQR=require('jsqr');const {PNG}=require('pngjs');
const {spawn}=require('node:child_process');const fs=require('node:fs');const os=require('node:os');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
const root=path.resolve(__dirname,'..'),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'hehu-scan-')),base='http://127.0.0.1:8767';
const schema=createSchema();const server=spawn(PYTHON,[path.join(root,'server.py')],{env:{...process.env,PORT:'8767',HOST:'0.0.0.0',HEHU_DB_SCHEMA:schema,SEED_DEMO:'1'},stdio:'ignore'});
let browser;
try{
 for(let i=0;i<60;i++){try{await fetch(base+'/api/config');break;}catch{await new Promise(r=>setTimeout(r,100));}}
 browser=await chromium.launch({channel:'chrome',headless:true});
 const errors=[],staff=await browser.newContext({viewport:{width:1440,height:1000}}),d=await staff.newPage();d.on('pageerror',e=>errors.push(e.message));
 await d.goto(base);await d.getByRole('button',{name:'医护工作台',exact:true}).click();await d.getByRole('button',{name:'进入医护工作台',exact:false}).click();await d.locator('.stats').waitFor();
 await d.locator('[data-nav=sharing]').click();await d.locator('#qr-base').waitFor();
 const network=await d.evaluate(async()=>await (await fetch('/api/sharing')).json());assert.ok(network.lan_urls.length,'need a detected local network address');
 const lan=network.lan_urls[0];await d.locator('#qr-base').fill('http://127.0.0.1:8767');await d.getByRole('button',{name:'生成二维码',exact:true}).click();await d.getByText('暂未生成二维码',{exact:true}).waitFor();assert.equal(await d.locator('#questionnaire-qr').count(),0);
 await d.locator('#qr-base').fill(lan);await d.locator('#qr-kind').selectOption('nutrition');await d.getByRole('button',{name:'生成二维码',exact:true}).click();await d.locator('#questionnaire-qr').waitFor();
 const link=await d.locator('#qr-link').getAttribute('href');assert.equal(link,lan+'/?questionnaire=nutrition');
 const downloadEvent=d.waitForEvent('download');await d.getByRole('button',{name:'下载 PNG',exact:true}).click();const download=await downloadEvent;const output=path.join(tmp,'qr.png');await download.saveAs(output);
 const png=PNG.sync.read(fs.readFileSync(output));const decoded=jsQR(new Uint8ClampedArray(png.data),png.width,png.height);assert.equal(decoded.data,link,'downloaded PNG must independently decode to the requested questionnaire URL');
 await d.evaluate(()=>{window.print=()=>{window.printInvoked=true;};});await d.getByRole('button',{name:'打印二维码',exact:true}).click();assert.equal(await d.evaluate(()=>window.printInvoked),true);await d.emulateMedia({media:'print'});assert.ok(await d.locator('#qr-print').isVisible());assert.equal(await d.locator('#app').isVisible(),false);assert.equal(await d.locator('#qr-print h2').textContent(),'生长与营养随访');await d.emulateMedia({media:'screen'});
 await d.screenshot({path:path.join(root,'output/禾护_问卷二维码.png'),fullPage:true});
 // A new guardian follows the actual generated LAN link, logs in and creates a child.
 const parent=await browser.newContext({viewport:{width:390,height:844}}),p=await parent.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(link);await p.locator('.login-box h2').filter({hasText:'生长与营养随访'}).waitFor();await p.locator('[name=phone]').fill('13900139123');await p.getByRole('button',{name:'获取验证码',exact:true}).click();await p.locator('#dev-code b').waitFor();await p.getByRole('button',{name:'进入健康空间',exact:false}).click();await p.getByRole('heading',{name:'为哪位孩子填写？',exact:true}).waitFor();
 assert.equal((await p.request.get(lan+'/api/sharing')).status(),403);
 await p.getByRole('button',{name:'建立新患儿档案',exact:false}).click();await p.locator('[name=name]').fill('扫码测试宝宝');await p.locator('[name=birth]').fill('2025-01-01');await p.locator('[name=allergies]').fill('不清楚');await p.locator('[name=history]').fill('足月出生');await p.locator('[name=consent]').check();await p.getByRole('button',{name:'创建健康档案',exact:true}).click();await p.locator('#questionnaire-form').waitFor();assert.equal(await p.locator('.modal-head h2').textContent(),'生长与营养随访');
 await p.locator('[name=concerns]').fill('扫码问卷草稿恢复测试');await p.getByRole('button',{name:'保存草稿',exact:true}).click();await p.locator('#modal').waitFor({state:'hidden'});await p.reload();await p.getByRole('button',{name:'扫码测试宝宝',exact:false}).click();assert.equal(await p.locator('[name=concerns]').inputValue(),'扫码问卷草稿恢复测试');await p.getByLabel('暂无明显不适',{exact:false}).check();await p.getByRole('button',{name:'提交问卷',exact:true}).click();await p.getByRole('heading',{name:'问卷提交成功',exact:true}).waitFor();assert.equal(new URL(p.url()).searchParams.has('questionnaire'),false);assert.equal(await p.evaluate(()=>sessionStorage.getItem('hehu-scan')),null);
 await p.screenshot({path:path.join(root,'output/禾护_扫码提交成功.png'),fullPage:true});
 // Existing guardian with two children must explicitly select the child; never assume the first.
 const seeded=await browser.newContext(),q=await seeded.newPage();q.on('pageerror',e=>errors.push(e.message));await q.goto(lan);await q.getByRole('button',{name:'获取验证码',exact:true}).click();await q.locator('#dev-code b').waitFor();await q.getByRole('button',{name:'进入健康空间',exact:false}).click();await q.locator('.stats').waitFor();
 const res=await q.request.post(lan+'/api/children',{data:{name:'二宝扫码测试',sex:'男',birth:'2024-06-01',allergies:'不清楚',feeding:'普通膳食',history:'无',consent:true}});assert.equal(res.status(),201);const child=await res.json();
 await q.goto(lan+'/?questionnaire=symptoms');await q.getByRole('button',{name:'二宝扫码测试',exact:false}).click();await q.locator('#questionnaire-form').waitFor();assert.equal(await q.locator('.modal-head h2').textContent(),'过敏症状随访');await q.getByLabel('暂无明显不适',{exact:false}).check();await q.getByRole('button',{name:'提交问卷',exact:true}).click();await q.getByRole('heading',{name:'问卷提交成功',exact:true}).waitFor();
 const detail=await (await q.request.get(lan+'/api/children/'+child.id)).json();assert.equal(detail.questionnaires.length,1);assert.equal(detail.questionnaires[0].kind,'过敏症状随访');
 await q.goto(lan+'/?questionnaire=invalid');await q.locator('.workspace').waitFor();assert.equal(await q.locator('#questionnaire-form').count(),0);
 assert.deepEqual(errors,[]);console.log('PASS: QR independent decode, PNG download, print layout, actual LAN access, new guardian + new child, scan draft reload, multi-child selection, targeted submission and access control.');
}finally{if(browser)await browser.close();await stopServer(server);dropSchema(schema);fs.rmSync(tmp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1)});
