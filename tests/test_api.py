import unittest, subprocess, tempfile, os, sys, time, json, urllib.request, urllib.error, http.cookiejar, socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Client:
    def __init__(self,base): self.base=base;self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(self,path,data=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.base+'/api'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            r=self.opener.open(req);raw=r.read();return r.status,json.loads(raw) if r.headers.get_content_type()=='application/json' else raw
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def login(self,phone):
        status,data=self.request('/auth/code',{'phone':phone});assert status==200,(status,data)
        return self.request('/auth/login',{'phone':phone,'code':data['dev_code']})
class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();cls.base='http://127.0.0.1:'+str(port)
        cls.proc=subprocess.Popen([sys.executable,str(ROOT/'server.py')],env={**os.environ,'PORT':str(port),'CARE_DB':cls.temp.name+'/test.db'},stdout=subprocess.DEVNULL)
        for _ in range(80):
            try:urllib.request.urlopen(cls.base+'/api/config');break
            except Exception:time.sleep(.05)
    @classmethod
    def tearDownClass(cls):cls.proc.terminate();cls.proc.wait();cls.temp.cleanup()
    def test_complete_care_workflow_and_access_control(self):
        parent=Client(self.base);doctor=Client(self.base);other=Client(self.base)
        self.assertEqual(parent.request('/children')[0],401)
        self.assertEqual(parent.login('13900139000')[0],200)
        self.assertEqual(other.login('13700137000')[0],200)
        self.assertEqual(doctor.request('/auth/login',{'role':'clinician','username':'doctor','password':'Care2026!'})[0],200)
        child={'name':'流程测试患儿','sex':'女','birth':'2024-01-01','feeding':'普通膳食','allergies':'待核实','history':'无','consent':True}
        status,data=parent.request('/children',child);self.assertEqual(status,201);cid=data['id'];base='/children/'+str(cid)
        self.assertEqual(other.request(base)[0],403)
        self.assertEqual(other.request(base+'/messages',{'body':'越权留言'})[0],403)
        self.assertEqual(parent.request(base+'/export')[0],403)
        self.assertEqual(parent.request('/audit')[0],403)
        self.assertEqual(parent.request(base+'/assessments',{'summary':'越权评估','attention':'常规随访'})[0],403)
        self.assertEqual(parent.request(base+'/measurements',{'day':'2025-01-01','height':80,'weight':10},origin='https://attacker.test')[0],403)
        self.assertEqual(parent.request(base+'/measurements',{'day':'2023-01-01','height':80,'weight':10})[0],400)
        self.assertEqual(parent.request(base+'/measurements',{'day':'2025-01-01','height':800,'weight':10})[0],400)
        measurement={'day':'2025-01-01','height':80,'weight':10}
        self.assertEqual(parent.request(base+'/measurements',measurement)[0],201)
        self.assertEqual(parent.request(base+'/measurements',measurement)[0],400)
        self.assertEqual(doctor.request(base+'/plans',{'goal':'持续观察','diet':'按医护建议','guidance':'定期记录','next_date':'2099-01-01'})[0],201)
        detail=parent.request(base)[1];tid=detail['tasks'][0]['id']
        draft={'kind':'生长与营养随访','status':'draft','answers':{'concerns':'测试草稿'}}
        self.assertEqual(parent.request(base+'/questionnaires',draft)[0],201)
        self.assertEqual(len(doctor.request(base)[1]['questionnaires']),0)
        qid=parent.request(base)[1]['questionnaires'][0]['id']
        answers={'feeding':'普通膳食','appetite':'一般','change':'有所加重','adherence':'部分执行','symptoms':['皮肤不适']}
        payload={'id':qid,'kind':'生长与营养随访','status':'submitted','answers':answers,'task_id':tid}
        self.assertEqual(parent.request(base+'/questionnaires',payload)[0],201)
        detail=doctor.request(base)[1]
        self.assertEqual(len(detail['questionnaires']),1);self.assertEqual(detail['tasks'][0]['status'],'completed');self.assertEqual(len(detail['risks']),1)
        self.assertEqual(parent.request(base+'/questionnaires',payload)[0],409)
        self.assertEqual(doctor.request(base+'/assessments',{'summary':'人工复核示例','attention':'重点关注'})[0],201)
        self.assertEqual(doctor.request(base+'/risks',{'id':detail['risks'][0]['id'],'result':'已联系家长并安排复诊'})[0],201)
        self.assertEqual(parent.request(base+'/messages',{'body':'家长问题'})[0],201)
        self.assertEqual(doctor.request(base+'/messages',{'body':'医护回复'})[0],201)
        detail=parent.request(base)[1];self.assertEqual(len(detail['messages']),2);self.assertEqual(detail['risks'][0]['status'],'closed')
        self.assertEqual(doctor.request(base+'/export')[0],200)
        self.assertTrue(any(a['action']=='export' for a in doctor.request('/audit')[1]))
        self.assertEqual(parent.request('/auth/logout',{})[0],200);self.assertEqual(parent.request(base)[0],401)
    def test_otp_limits_expiry_and_single_use(self):
        client=Client(self.base);phone='13600136000'
        self.assertEqual(client.request('/auth/code',{'phone':'123'})[0],400)
        status,data=client.request('/auth/code',{'phone':phone});self.assertEqual(status,200)
        self.assertEqual(client.request('/auth/code',{'phone':phone})[0],429)
        for _ in range(5):self.assertEqual(client.request('/auth/login',{'phone':phone,'code':'000000'})[0],400)
        self.assertEqual(client.request('/auth/login',{'phone':phone,'code':data['dev_code']})[0],400)
        phone='13500135000';data=client.request('/auth/code',{'phone':phone})[1]
        self.assertEqual(client.request('/auth/login',{'phone':phone,'code':data['dev_code']})[0],200)
        self.assertEqual(client.request('/auth/login',{'phone':phone,'code':data['dev_code']})[0],400)
    def test_plan_and_questionnaire_validation(self):
        p=Client(self.base);self.assertEqual(p.login('13800138000')[0],200)
        payload={'kind':'首次综合评估','status':'submitted','answers':{}}
        self.assertEqual(p.request('/children/1/questionnaires',payload)[0],400)
        payload['answers']={'feeding':'普通膳食','appetite':'一般','change':'无明显变化','adherence':'尚未制定方案','symptoms':['暂无明显不适','皮肤不适']}
        self.assertEqual(p.request('/children/1/questionnaires',payload)[0],400)
        self.assertEqual(p.request('/children/1/measurements',{'day':'2099-01-01','height':90,'weight':12})[0],400)
if __name__=='__main__':unittest.main(verbosity=2)
