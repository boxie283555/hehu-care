const api=require('../../utils/api'),session=require('../../utils/session');
Page({data:{loading:true,detail:null,measure:{day:session.today(),height:'',weight:''},body:'',busy:false,kinds:Object.keys(session.kinds).map(key=>({key,title:session.kinds[key]}))},
 onLoad(q){this.childId=Number(q.child);},async onShow(){await this.load();},
 async load(){try{const detail=await api.request('/children/'+this.childId);detail.measurements.sort((a,b)=>b.day.localeCompare(a.day));this.setData({detail,noClinical:!detail.assessments.length&&!detail.plans.length,loading:false});}catch(e){api.error(e);}},
 fill(e){const kind=e.currentTarget.dataset.kind||'nutrition',task=e.currentTarget.dataset.task;session.setPending(kind);wx.navigateTo({url:'/pages/questionnaire/index?child='+this.childId+'&kind='+kind+(task?'&task='+task:'')});},
 input(e){this.setData({[e.currentTarget.dataset.key]:e.detail.value});},
 async measure(){if(this.data.busy)return;this.setData({busy:true});try{await api.request('/children/'+this.childId+'/measurements',this.data.measure);await this.load();wx.showToast({title:'测量已保存'});}catch(e){api.error(e);}finally{this.setData({busy:false});}},
 async send(){if(this.data.busy)return;this.setData({busy:true});try{await api.request('/children/'+this.childId+'/messages',{body:this.data.body});this.setData({body:''});await this.load();wx.showToast({title:'留言已发送'});}catch(e){api.error(e);}finally{this.setData({busy:false});}},
 back(){wx.reLaunch({url:'/pages/children/index'});}
});
