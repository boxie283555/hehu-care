const {PYTHON,createSchema,dropSchema,stopServer}=require('./runtime.cjs');
const playwrightPath=process.env.PLAYWRIGHT_PATH;
let chromium;
try { ({chromium}=require(playwrightPath||'playwright')); }
catch { ({chromium}=require(require('node:path').join(require('node:os').homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'))); }
const {spawn}=require('node:child_process');
const fs=require('node:fs');const os=require('node:os');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
const root=path.resolve(__dirname,'..'),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'hehu-ui-'));
const schema=createSchema();const server=spawn(PYTHON,[path.join(root,'server.py')],{env:{...process.env,PORT:'8766',HEHU_DB_SCHEMA:schema,SEED_DEMO:'1'},stdio:'ignore'});
let browser;try{
for(let i=0;i<50;i++){try{await fetch('http://127.0.0.1:8766/api/config');break;}catch{await new Promise(r=>setTimeout(r,100));}}
browser=await chromium.launch({channel:'chrome',headless:true});
const parent=await browser.newContext({viewport:{width:1440,height:1050}}),p=await parent.newPage(),errors=[];
p.on('pageerror',e=>errors.push(e.message));
await p.goto('http://127.0.0.1:8766');await p.getByRole('button',{name:'获取验证码',exact:true}).click();await p.locator('#dev-code b').waitFor();await p.getByRole('button',{name:'进入健康空间',exact:false}).click();await p.locator('.stats').waitFor();
await p.screenshot({path:path.join(root,'output/禾护_工作概览.png'),fullPage:true});
await p.getByRole('button',{name:'新建患儿档案',exact:false}).click();
await p.locator('[name=name]').fill('安安（流程测试）');await p.locator('[name=birth]').fill('2024-01-01');await p.locator('[name=allergies]').fill('待核实，演示资料');await p.locator('[name=history]').fill('足月出生，演示资料');await p.locator('[name=consent]').check();await p.getByRole('button',{name:'创建健康档案',exact:true}).click();await p.locator('.profile h2').filter({hasText:'安安'}).waitFor();
await p.locator('[data-nav=growth]').first().click();await p.getByRole('button',{name:'添加测量',exact:false}).click();await p.locator('[name=day]').fill('2025-01-01');await p.locator('[name=height]').fill('80');await p.locator('[name=weight]').fill('10');await p.getByRole('button',{name:'保存测量',exact:true}).click();await p.getByRole('cell',{name:'80 cm',exact:true}).waitFor();
await p.locator('[data-nav=questionnaires]').first().click();await p.locator('[data-kind="首次综合评估"]').click();await p.locator('[name=concerns]').fill('希望获得饮食建议');await p.getByRole('button',{name:'保存草稿',exact:true}).click();await p.getByRole('button',{name:'继续填写',exact:true}).click();assert.equal(await p.locator('[name=concerns]').inputValue(),'希望获得饮食建议');await p.getByLabel('皮肤不适',{exact:false}).check();await p.locator('[name=change]').selectOption('有所加重');await p.getByRole('button',{name:'提交问卷',exact:true}).click();await p.getByRole('button',{name:'查看记录',exact:true}).waitFor();
await p.locator('[data-nav=messages]').first().click();await p.locator('[name=body]').fill('最近食欲一般，请问如何记录？');await p.getByRole('button',{name:'发送留言',exact:false}).click();await p.locator('.message p').filter({hasText:'最近食欲一般'}).waitFor();
const staff=await browser.newContext({viewport:{width:1440,height:1050}}),d=await staff.newPage();d.on('pageerror',e=>errors.push(e.message));await d.goto('http://127.0.0.1:8766');await d.getByRole('button',{name:'医护工作台',exact:true}).click();await d.getByRole('button',{name:'进入医护工作台',exact:false}).click();await d.locator('#child-select').waitFor();await d.locator('#child-select').selectOption({label:'安安（流程测试） · '+await p.locator('#child-select option:checked').textContent().then(t=>t.split(' · ')[1])});
await d.locator('[data-nav=plans]').first().click();await d.getByRole('button',{name:'新建评估',exact:false}).click();await d.locator('[name=summary]').fill('已复核问卷，建议持续记录膳食和症状，结合门诊评估。');await d.getByRole('button',{name:'保存评估',exact:true}).click();await d.locator('.plan-entry').waitFor();
await d.getByRole('button',{name:'制定计划',exact:false}).click();await d.locator('[name=goal]').fill('持续记录并完成随访');await d.locator('[name=diet]').fill('按照门诊指导记录膳食，不自行扩大食物回避。');await d.locator('[name=guidance]').fill('每次记录真实测量日期及近期症状。');await d.locator('[name=next_date]').fill('2027-01-01');await d.getByRole('button',{name:'保存并安排随访',exact:true}).click();await d.locator('.next-date').waitFor();
await d.locator('[data-nav=tasks]').first().click();await d.getByRole('button',{name:'复核处理',exact:true}).click();await d.locator('[name=result]').fill('已联系监护人，安排门诊复核。');await d.getByRole('button',{name:'确认完成并记录',exact:true}).click();await d.getByText('已处理',{exact:true}).waitFor();
await d.locator('[data-nav=messages]').first().click();await d.locator('[name=body]').fill('请按实际情况填写，已制定随访计划。');await d.getByRole('button',{name:'回复家长',exact:false}).click();await d.locator('.message p').filter({hasText:'已制定随访计划'}).waitFor();
await p.reload();await p.locator('[data-nav=tasks]').first().click();await p.getByRole('button',{name:'去填写',exact:true}).click();await p.getByLabel('暂无明显不适',{exact:false}).check();await p.getByRole('button',{name:'提交问卷',exact:true}).click();await p.getByText('已完成',{exact:true}).waitFor();
await p.locator('[data-nav=plans]').first().click();await p.getByText('持续记录并完成随访',{exact:true}).waitFor();
await p.setViewportSize({width:390,height:844});await p.locator('[data-nav=overview]').first().click();await p.screenshot({path:path.join(root,'output/禾护_手机端.png'),fullPage:true});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile page should not overflow');
assert.deepEqual(errors,[]);console.log('PASS: browser workflow, draft restore, measurement, clinical assessment, plan, risk handling, message reply, follow-up completion, mobile layout; no JS errors.');
}finally{if(browser)await browser.close();await stopServer(server);dropSchema(schema);fs.rmSync(tmp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1)});
