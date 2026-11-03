#!/usr/bin/env python3
"""Pediatric allergy care prototype backed by PostgreSQL."""
import os, json, secrets, hashlib, hmac, re, time, io, csv
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse
from database import connect, initialize_schema, reset_sequences, close_pool
from psycopg.errors import UniqueViolation
from network_config import sharing_config, public_base
ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('PORT', '8765'))
HOST = os.environ.get('HOST', '127.0.0.1')
PUBLIC_BASE = public_base()

def now(): return datetime.now().isoformat(timespec='seconds')
def password_hash(password, salt): return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 150000).hex()

def init_db():
    with connect() as c:
        initialize_schema(c)
        if os.environ.get('SEED_DEMO','0') != '1' or c.execute('SELECT count(*) FROM users').fetchone()['count']: return
        salt=secrets.token_hex(16)
        c.execute('INSERT INTO users VALUES(1,%s,%s,%s,%s,%s)',('doctor','林医生','clinician',salt,password_hash('Care2026!',salt)))
        c.execute('INSERT INTO users(id,phone,name,role) VALUES(2,%s,%s,%s)',('13800138000','演示家长','guardian'))
        c.execute('INSERT INTO children VALUES(1,2,%s,%s,%s,%s,%s,%s,%s)',('小禾（演示）','女','2023-04-12','牛奶蛋白（演示记录）','普通膳食','演示资料：用于体验流程，不代表真实病例。',now()))
        for months,h,w in [(5,92.0,12.8),(4,92.8,13.0),(3,93.5,13.1),(2,94.2,13.4),(1,95.0,13.6),(0,95.8,13.8)]:
            day=(date.today()-timedelta(days=30*months)).isoformat()
            c.execute('INSERT INTO measurements(child_id,day,height,weight,source,created_by) VALUES(1,%s,%s,%s,%s,2)',(day,h,w,'家长测量（演示）'))
        answers={'feeding':'普通膳食','avoid':'牛奶及奶制品','substitute':'按医护指导选择替代食物','appetite':'一般','symptoms':['皮肤不适'],'change':'无明显变化','adherence':'部分执行','concerns':'希望了解日常饮食搭配。','family':'无明确家族过敏史','birth_history':'足月出生（演示）'}
        c.execute('INSERT INTO questionnaires(child_id,kind,version,status,answers,created,created_by) VALUES(1,%s,%s,%s,%s,%s,2)',('首次综合评估','1.0','submitted',json.dumps(answers,ensure_ascii=False),now()))
        c.execute('INSERT INTO tasks(child_id,title,due,status,created) VALUES(1,%s,%s,%s,%s)',('完成生长与营养随访问卷',(date.today()+timedelta(days=7)).isoformat(),'pending',now()))
        c.execute('INSERT INTO messages(child_id,user_id,body,created) VALUES(1,1,%s,%s)',('欢迎使用禾护。请先完善健康档案，按计划记录生长和饮食变化。本消息为演示内容。',now()))

        reset_sequences(c)

class APIError(Exception):
    def __init__(self, message, status=400): self.message=message; self.status=status

def required(data, key, maximum=3000):
    v=data.get(key)
    if not isinstance(v,str) or not v.strip(): raise APIError('请填写'+key)
    v=v.strip()
    if len(v)>maximum: raise APIError('内容过长：'+key)
    return v

def valid_date(value, future=True):
    try: d=date.fromisoformat(value)
    except (ValueError, TypeError): raise APIError('日期格式不正确')
    if not future and d>date.today(): raise APIError('日期不能晚于今天')
    return d

def rows(c,sql,args=()):return [dict(r) for r in c.execute(sql,args).fetchall()]

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def respond(self, data, status=200, cookie=None):
        # Persist before sending success, so the next request sees committed state.
        if status < 400 and hasattr(self, 'db'): self.db.commit()
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if cookie:self.send_header('Set-Cookie',cookie + ('; Secure' if PUBLIC_BASE.startswith('https://') else ''))
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def session_token(self):
        authorization = self.headers.get('Authorization')
        if authorization is not None:
            match = re.fullmatch(r'Bearer ([A-Za-z0-9_-]{20,200})', authorization)
            if not match: raise APIError('登录凭据格式不正确',401)
            return match.group(1)
        cookie = SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: raise APIError('请先登录',401)
        token = cookie.get('care_session')
        return token.value if token else ''
    def user(self,c):
        u=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=%s AND s.expires>%s',(self.session_token(),time.time())).fetchone()
        if not u:raise APIError('登录已过期，请重新登录',401)
        return dict(u)
    def child(self,c,u,cid):
        ch=c.execute('SELECT * FROM children WHERE id=%s',(cid,)).fetchone()
        if not ch or (u['role']=='guardian' and ch['owner']!=u['id']):raise APIError('无权访问该患儿',403)
        return dict(ch)
    def clinician(self,u):
        if u['role']!='clinician':raise APIError('此操作仅限医护人员',403)
    def audit(self,c,u,action,cid=None):c.execute('INSERT INTO audit(user_id,action,child_id,created) VALUES(%s,%s,%s,%s)',(u['id'],action,cid,now()))
    def do_GET(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):
            files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/vendor/qrcode.js':'vendor/qrcode.js'}
            if path not in files:self.send_error(404);return
            f=ROOT/'web'/files[path]
            raw=f.read_bytes();self.send_response(200)
            self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[f.suffix[1:]])
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; frame-ancestors 'none'; base-uri 'self'")
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        try:
            with connect() as c:
                self.db=c
                if path=='/api/config':return self.respond({'app':'hehu-care','mode':'development','sms':'development','today':date.today().isoformat(),'bind_host':HOST,'database':'postgresql'})
                u=self.user(c)
                if path=='/api/sharing':
                    self.clinician(u);return self.respond(sharing_config(HOST,PORT))
                if path=='/api/me':return self.respond({'id':u['id'],'name':u['name'],'role':u['role']})
                if path=='/api/children':
                    query="SELECT c.*, (SELECT count(*) FROM tasks t WHERE t.child_id=c.id AND t.status='pending') pending, (SELECT count(*) FROM risks r WHERE r.child_id=c.id AND r.status='open') risks FROM children c"
                    return self.respond(rows(c,query+(' WHERE owner=%s' if u['role']=='guardian' else '')+' ORDER BY c.id', (u['id'],) if u['role']=='guardian' else ()))
                if path=='/api/audit':
                    self.clinician(u);return self.respond(rows(c,'SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 150'))
                m=re.fullmatch(r'/api/children/(\d+)(/export)?',path)
                if m:
                    cid=int(m[1]);ch=self.child(c,u,cid)
                    if m[2]:
                        self.clinician(u);self.audit(c,u,'export',cid)
                        items=rows(c,'SELECT day,height,weight,source FROM measurements WHERE child_id=%s ORDER BY day',(cid,))
                        s=io.StringIO();writer=csv.writer(s);writer.writerow(['患儿编号','测量日期','身高(cm)','体重(kg)','来源'])
                        for r in items:writer.writerow([cid,r['day'],r['height'],r['weight'],("'" if r['source'].startswith(('=','+','-','@')) else '')+r['source']])
                        raw=('\ufeff'+s.getvalue()).encode();c.commit();self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="growth.csv"');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
                    self.audit(c,u,'view',cid)
                    result={'child':ch}
                    for name in ['measurements','questionnaires','assessments','plans','tasks','risks']:
                        sql='SELECT * FROM '+name+' WHERE child_id=%s'
                        if name=='questionnaires' and u['role']=='clinician':sql+=" AND status='submitted'"
                        result[name]=rows(c,sql+' ORDER BY id DESC',(cid,))
                    for q in result['questionnaires']:q['answers']=json.loads(q['answers'])
                    result['messages']=rows(c,'SELECT m.*,u.name,u.role FROM messages m JOIN users u ON m.user_id=u.id WHERE child_id=%s ORDER BY m.id',(cid,))
                    return self.respond(result)
                raise APIError('接口不存在',404)
        except APIError as e:self.respond({'error':e.message},e.status)
        except Exception as e:
            print('GET error:',type(e).__name__,flush=True);self.respond({'error':'服务异常，请稍后重试'},500)
    def do_POST(self):
        try:
            # Same-origin JSON requests only; cookies are HttpOnly + SameSite=Strict.
            origin=self.headers.get('Origin')
            if origin and origin not in {'http://'+self.headers.get('Host',''), PUBLIC_BASE}:raise APIError('请求来源不允许',403)
            if self.headers.get_content_type()!='application/json':raise APIError('请使用JSON请求',415)
            size=int(self.headers.get('Content-Length','0'))
            if size>65536:raise APIError('请求内容过大',413)
            try:data=json.loads(self.rfile.read(size))
            except Exception:raise APIError('请求格式不正确')
            if not isinstance(data,dict):raise APIError('请求格式不正确')
            path=urlparse(self.path).path
            with connect() as c:
                self.db=c
                if path=='/api/auth/code':
                    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('sms-ip:'+self.client_address[0],))
                    phone=required(data,'phone',20)
                    if not re.fullmatch(r'1[3-9]\d{9}',phone):raise APIError('请输入有效的11位手机号')
                    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('phone:'+phone,))
                    old=c.execute('SELECT sent FROM codes WHERE phone=%s',(phone,)).fetchone()
                    t=time.time()
                    if old and t-old['sent']<60:raise APIError('请60秒后再获取验证码',429)
                    c.execute('DELETE FROM sms_limits WHERE stamp<%s',(t-3600,))
                    if c.execute('SELECT count(*) FROM sms_limits WHERE ip=%s',(self.client_address[0],)).fetchone()['count']>=30:raise APIError('请求过于频繁，请稍后重试',429)
                    code=str(secrets.randbelow(900000)+100000)
                    c.execute('INSERT INTO codes VALUES(%s,%s,%s,%s,0) ON CONFLICT (phone) DO UPDATE SET digest=EXCLUDED.digest,expires=EXCLUDED.expires,sent=EXCLUDED.sent,attempts=0',(phone,hashlib.sha256(code.encode()).hexdigest(),t+300,t))
                    c.execute('INSERT INTO sms_limits VALUES(%s,%s)',(self.client_address[0],t))
                    return self.respond({'message':'本地开发模式：未发送真实短信','dev_code':code,'expires_in':300})
                if path=='/api/auth/login':
                    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('login-ip:'+self.client_address[0],))
                    if data.get('client')=='miniprogram' and data.get('role')=='clinician':raise APIError('小程序仅提供监护人登录',403)
                    if data.get('role')=='clinician':
                        t=time.time();ip=self.client_address[0]
                        c.execute('DELETE FROM login_limits WHERE stamp<%s',(t-900,))
                        if c.execute('SELECT count(*) FROM login_limits WHERE ip=%s',(ip,)).fetchone()['count']>=10:raise APIError('登录失败次数过多，请15分钟后重试',429)
                        u=c.execute("SELECT * FROM users WHERE phone=%s AND role='clinician'",(required(data,'username',50),)).fetchone()
                        pwd=required(data,'password',100)
                        if not u or not hmac.compare_digest(u['password'],password_hash(pwd,u['salt'])):
                            c.execute('INSERT INTO login_limits VALUES(%s,%s)',(ip,t));c.commit();raise APIError('账号或密码不正确',401)
                    else:
                        phone=required(data,'phone',20);code=required(data,'code',10)
                        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('phone:'+phone,))
                        old=c.execute('SELECT * FROM codes WHERE phone=%s FOR UPDATE',(phone,)).fetchone()
                        if not old or old['expires']<time.time() or old['attempts']>=5:raise APIError('验证码已失效，请重新获取')
                        if not hmac.compare_digest(old['digest'],hashlib.sha256(code.encode()).hexdigest()):
                            c.execute('UPDATE codes SET attempts=attempts+1 WHERE phone=%s',(phone,));c.commit();raise APIError('验证码不正确')
                        c.execute('DELETE FROM codes WHERE phone=%s',(phone,))
                        c.execute("INSERT INTO users(phone,name,role) VALUES(%s,%s,'guardian') ON CONFLICT (phone) DO NOTHING",(phone,'家长'+phone[-4:]))
                        u=c.execute('SELECT * FROM users WHERE phone=%s',(phone,)).fetchone()
                    token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES(%s,%s,%s)',(token,u['id'],time.time()+43200))
                    self.audit(c,u,'login')
                    if data.get('client')=='miniprogram':return self.respond({'ok':True,'access_token':token,'expires_in':43200})
                    return self.respond({'ok':True},cookie='care_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200')
                u=self.user(c)
                if path=='/api/auth/logout':
                    c.execute('DELETE FROM sessions WHERE token=%s',(self.session_token(),))
                    return self.respond({'ok':True},cookie='care_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if path=='/api/children':
                    if u['role']!='guardian':raise APIError('请由监护人创建患儿档案',403)
                    if data.get('consent') is not True:raise APIError('请确认监护授权和数据使用说明')
                    name=required(data,'name',40);sex=required(data,'sex',5);birth=required(data,'birth',10)
                    b=valid_date(birth,False)
                    if sex not in ['男','女'] or (date.today()-b).days>365.25*18:raise APIError('请填写18岁以内患儿的有效出生信息')
                    vals=[required(data,k,1000) for k in ['allergies','feeding','history']]
                    cur=c.execute('INSERT INTO children(owner,name,sex,birth,allergies,feeding,history,created) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',(u['id'],name,sex,birth,*vals,now()))
                    child_id=cur.fetchone()['id']
                    self.audit(c,u,'create_child_and_guardian_consent',child_id);return self.respond({'id':child_id},201)
                m=re.fullmatch(r'/api/children/(\d+)/(measurements|questionnaires|assessments|plans|messages|tasks|risks)',path)
                if not m:raise APIError('接口不存在',404)
                cid=int(m[1]);kind=m[2];ch=self.child(c,u,cid)
                if kind=='measurements':
                    day=required(data,'day',10);d=valid_date(day,False)
                    if d<date.fromisoformat(ch['birth']):raise APIError('测量日期不能早于出生日期')
                    try:h=float(data.get('height',0));w=float(data.get('weight',0))
                    except (ValueError,TypeError):raise APIError('请填写有效的身高和体重')
                    if not (20<=h<=230 and 0.3<=w<=200):raise APIError('请检查单位和录入值：身高20–230 cm，体重0.3–200 kg（仅录入校验）')
                    if c.execute('SELECT id FROM measurements WHERE child_id=%s AND day=%s',(cid,day)).fetchone():raise APIError('该日期已有记录，请使用其他测量日期')
                    c.execute('INSERT INTO measurements(child_id,day,height,weight,source,created_by) VALUES(%s,%s,%s,%s,%s,%s)',(cid,day,h,w,'医护录入' if u['role']=='clinician' else '家长测量',u['id']))
                elif kind=='questionnaires':
                    if u['role']!='guardian':raise APIError('问卷请由监护人填报',403)
                    status=data.get('status');qkind=data.get('kind');a=data.get('answers')
                    if status not in ['draft','submitted'] or qkind not in ['首次综合评估','生长与营养随访','过敏症状随访']:raise APIError('问卷类型或状态不正确')
                    if not isinstance(a,dict) or len(json.dumps(a))>15000:raise APIError('问卷数据不正确')
                    if status=='submitted':
                        for key in ['feeding','appetite','change','adherence']:required(a,key,300)
                        if not isinstance(a.get('symptoms'),list) or not a['symptoms'] or any(x not in ['暂无明显不适','皮肤不适','消化道不适','呼吸道不适','其他'] for x in a['symptoms']):raise APIError('请选择症状情况')
                        if '暂无明显不适' in a['symptoms'] and len(a['symptoms'])>1:raise APIError('无不适不能与其他症状同时选择')
                    qid=data.get('id')
                    if qid:
                        q=c.execute("SELECT * FROM questionnaires WHERE id=%s AND child_id=%s AND created_by=%s AND status='draft' FOR UPDATE",(qid,cid,u['id'])).fetchone()
                        if not q:raise APIError('草稿不存在或已提交',409)
                        c.execute('UPDATE questionnaires SET kind=%s,status=%s,answers=%s,created=%s WHERE id=%s',(qkind,status,json.dumps(a,ensure_ascii=False),now(),qid))
                    else:c.execute("INSERT INTO questionnaires(child_id,kind,version,status,answers,created,created_by) VALUES(%s,%s,'1.0',%s,%s,%s,%s)",(cid,qkind,status,json.dumps(a,ensure_ascii=False),now(),u['id']))
                    if status=='submitted' and a.get('change')=='有所加重':c.execute("INSERT INTO risks(child_id,reason,status,due,created) VALUES(%s,%s,'open',%s,%s)",(cid,'家长报告症状有所加重，需医护人工复核',(date.today()+timedelta(days=1)).isoformat(),now()))
                    if status=='submitted':
                        taskid=data.get('task_id')
                        if taskid:
                            task=c.execute("SELECT * FROM tasks WHERE id=%s AND child_id=%s AND status='pending' FOR UPDATE",(taskid,cid)).fetchone()
                            if not task:raise APIError('关联随访任务已变化，请刷新后重试',409)
                            c.execute("UPDATE tasks SET status='completed',result='监护人已提交随访问卷' WHERE id=%s",(taskid,))
                elif kind=='assessments':
                    self.clinician(u)
                    attention=required(data,'attention',30)
                    if attention not in ['常规随访','重点关注']:raise APIError('关注级别不正确')
                    c.execute('INSERT INTO assessments(child_id,summary,attention,created,created_by) VALUES(%s,%s,%s,%s,%s)',(cid,required(data,'summary'),attention,now(),u['id']))
                elif kind=='plans':
                    self.clinician(u);nd=required(data,'next_date',10)
                    if valid_date(nd)<date.today():raise APIError('下次随访不能早于今天')
                    vals=[required(data,k) for k in ['goal','diet','guidance']]
                    c.execute('INSERT INTO plans(child_id,goal,diet,guidance,next_date,created,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s)',(cid,*vals,nd,now(),u['id']))
                    c.execute("INSERT INTO tasks(child_id,title,due,status,created) VALUES(%s,%s,%s,'pending',%s)",(cid,'完成生长与营养随访问卷',nd,now()))
                elif kind=='messages':c.execute('INSERT INTO messages(child_id,user_id,body,created) VALUES(%s,%s,%s,%s)',(cid,u['id'],required(data,'body',2000),now()))
                elif kind=='tasks':
                    self.clinician(u);result=required(data,'result',1000)
                    cur=c.execute("UPDATE tasks SET status='completed',result=%s WHERE id=%s AND child_id=%s AND status='pending'",(result,data.get('id'),cid))
                    if not cur.rowcount:raise APIError('任务不存在或已完成',409)
                elif kind=='risks':
                    self.clinician(u);result=required(data,'result',2000)
                    cur=c.execute("UPDATE risks SET status='closed',owner=%s,result=%s WHERE id=%s AND child_id=%s AND status='open'",(u['id'],result,data.get('id'),cid))
                    if not cur.rowcount:raise APIError('事项不存在或已处理',409)
                self.audit(c,u,'create_or_update_'+kind,cid)
                return self.respond({'ok':True},201)
        except APIError as e:self.respond({'error':e.message},e.status)
        except UniqueViolation:self.respond({'error':'记录已存在，请刷新后重试'},409)
        except (ValueError,TypeError):self.respond({'error':'输入格式不正确'},400)
        except Exception as e:
            print('POST error:',type(e).__name__,flush=True);self.respond({'error':'保存失败，请稍后重试'},500)

if __name__=='__main__':
    try:
        init_db()
    except Exception as exc:
        print('数据库初始化失败：'+str(exc),flush=True)
        raise SystemExit(1)
    server = ThreadingHTTPServer((HOST,PORT),Handler)
    print('禾护本地演示服务：http://%s:%s（开发短信模式）'%(HOST,PORT),flush=True)
    if HOST == '0.0.0.0':
        for url in sharing_config(HOST,PORT)['lan_urls']:
            print('同一 Wi-Fi 手机访问：'+url,flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        close_pool()
